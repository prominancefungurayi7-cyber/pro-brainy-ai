"""Optional, small live Gemini smoke check for the writing services."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.composition_service import generate_composition  # noqa: E402
from services.essay_service import generate_essay  # noqa: E402
from services.grammar_service import fix_grammar  # noqa: E402
from services.ppt_service import generate_presentation  # noqa: E402
from services.resume_service import build_resume  # noqa: E402
from services.summarizer_service import summarize_text  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Run one small live call for each writing service.')
    parser.add_argument('--live', action='store_true', help='Required to call Gemini.')
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to make Gemini API calls.')

    cases = (
        ('grammar', lambda: fix_grammar('We was late to the meeting.')),
        ('essay', lambda: generate_essay('Why rain matters for crops', 100, 'O level')),
        ('composition', lambda: generate_composition('A rainy school morning', 100, 'O level')),
        ('summarizer', lambda: summarize_text(
            'The town library extended its weekday hours from 5 pm to 7 pm. '
            'Staff said the change would help students after school. '
            'The weekend schedule did not change.', 'concise')),
        ('resume', lambda: build_resume(
            'Alex Moyo', 'Teaching Assistant', 'Two years supporting classroom activities',
            'Lesson planning, student support')),
        ('presentation', lambda: generate_presentation(
            'The water cycle', 'secondary school students', 3)),
    )
    failed = False
    for name, run in cases:
        try:
            result = run()
            if not isinstance(result, str) or not result.strip():
                raise ValueError('Empty result')
            print(f'{name}: OK ({len(result)} characters)', flush=True)
        except Exception as exc:
            failed = True
            print(f'{name}: ERROR {type(exc).__name__}: {str(exc)[:120]}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
