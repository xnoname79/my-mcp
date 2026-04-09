import json
import os
from datetime import datetime

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


def backup_db():
    """Tạo file backup .bak trước khi reset."""
    if not os.path.exists(DB_FILE):
        return ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = f"{DB_FILE}.{timestamp}.bak"
    with open(DB_FILE, "r") as src, open(bak_path, "w") as dst:
        dst.write(src.read())
    return bak_path


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


@mcp.tool()
def list_api_requirements():
    """Lấy toàn bộ danh sách API specs hiện có trong DB."""
    db = load_db()
    reqs = db["api_requirements"]
    if not reqs:
        return "DB hiện đang trống."
    result = []
    for i, req in enumerate(reqs):
        result.append({"index": i, **req})
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def update_api_requirement(
    index: int,
    endpoint: str = "",
    method: str = "",
    description: str = "",
    status: str = "",
):
    """Chỉnh sửa một API spec có sẵn theo index.

    Args:
        index: Vị trí của API spec trong danh sách (lấy từ list_api_requirements)
        endpoint: Endpoint mới (để trống nếu không đổi)
        method: Method mới (để trống nếu không đổi)
        description: Mô tả mới (để trống nếu không đổi)
        status: Trạng thái mới (để trống nếu không đổi)
    """
    db = load_db()
    reqs = db["api_requirements"]
    if index < 0 or index >= len(reqs):
        return f"Lỗi: index {index} không hợp lệ. DB có {len(reqs)} specs (0-{len(reqs) - 1})."

    if endpoint:
        reqs[index]["endpoint"] = endpoint
    if method:
        reqs[index]["method"] = method
    if description:
        reqs[index]["description"] = description
    if status:
        reqs[index]["status"] = status

    save_db(db)
    return f"Đã cập nhật API spec #{index}: {reqs[index]['method']} {reqs[index]['endpoint']}"


@mcp.tool()
def reset_api_requirements():
    """Xóa toàn bộ API specs trong DB để bắt đầu mới. Tự động backup trước khi reset."""
    bak = backup_db()
    db = load_db()
    db["api_requirements"] = []
    db["last_updated"] = ""
    save_db(db)
    return f"Đã xóa toàn bộ API specs. DB đã được reset. Backup: {bak}"


if __name__ == "__main__":
    mcp.run()
