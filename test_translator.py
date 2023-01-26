import unittest

from vm_translator import VmTranslator


class TestVmTranslator(unittest.TestCase):

    # def test_file_open(self):
    #     VmTranslator('SimpleAdd.vm', 'out.asm')

    def test_mutating_through_state(self):
        vm = VmTranslator(
            in_file='SimpleAdd.vm', out_file='out.asm')

        while vm.parser.has_more_lines():
            vm.parser.advance()
            print(vm.parser._current_raw_instruction)
            print(vm.parser.command_type())
            print(vm.parser.arg1())
            print(vm.parser.arg2())
            print()


if __name__ == '__main__':
    unittest.main()
