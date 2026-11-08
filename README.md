# Pro Brainy AI

## Local development

Create `.env` from `.env.example` and set `GEMINI_API_KEY` to your Google Gemini API key. Set `SECRET_KEY` to a long random value for local use. Install dependencies with `pip install -r requirements.txt`, then run `python app.py`.

## Accounts and tools

Visitors must register and log in before using any AI tool. Forms use CSRF tokens. New accounts require a password of at least 12 characters. Login attempts are throttled by account and request source. Registration uses a signed browser token and request rate limits; the same normalized username cannot be registered twice from one browser token, and a browser token can create at most three accounts. Reused names across browsers are recorded as a review signal without automatically blocking legitimate users. These are abuse signals, not proof of identity: clearing browser data or changing devices can bypass them, and legitimate people can share a device or name. The free account limit is 30 tool requests per 24 hours, with a burst limit of five per minute; set `FREE_TOOL_DAILY_LIMIT` to change the daily limit.

The humanizer accepts pasted text, `.txt`, `.pdf`, and `.docx` uploads. A `.docx` upload shows progress based on completed body paragraphs and downloads the edited `.docx` when it reaches 100%. The ordinary form submission still works without JavaScript. Body paragraphs, including table cells, are rewritten in document order; styled headings, titles, and short all-bold headings are left unchanged. Paragraph and table structure is preserved. Complex Word fields, hyperlinks, tracked changes, and text outside the main document body are left unchanged to avoid corrupting the file. Inline character formatting within rewritten paragraphs can shift because the AI rewrites whole paragraphs.

## GitHub CI and Render deployment

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the tests for pushes and pull requests to `main`. The root `render.yaml` defines a web service that uses SQLite. Render deploys a new commit only after its GitHub checks pass.

1. Push this repository to GitHub with `.env` excluded. Never commit API keys or database credentials.
2. In Render, connect your GitHub account and create a new **Blueprint** from this repository's `main` branch. Use the root `render.yaml` file.
3. When Render asks for `GEMINI_API_KEY`, paste the API key into Render's secret field. Render generates `SECRET_KEY`. The deployed app uses SQLite through `DATABASE_URL`.
4. After the deployment succeeds, open the service URL and verify `/health` returns `{"status":"ok"}`. Check the GitHub Actions result on the deployed commit.

The deployment uses SQLite only. **SQLite data on Render's free web service disappears on every restart or redeploy**, so users may need to register again. Signup limits, login throttles, and tool usage counters also reset. To retain accounts and enforce paid entitlements reliably, use a durable database or a paid Render service with a persistent disk before charging users. Add verified email ownership, a payment provider with server-side webhook verification, and an account recovery process before a paid launch. Device and name checks alone cannot prevent fraud. Switching to Postgres later requires a data migration; it does not happen automatically.

This repository previously tracked `.env` and SQLite database files. Removing them from current tracking does not remove secrets or data from earlier Git commits. Rotate any API keys or Flask secret that were committed previously, and review historical database contents before public release.
