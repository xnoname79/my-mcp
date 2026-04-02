```sh
pip install -r requirements.txt

# Run sync-bridge
# Run both for sources that need to share the context
claude mcp add -e DB_FILE=/path/to/db_file.json -- sync-bridge /path/to/python /path/to/main.py

# Run issue-fetcher
# Refer to this link to create your own github_token https://github.com/settings/tokens
claude mcp add -e GITHUB_TOKEN=github_token -- issue-fetcher /path/to/python /path/to/github_issues.py

# Run sync-docs
cd dynamic-docs && npm install

claude mcp add -e DOCS_DB_FILE=/path/to/docs_db.json -e DOCS_PROJECT_DIR=/path/to/dynamic-docs -- sync-docs /path/to/python /path/to/docusaurus_docs.py
```
