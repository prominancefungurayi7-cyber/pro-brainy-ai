import unittest

from services.level_service import build_level_instruction, normalize_education_level


class LevelInstructionTests(unittest.TestCase):
    def test_normalize_education_level_handles_supported_values(self):
        self.assertEqual(normalize_education_level('O level'), 'O level')
        self.assertEqual(normalize_education_level('A level'), 'A level')
        self.assertEqual(normalize_education_level('tertiary education'), 'Tertiary education')
        self.assertEqual(normalize_education_level('Primary school'), 'Primary school')

    def test_normalize_education_level_defaults_to_primary_school(self):
        self.assertEqual(normalize_education_level('unknown'), 'Primary school')

    def test_build_level_instruction_includes_school_specific_guidance(self):
        instruction = build_level_instruction('Primary school')
        lowered = instruction.lower()
        self.assertIn('simple vocabulary', lowered)
        self.assertIn('short sentences', lowered)

    def test_normalize_education_level_accepts_synonyms(self):
        self.assertEqual(normalize_education_level('tertiary'), 'Tertiary education')
        self.assertEqual(normalize_education_level('o-level'), 'O level')

    def test_build_level_instruction_includes_o_level_guidance(self):
        instruction = build_level_instruction('O level')
        lowered = instruction.lower()
        self.assertIn('structured paragraphs', lowered)
        self.assertIn('exam', lowered)

    def test_build_level_instruction_includes_tertiary_guidance(self):
        instruction = build_level_instruction('tertiary education')
        lowered = instruction.lower()
        self.assertIn('academic', lowered)
        self.assertIn('depth', lowered)


if __name__ == '__main__':
    unittest.main()
