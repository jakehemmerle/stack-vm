from enum import Enum
import sys


class _CommandType(Enum):
    C_ARITHMETIC = 1
    C_PUSH = "push"
    C_POP = "pop"
    C_LABEL = 4
    C_GOTO = 5
    C_IF = 6
    C_FUNCTION = 7
    C_RETURN = 8
    C_CALL = 9

    arithmetic_commands = ["add", "sub", "neg",
                           "eq", "gt", "lt", "and", "or", "not"]

    @staticmethod
    def from_string(command: str):
        if command in ["add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"]:
            return _CommandType.C_ARITHMETIC
        elif command == "push":
            return _CommandType.C_PUSH
        elif command == "pop":
            return _CommandType.C_POP
        elif command.startswith("("):
            return _CommandType.C_LABEL
        elif command == "goto":
            return _CommandType.C_GOTO
        # elif command == "if-goto":
        #     return _CommandType.C_IF
        elif command == "function":
            return _CommandType.C_FUNCTION
        elif command == "return":
            return _CommandType.C_RETURN
        elif command == "call":
            return _CommandType.C_CALL
        else:
            raise ValueError(command)


class VmTranslator:
    """VM Translator converts VM code to Hack assembly code."""

    def __init__(self, in_file, out_file="out.asm"):
        self.parser = Parser(in_file)
        self.code_writer = CodeWriter(out_file)

    def translate(self):
        while self.parser.has_more_lines():
            self.parser.advance()
            current_instruction = self.parser.command_type()
            if current_instruction == _CommandType.C_ARITHMETIC:
                self.code_writer.write_arithmetic(self.parser.arg1())
            elif current_instruction in [_CommandType.C_PUSH, _CommandType.C_POP]:
                self.code_writer.write_push_pop(
                    current_instruction, self.parser.arg1(), self.parser.arg2())
            else:
                print("Not implemented yet")

        # for vm_instruction in self.code_writer.assembly:
        #     for asm_instruction in vm_instruction:
        #         print(asm_instruction)

    def close(self):
        self.code_writer.close()

        return 0


class Parser:
    """
    Parser parses a file of VM instructions and breaks it into different pieces to be used by the CodeWriter for translation
    """

    _vm_instructions: list[str]
    _current_instruction_index: int
    _current_parsed_instruction: dict

    def __init__(self, in_file):
        self._vm_instructions = []
        self._current_instruction_index = 0

        with open(in_file, 'r') as f:
            raw_vm_instructions = f.read().splitlines()

        # remove comments and empty lines
        for line in raw_vm_instructions:
            instruction = line.strip().split("//")[0]
            if instruction != "":
                self._vm_instructions.append(instruction)

        self._current_parsed_instruction = None

    def _current_raw_instruction(self):
        return self._vm_instructions[self._current_instruction_index - 1]

    @staticmethod
    def _parse_instruction(raw_instruction):
        split_instruction = raw_instruction.split()
        instruction_type = _CommandType.from_string(split_instruction[0])

        if instruction_type == _CommandType.C_ARITHMETIC:
            arg1 = split_instruction[0]
            arg2 = None
        else:
            arg1 = split_instruction[1]
            arg2 = split_instruction[2]

        return {
            'type': instruction_type,
            'arg1': arg1,
            'arg2': arg2
        }

    def has_more_lines(self):
        return self._current_instruction_index < (len(self._vm_instructions))

    def advance(self):
        if not self.has_more_lines():
            raise ValueError("No more lines to advance to")

        self._current_instruction_index += 1

        self._current_parsed_instruction = self._parse_instruction(
            self._current_raw_instruction())

    def command_type(self):
        return self._current_parsed_instruction['type']

    def arg1(self):
        return self._current_parsed_instruction['arg1']

    def arg2(self):
        return self._current_parsed_instruction['arg2']


class CodeWriter:
    registers = {
        'sp': 0,
        'lcl': 1,
        'arg': 2,
        'this': 3,
        'that': 4,
        'temp': 5,
        'static': 16,
    }

    # we could generate a in a symbol table to make more effective use of memory but this is fine for now
    default_bases = {
        'sp': 256,
    }

    assembly: list[list[str]]
    _temp_vm_instruction: list[str]

    def __init__(self, out_file):
        self.assembly = [[
            "// initialize register values",
            "@256",
            "D=A",
            "@SP",
            "M=D",
        ]]
        self._temp_vm_instruction = []
        self._lt_counter = 0
        self.out_file = out_file

    """new lambda helpers: a_to_d, sp_to_d, deref_to_d, d_to_sp, d_to_deref, inc_sp, dec_sp"""

    def _pop_to_d(self):
        """*a is x and d is y; MAKE SURE to write to M after"""
        self._temp_vm_instruction.append("@SP")
        self._temp_vm_instruction.append("AM=M-1")
        self._temp_vm_instruction.append("D=M")

    def _generate_comparison(self, comparison):
        instruction = None
        if comparison == "eq":
            instruction = "JEQ"
        elif comparison == "gt":
            instruction = "JGT"
        elif comparison == "lt":
            instruction = "JLT"
        else:
            raise ValueError(comparison)

        # sp--; y into D
        self._temp_vm_instruction.append("@SP")
        self._temp_vm_instruction.append("AM=M-1")
        # D = *sp
        self._temp_vm_instruction.append("D=M")

        # sp--; x - y into D
        self._temp_vm_instruction.append("@SP")
        self._temp_vm_instruction.append("AM=M-1")
        # D = *sp - D
        self._temp_vm_instruction.append("D=M-D")

        # @LT_TRUE_#;
        self._temp_vm_instruction.append(
            "@LT_TRUE_{}".format(self._lt_counter))
        # D; JLT
        self._temp_vm_instruction.append("D;{}".format(instruction))

        # set *sp to false
        # @SP
        self._temp_vm_instruction.append("@SP")
        # A=M
        self._temp_vm_instruction.append("A=M")
        # M=0
        self._temp_vm_instruction.append("M=0")
        # @LT_END_#;
        self._temp_vm_instruction.append(
            "@LT_END_{}".format(self._lt_counter))
        # 0; JMP
        self._temp_vm_instruction.append("0;JMP")

        # true
        # (LT_TRUE_#)
        self._temp_vm_instruction.append(
            "(LT_TRUE_{})".format(self._lt_counter))
        # @SP
        self._temp_vm_instruction.append("@SP")
        # A=M
        self._temp_vm_instruction.append("A=M")
        # M=true
        self._temp_vm_instruction.append("M=-1")

        # (LT_END_#)
        self._temp_vm_instruction.append(
            "(LT_END_{})".format(self._lt_counter))
        # sp++
        self._temp_vm_instruction.append("@SP")
        self._temp_vm_instruction.append("M=M+1")

        # increment lt counter
        self._lt_counter += 1

    def write_arithmetic(self, command: str):
        self._temp_vm_instruction = []

        if command == "add":
            # decrement sp
            # copy *sp to D
            # decrement A
            # store M = M + D
            self._temp_vm_instruction.append("// add")
            self._pop_to_d()
            self._temp_vm_instruction.append("A=A-1")
            self._temp_vm_instruction.append("M=M+D")
        elif command == "sub":
            # decrement sp
            # copy *sp to D
            # decrement A
            # store M = M - D
            self._temp_vm_instruction.append("// sub")
            self._pop_to_d()
            self._temp_vm_instruction.append("A=A-1")
            self._temp_vm_instruction.append("M=M-D")
        elif command == "neg":
            self._temp_vm_instruction.append("// neg")
            self._temp_vm_instruction.append(
                "@SP")
            self._temp_vm_instruction.append("A=M-1")
            # might need to fix this for booleans, not ints
            self._temp_vm_instruction.append("M=-M")
        elif command in ["lt", "gt", "eq"]:
            self._generate_comparison(command)
        elif command in ["and", "or"]:
            operator = "&" if command == "and" else "|"
            self._temp_vm_instruction.append("// {}".format(command))
            self._pop_to_d()
            self._temp_vm_instruction.append("A=A-1")
            self._temp_vm_instruction.append("M=M{}D".format(operator))
        elif command == "not":
            self._temp_vm_instruction.append("// not")
            self._temp_vm_instruction.append("@SP")
            self._temp_vm_instruction.append("A=M-1")
            self._temp_vm_instruction.append("M=!M")
        else:
            raise ValueError(command)

        # cleanup
        self.assembly.append(self._temp_vm_instruction)
        self._temp_vm_instruction = []

    def write_push_pop(self, command, segment, index):
        """TODO have first if be push/pop not constant/pointer"""

        comment = '// {} {} {}'
        if command == _CommandType.C_POP:
            comment = comment.format('pop', segment, index)
        else:
            comment = comment.format('push', segment, index)
        self._temp_vm_instruction.append(comment)

        # new lambda helpers: a_to_d, sp_to_d, deref_to_d, d_to_sp, d_to_deref, inc_sp, dec_sp

        if segment == 'constant':
            if command == _CommandType.C_PUSH:
                self._temp_vm_instruction.append("@{}".format(index))
                self._temp_vm_instruction.append("D=A")
                self._temp_vm_instruction.append(
                    "@SP")
                self._temp_vm_instruction.append("A=M")
                self._temp_vm_instruction.append("M=D")

                self._temp_vm_instruction.append(
                    "@SP")
                self._temp_vm_instruction.append("M=M+1")

            # we never pop a var to a constant, so no else statement

        else:  # segment/index must be an address/pointer
            if command == _CommandType.C_PUSH:  # push (to some variable )
                self._temp_vm_instruction.append(
                    "@{}".format(self.default_bases[segment] + index))
                self._temp_vm_instruction.append("A=M")
                self._temp_vm_instruction.append("D=M")
                self._temp_vm_instruction.append(
                    "@SP")
                self._temp_vm_instruction.append("A=M")
                self._temp_vm_instruction.append("M=D")

                self._temp_vm_instruction.append(
                    "@SP")
                self._temp_vm_instruction.append("M=M+1")

            else:  # pop (to some variable)
                self._temp_vm_instruction.append(
                    "@SP")
                self._temp_vm_instruction.append("M=M-1")

                self._temp_vm_instruction.append(
                    "@SP")
                self._temp_vm_instruction.append("A=M")
                self._temp_vm_instruction.append("D=M")
                self._temp_vm_instruction.append(
                    "@{}".format(self.default_bases[segment] + index))
                self._temp_vm_instruction.append("M=D")

        self.assembly.append(self._temp_vm_instruction)
        self._temp_vm_instruction = []

    def close(self):
        self.assembly.append(["(END)", "@END", "0;JMP"])
        f = open(self.out_file, 'w')
        for vm_instruction in self.assembly:
            for asm_instruction in vm_instruction:
                f.write(asm_instruction + "\n")
        f.close()

        return 0

    def __del__(self):
        return self.close()


if __name__ == '__main__':
    # vm = VmTranslator(sys.argv[1], sys.argv[2])
    vm = VmTranslator("mod01/VmTranslator/StackTest.vm")
    vm.translate()
    vm.close()
