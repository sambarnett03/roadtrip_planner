# Cleaned Roadmap Planner (minimal)

This repository is a **cleaned, minimal** version derived from the uploaded project `firebase_map`.
I removed large editor history, secrets, and other noisy files, and produced a minimal, well-structured
Flask application that:

- Does **not** contain Firebase service-account JSON credentials.
- Loads Firebase Admin SDK from the path specified in the environment variable `FIREBASE_CREDENTIALS`.
- Uses `FLASK_SECRET_KEY` or a default dev key (set in production).
- Contains minimal templates and routes to demonstrate how to build on this.

## What I removed
- `.history/` (many backup files).
- `roadmap-planner-...firebase-adminsdk-*.json` (sensitive credentials).
- Other large / unused files.

## How to run
1. Create a Python virtualenv and install requirements:
   ```bash
   python -m venv env
   source env/bin/activate
   pip install -r requirements.txt
   ```
2. Place your Firebase Admin SDK JSON somewhere safe and set:
   ```bash
   export FIREBASE_CREDENTIALS="/full/path/to/your-service-account.json"
   export FLASK_SECRET_KEY="replace-with-secure-secret"
   ```
   or edit `.env.example` to create a `.env` for local development.
3. Run:
   ```bash
   python app.py
   ```
4. Visit http://127.0.0.1:5000

## Recommended next refactors (I can do these on request)
- Split into a package (app/ with blueprints `auth`, `roadmaps`, `maps`).
- Add proper authentication using Firebase Authentication (client + server verification).
- Add unit tests and CI.
- Reintroduce only the templates and assets you actually need from the original repo.

