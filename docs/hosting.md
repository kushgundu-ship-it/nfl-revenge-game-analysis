# Hosting the dashboard

Deploy on Streamlit Community Cloud with these settings:

- Repository: `kushgundu-ship-it/nfl-revenge-game-analysis`
- Branch: `main`
- Entrypoint: `dashboard/app.py`
- Python: `3.11` in Advanced settings

Dependencies are declared beside the entrypoint. The reviewed DuckDB snapshot
and Stage 4 validation report are included, so no data rebuild is needed.
The app checks CSV hashes and database counts at startup.

After deployment, open the public URL while signed out. Check Overview, Patterns,
Player explorer (including a baseline), and Methods & limits. Then add an
**Open dashboard** link near the top of the README.

No secrets are required. Keep raw downloads and credentials out of Git.
Review and commit the database, validation report, and CSVs together after
any deliberate rebuild of the analysis.
