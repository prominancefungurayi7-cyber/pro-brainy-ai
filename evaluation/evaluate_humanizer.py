"""Run a small, explicit live quality review; no API calls without --live."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.humanizer_service import _anchors, humanize_text  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Evaluate humanizer examples for a human review.')
    parser.add_argument('--live', action='store_true', help='Call Gemini for each case.')
    parser.add_argument('--limit', type=int, default=0, help='Maximum cases to run; 0 means all.')
    parser.add_argument('--output', type=Path, default=ROOT / 'evaluation' / 'review.json')
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to make Gemini API calls. The script makes no calls by default.')
    cases = json.loads((ROOT / 'evaluation' / 'humanizer_cases.json').read_text(encoding='utf-8'))
    selected = cases[:args.limit] if args.limit else cases
    report = []
    for case in selected:
        try:
            rewrite = humanize_text(case['source'], case.get('voice_sample'))
            report.append({
                'id': case['id'], 'domain': case['domain'], 'source': case['source'],
                'rewrite': rewrite, 'facts_preserved': _anchors(case['source']) == _anchors(rewrite),
                'human_review': {'naturalness_1_to_5': None, 'voice_match_1_to_5': None,
                                 'meaning_preserved_1_to_5': None, 'notes': ''},
            })
        except Exception as exc:
            report.append({'id': case['id'], 'error': str(exc)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(report)} cases to {args.output}')


if __name__ == '__main__':
    main()
