import json
import os

from mcp.server.fastmcp import FastMCP

# Khởi tạo MCP Server
mcp = FastMCP("Agent-Sync-Bridge")
DB_FILE = os.environ.get("DB_FILE", "")


def load_db():
    if not os.path.exists(DB_FILE):
        return {"api_requirements": [], "last_updated": ""}
    with open(DB_FILE, "r") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


@mcp.tool()
def add_api_requirement(endpoint: str, method: str, description: str):
    """Ghi lại yêu cầu API mới từ Agent FE."""
    db = load_db()
    db["api_requirements"].append(
        {
            "endpoint": endpoint,
            "method": method,
            "description": description,
            "status": "pending",
        }
    )
    save_db(db)
    return f"Đã ghi nhận yêu cầu API: {method} {endpoint}"


@mcp.tool()
def get_pending_requirements():
    """Lấy danh sách các API mà FE đang yêu cầu nhưng BE chưa làm."""
    db = load_db()
    pending = [req for req in db["api_requirements"] if req["status"] == "pending"]
    return json.dumps(pending) if pending else "Không có yêu cầu mới nào."


if __name__ == "__main__":
    mcp.run()
