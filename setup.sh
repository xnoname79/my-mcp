#!/bin/bash
set -e

REPO_URL="https://raw.githubusercontent.com/xnoname79/my-mcp/master/memory/sync-bridge/CLAUDE.md"
DEFAULT_SERVER="http://localhost:8989/mcp"
MCP_NAME="sync-bridge"

usage() {
    cat <<EOF
Usage: $(basename "$0") --project <name> [options]

Setup sync-bridge MCP for the current project directory.
Downloads CLAUDE.md rules and registers the MCP server.

Required:
  --project <name>    Project name in sync-bridge (e.g. "blog-app")

Optional:
  --tag <tag>         Tag for this app (e.g. "user-app", "admin-app")
  --server <url>      MCP server URL (default: $DEFAULT_SERVER)
  --name <name>       MCP registration name (default: $MCP_NAME)

Examples:
  $(basename "$0") --project blog-app
  $(basename "$0") --project blog-app --tag user-app
  $(basename "$0") --project blog-app --tag admin-app --server http://192.168.1.10:8989/mcp
EOF
    exit 1
}

PROJECT=""
TAG=""
SERVER="$DEFAULT_SERVER"
NAME="$MCP_NAME"

while [[ $# -gt 0 ]]; do
    case $1 in
        --project) PROJECT="$2"; shift 2 ;;
        --tag)     TAG="$2"; shift 2 ;;
        --server)  SERVER="$2"; shift 2 ;;
        --name)    NAME="$2"; shift 2 ;;
        -h|--help) usage ;;
        *)         echo "Unknown option: $1"; usage ;;
    esac
done

if [ -z "$PROJECT" ]; then
    echo "Error: --project is required"
    usage
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_CLAUDE_MD="$SCRIPT_DIR/memory/sync-bridge/CLAUDE.md"
TARGET_CLAUDE_MD="$(pwd)/CLAUDE.md"

echo "=== Sync-Bridge Setup ==="
echo "  Project:  $PROJECT"
echo "  Tag:      ${TAG:-"(none - sees all specs)"}"
echo "  Server:   $SERVER"
echo "  MCP Name: $NAME"
echo ""

# 1. Download/copy CLAUDE.md rules
echo "[1/3] Downloading sync-bridge rules..."
SYNC_RULES=""
if [ -f "$LOCAL_CLAUDE_MD" ]; then
    SYNC_RULES=$(cat "$LOCAL_CLAUDE_MD")
else
    SYNC_RULES=$(curl -sS "$REPO_URL")
    if [ $? -ne 0 ] || [ -z "$SYNC_RULES" ]; then
        echo "Error: Failed to download CLAUDE.md from $REPO_URL"
        exit 1
    fi
fi

# 2. Build project/tag config line
CONFIG_LINE="When using sync-bridge MCP, always use project=\"$PROJECT\""
if [ -n "$TAG" ]; then
    CONFIG_LINE="$CONFIG_LINE and tag=\"$TAG\""
fi
CONFIG_LINE="$CONFIG_LINE for all tool calls."

# 3. Append to CLAUDE.md
echo "[2/3] Updating CLAUDE.md..."
{
    if [ -f "$TARGET_CLAUDE_MD" ]; then
        echo ""
        echo "---"
        echo ""
    fi
    echo "$SYNC_RULES"
    echo ""
    echo "### Project Config"
    echo "$CONFIG_LINE"
} >> "$TARGET_CLAUDE_MD"
echo "  -> Updated: $TARGET_CLAUDE_MD"

# 4. Register MCP
echo "[3/3] Registering MCP server..."
claude mcp add --transport http "$NAME" "$SERVER" 2>/dev/null && \
    echo "  -> Registered: $NAME -> $SERVER" || \
    echo "  -> Note: claude CLI not found or already registered. Run manually:"
echo ""
echo "  claude mcp add --transport http $NAME $SERVER"
echo ""
echo "=== Setup complete! ==="
