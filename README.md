# Pro Brainy AI

## Local development

Create `.env` from `.env.example` and set `GEMINI_API_KEY` to your Google Gemini API key. Set `SECRET_KEY` to a long random value for local use. Install dependencies with `pip install -r requirements.txt`, then run `python app.py`.

## GitHub CI and Render deployment

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the tests for pushes and pull requests to `main`. The root `render.yaml` defines the web service and a Render Postgres database. Render deploys a new commit only after its GitHub checks pass.

1. Push this repository to GitHub with `.env` excluded. Never commit API keys or database credentials.
2. In Render, connect your GitHub account and create a new **Blueprint** from this repository's `main` branch. Use the root `render.yaml` file.
3. When Render asks for `GEMINI_API_KEY`, paste the API key into Render's secret field. Render generates `SECRET_KEY` and connects `DATABASE_URL` to its Postgres instance automatically.
4. After the deployment succeeds, open the service URL and verify `/health` returns `{"status":"ok"}`. Check the GitHub Actions result on the deployed commit.

The Blueprint uses Render's free Postgres plan. Render currently expires free Postgres databases after 30 days; upgrade the database plan before expiration if you need to retain user accounts and other stored data. The web service's local filesystem is temporary, so SQLite is not suitable for deployed user data.

This repository previously tracked `.env`. Removing it from current tracking does not remove secrets from earlier Git commits. Rotate any API keys or Flask secret that were committed previously.
