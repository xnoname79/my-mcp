```sh
pip install -r requirements.txt

# ─── sync-bridge (shared HTTP server) ───────────────────────────────
# One server handles ALL projects. DB auto-created per project at
# ~/.sync_bridge_db/<project>.db

# 1. Start the sync-bridge HTTP server (one time)
python3 /path/to/main.py

# 2. Connect from any Claude session (BE, FE, etc.)
claude mcp add --transport http sync-bridge http://localhost:8989/mcp

# That's it! Project is specified in each tool call, not in setup.
# One server, one port, unlimited projects.

# Optional env vars:
#   SYNC_HOST  — bind address (default: 0.0.0.0)
#   SYNC_PORT  — port (default: 8989)

# ─── issue-fetcher ──────────────────────────────────────────────────
# Refer to this link to create your own github_token https://github.com/settings/tokens
claude mcp add \
-e GITHUB_TOKEN=github_token \
-- issue-fetcher /path/to/python /path/to/github_issues.py

# ─── sync-docs ──────────────────────────────────────────────────────
cd dynamic-docs && npm install

claude mcp add \
-e DOCS_DB_FILE=/path/to/docs_db.json \
-e DOCS_PROJECT_DIR=/path/to/dynamic-docs \
-- sync-docs /path/to/python /path/to/docusaurus_docs.py
```
