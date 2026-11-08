# Humanizer quality review

The release gate is writing quality and factual fidelity, not an AI detector percentage.
The sample cases cover work, academic, resume, personal, email, and technical writing.

Run `python evaluation/evaluate_humanizer.py --live --limit 2 --output evaluation/review.json`
to call Gemini for two cases. Remove `--limit` only when the API quota and cost are acceptable.
The script never calls Gemini without `--live`. Keep review files local; they may contain
private writing. Do not commit user submissions.

For each output, have two people independently rate naturalness, voice match, and meaning
preservation from 1 (poor) to 5 (excellent), then record specific edits or lost facts.
Compare a new release against the previous one on the same cases without showing reviewers
which release produced which text. Expand the set with consented, anonymized user examples.
Track median rating, factual failures, document errors, completion time, and API failures.
Do not release a change that introduces factual errors or lowers human preference.
