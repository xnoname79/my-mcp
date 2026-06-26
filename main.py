import json
import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

import anyio
from starlette.requests import Request
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

DB_FILE = os.environ.get("DB_FILE", "")
SYNC_HOST = os.environ.get("SYNC_HOST", "0.0.0.0")
SYNC_PORT = int(os.environ.get("SYNC_PORT", "8989"))

_db_lock = asyncio.Lock()
_change_event = anyio.Event()


def _signal_change():
    """Set the current event and replace it with a new one for the next wait cycle."""
    global _change_event
    _change_event.set()
    _change_event = anyio.Event()


def load_db():
    if not os.path.exists(DB_FILE):
        return {"api_requirements": [], "last_updated": "", "change_log": []}
    with open(DB_FILE, "r") as f:
        data = json.load(f)
    if "change_log" not in data:
        data["change_log"] = []
    return data


def save_db(data, log_entry=None):
    data["last_updated"] = datetime.now().isoformat()
    if log_entry:
        data["change_log"].append(
            {"timestamp": data["last_updated"], **log_entry}
        )
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    _signal_change()


def backup_db():
    if not os.path.exists(DB_FILE):
        return ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = f"{DB_FILE}.{timestamp}.bak"
    with open(DB_FILE, "r") as src, open(bak_path, "w") as dst:
        dst.write(src.read())
    return bak_path


@asynccontextmanager
async def lifespan(server):
    yield {}


mcp = FastMCP(
    "Agent-Sync-Bridge",
    lifespan=lifespan,
    host=SYNC_HOST,
    port=SYNC_PORT,
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return JSONResponse({"status": "ok", "server": "Agent-Sync-Bridge"})


# ─── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def add_api_requirement(endpoint: str, method: str, description: str):
    """Ghi lại yêu cầu API mới từ Agent FE hoặc BE."""
    async with _db_lock:
        db = load_db()
        req = {
            "endpoint": endpoint,
            "method": method,
            "description": description,
            "status": "pending",
        }
        db["api_requirements"].append(req)
        save_db(db, log_entry={
            "action": "add",
            "detail": f"Added {method} {endpoint}",
            "requirement": req,
        })
    return f"Đã ghi nhận yêu cầu API: {method} {endpoint}"


@mcp.tool()
async def get_pending_requirements(status: str = ""):
    """Lấy danh sách các API specs đang hoạt động (chưa done).

    Args:
        status: Lọc theo trạng thái cụ thể (vd: "pending", "discuss", "confirm").
                Để trống = trả về tất cả specs chưa done.
    """
    db = load_db()
    if status:
        filtered = [req for req in db["api_requirements"] if req["status"] == status]
    else:
        filtered = [req for req in db["api_requirements"] if req["status"] != "done"]
    if not filtered:
        msg = f"Không có specs nào với status '{status}'." if status else "Không có specs nào đang hoạt động."
        return msg
    result = [{"index": i, **req} for i, req in enumerate(db["api_requirements"]) if req in filtered]
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def list_api_requirements():
    """Lấy toàn bộ danh sách API specs hiện có trong DB."""
    db = load_db()
    reqs = db["api_requirements"]
    if not reqs:
        return "DB hiện đang trống."
    result = [{"index": i, **req} for i, req in enumerate(reqs)]
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def update_api_requirement(
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
    async with _db_lock:
        db = load_db()
        reqs = db["api_requirements"]
        if index < 0 or index >= len(reqs):
            return f"Lỗi: index {index} không hợp lệ. DB có {len(reqs)} specs (0-{len(reqs) - 1})."

        changes = []
        if endpoint:
            reqs[index]["endpoint"] = endpoint
            changes.append(f"endpoint={endpoint}")
        if method:
            reqs[index]["method"] = method
            changes.append(f"method={method}")
        if description:
            reqs[index]["description"] = description
            changes.append("description updated")
        if status:
            reqs[index]["status"] = status
            changes.append(f"status={status}")

        save_db(db, log_entry={
            "action": "update",
            "detail": f"Updated #{index} {reqs[index]['method']} {reqs[index]['endpoint']}: {', '.join(changes)}",
            "requirement": reqs[index],
        })
    return f"Đã cập nhật API spec #{index}: {reqs[index]['method']} {reqs[index]['endpoint']}"


@mcp.tool()
async def reset_api_requirements():
    """Xóa toàn bộ API specs trong DB để bắt đầu mới. Tự động backup trước khi reset."""
    async with _db_lock:
        bak = backup_db()
        db = load_db()
        count = len(db["api_requirements"])
        db["api_requirements"] = []
        save_db(db, log_entry={
            "action": "reset",
            "detail": f"Reset DB ({count} specs cleared). Backup: {bak}",
        })
    return f"Đã xóa toàn bộ API specs. DB đã được reset. Backup: {bak}"


@mcp.tool()
async def watch_for_changes(since: str = "", timeout: int = 30):
    """Chờ đợi thay đổi mới từ phía đối tác (BE hoặc FE). Tool sẽ block cho đến khi
    có thay đổi mới hoặc hết timeout.

    Args:
        since: ISO timestamp - chỉ trả về changes sau thời điểm này. Để trống = lấy tất cả.
        timeout: Số giây tối đa chờ thay đổi (mặc định 30, tối đa 120).
    """
    timeout = max(1, min(timeout, 120))

    db = load_db()
    changes = db.get("change_log", [])
    if since:
        changes = [c for c in changes if c["timestamp"] > since]

    if changes:
        return json.dumps(changes, ensure_ascii=False)

    current_event = _change_event
    try:
        with anyio.fail_after(timeout):
            await current_event.wait()
    except TimeoutError:
        return json.dumps({"status": "timeout", "message": f"Không có thay đổi nào trong {timeout}s."})

    db = load_db()
    changes = db.get("change_log", [])
    if since:
        changes = [c for c in changes if c["timestamp"] > since]
    return json.dumps(changes, ensure_ascii=False) if changes else json.dumps({"status": "no_changes"})


@mcp.tool()
async def get_change_log(limit: int = 20):
    """Lấy lịch sử thay đổi gần nhất.

    Args:
        limit: Số lượng entries tối đa trả về (mặc định 20).
    """
    db = load_db()
    changes = db.get("change_log", [])
    recent = changes[-limit:] if limit > 0 else changes
    if not recent:
        return "Chưa có thay đổi nào."
    return json.dumps(recent, ensure_ascii=False)


# ─── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("sync-bridge://requirements")
def requirements_resource():
    """Toàn bộ API requirements hiện tại."""
    db = load_db()
    return json.dumps(db["api_requirements"], indent=2, ensure_ascii=False)


@mcp.resource("sync-bridge://changelog")
def changelog_resource():
    """50 thay đổi gần nhất."""
    db = load_db()
    return json.dumps(db.get("change_log", [])[-50:], indent=2, ensure_ascii=False)


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
