import json
import os
import subprocess
import signal
from datetime import datetime

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Docusaurus-Docs")
DB_FILE = os.environ.get("DOCS_DB_FILE", "")
DOCS_PROJECT_DIR = os.environ.get("DOCS_PROJECT_DIR", "")
_serve_process = None


def load_db():
    if not os.path.exists(DB_FILE):
        return {"docs": [], "sidebar": [], "site_config": {}, "last_updated": ""}
    with open(DB_FILE, "r") as f:
        return json.load(f)


def save_db(data):
    data["last_updated"] = datetime.now().isoformat()
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# --------------- Document CRUD ---------------


@mcp.tool()
def create_doc(
    slug: str,
    title: str,
    content: str,
    category: str = "",
    sidebar_position: int = 0,
    tags: str = "",
    description: str = "",
):
    """Tạo một trang documentation mới.

    Args:
        slug: Đường dẫn URL của trang, ví dụ "getting-started" hoặc "api/authentication"
        title: Tiêu đề trang
        content: Nội dung Markdown của trang
        category: Danh mục (folder), ví dụ "guides", "api-reference"
        sidebar_position: Vị trí trong sidebar (số nhỏ = lên trước)
        tags: Tags phân cách bằng dấu phẩy, ví dụ "setup,beginner"
        description: Mô tả ngắn cho SEO/meta
    """
    db = load_db()

    # Check duplicate slug
    for doc in db["docs"]:
        if doc["slug"] == slug:
            return f"Lỗi: slug '{slug}' đã tồn tại. Dùng update_doc để chỉnh sửa."

    doc = {
        "slug": slug,
        "title": title,
        "content": content,
        "category": category,
        "sidebar_position": sidebar_position,
        "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
        "description": description,
        "status": "draft",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    db["docs"].append(doc)
    save_db(db)
    return f"Đã tạo doc: '{title}' ({slug})"


@mcp.tool()
def update_doc(
    slug: str,
    title: str = "",
    content: str = "",
    category: str = "",
    sidebar_position: int = -1,
    tags: str = "",
    description: str = "",
    status: str = "",
):
    """Cập nhật một trang documentation theo slug.

    Args:
        slug: Slug của trang cần cập nhật
        title: Tiêu đề mới (để trống = không đổi)
        content: Nội dung mới (để trống = không đổi)
        category: Danh mục mới (để trống = không đổi)
        sidebar_position: Vị trí mới (-1 = không đổi)
        tags: Tags mới, phân cách bằng dấu phẩy (để trống = không đổi)
        description: Mô tả mới (để trống = không đổi)
        status: Trạng thái mới: "draft", "published", "archived" (để trống = không đổi)
    """
    db = load_db()

    for doc in db["docs"]:
        if doc["slug"] == slug:
            if title:
                doc["title"] = title
            if content:
                doc["content"] = content
            if category:
                doc["category"] = category
            if sidebar_position >= 0:
                doc["sidebar_position"] = sidebar_position
            if tags:
                doc["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
            if description:
                doc["description"] = description
            if status:
                doc["status"] = status
            doc["updated_at"] = datetime.now().isoformat()
            save_db(db)
            return f"Đã cập nhật doc: '{doc['title']}' ({slug})"

    return f"Lỗi: không tìm thấy doc với slug '{slug}'."


@mcp.tool()
def get_doc(slug: str):
    """Lấy chi tiết một trang documentation theo slug.

    Args:
        slug: Slug của trang cần xem
    """
    db = load_db()
    for doc in db["docs"]:
        if doc["slug"] == slug:
            return json.dumps(doc, ensure_ascii=False)
    return f"Không tìm thấy doc với slug '{slug}'."


@mcp.tool()
def list_docs(category: str = "", status: str = ""):
    """Lấy danh sách tất cả docs, có thể lọc theo category hoặc status.

    Args:
        category: Lọc theo danh mục (để trống = tất cả)
        status: Lọc theo trạng thái: "draft", "published", "archived" (để trống = tất cả)
    """
    db = load_db()
    docs = db["docs"]

    if category:
        docs = [d for d in docs if d.get("category") == category]
    if status:
        docs = [d for d in docs if d.get("status") == status]

    if not docs:
        return "Không có docs nào."

    result = []
    for d in docs:
        result.append({
            "slug": d["slug"],
            "title": d["title"],
            "category": d.get("category", ""),
            "status": d.get("status", "draft"),
            "sidebar_position": d.get("sidebar_position", 0),
            "tags": d.get("tags", []),
            "updated_at": d.get("updated_at", ""),
        })
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def delete_doc(slug: str):
    """Xóa một trang documentation theo slug.

    Args:
        slug: Slug của trang cần xóa
    """
    db = load_db()
    original_len = len(db["docs"])
    db["docs"] = [d for d in db["docs"] if d["slug"] != slug]

    if len(db["docs"]) == original_len:
        return f"Không tìm thấy doc với slug '{slug}'."

    save_db(db)
    return f"Đã xóa doc: {slug}"


@mcp.tool()
def search_docs(query: str):
    """Tìm kiếm docs theo từ khóa trong title, content, tags.

    Args:
        query: Từ khóa tìm kiếm
    """
    db = load_db()
    query_lower = query.lower()
    results = []

    for doc in db["docs"]:
        if (
            query_lower in doc["title"].lower()
            or query_lower in doc.get("content", "").lower()
            or query_lower in doc.get("description", "").lower()
            or any(query_lower in t.lower() for t in doc.get("tags", []))
        ):
            results.append({
                "slug": doc["slug"],
                "title": doc["title"],
                "category": doc.get("category", ""),
                "status": doc.get("status", "draft"),
                "tags": doc.get("tags", []),
            })

    return json.dumps(results, ensure_ascii=False) if results else "Không tìm thấy kết quả."


# --------------- Sidebar Management ---------------


@mcp.tool()
def update_sidebar(sidebar_items: str):
    """Cập nhật cấu trúc sidebar cho Docusaurus.

    Args:
        sidebar_items: JSON string mô tả cấu trúc sidebar, ví dụ:
            [{"type": "category", "label": "Guides", "items": ["getting-started", "installation"]},
             {"type": "doc", "id": "faq"}]
    """
    db = load_db()
    try:
        items = json.loads(sidebar_items)
    except json.JSONDecodeError:
        return "Lỗi: sidebar_items không phải JSON hợp lệ."

    db["sidebar"] = items
    save_db(db)
    return f"Đã cập nhật sidebar với {len(items)} mục."


@mcp.tool()
def get_sidebar():
    """Lấy cấu trúc sidebar hiện tại."""
    db = load_db()
    sidebar = db.get("sidebar", [])
    if not sidebar:
        return "Sidebar chưa được cấu hình."
    return json.dumps(sidebar, ensure_ascii=False)


@mcp.tool()
def auto_generate_sidebar():
    """Tự động tạo sidebar từ danh sách docs hiện có, nhóm theo category."""
    db = load_db()
    docs = [d for d in db["docs"] if d.get("status") != "archived"]

    if not docs:
        return "Không có docs nào để tạo sidebar."

    # Group by category
    categories = {}
    uncategorized = []
    for doc in docs:
        cat = doc.get("category", "")
        if cat:
            categories.setdefault(cat, []).append(doc)
        else:
            uncategorized.append(doc)

    sidebar = []

    # Add categorized docs
    for cat_name in sorted(categories.keys()):
        cat_docs = sorted(categories[cat_name], key=lambda d: d.get("sidebar_position", 0))
        sidebar.append({
            "type": "category",
            "label": cat_name.replace("-", " ").title(),
            "items": [d["slug"] for d in cat_docs],
        })

    # Add uncategorized docs
    for doc in sorted(uncategorized, key=lambda d: d.get("sidebar_position", 0)):
        sidebar.append({"type": "doc", "id": doc["slug"]})

    db["sidebar"] = sidebar
    save_db(db)
    return json.dumps(sidebar, ensure_ascii=False)


# --------------- Bulk & Reset ---------------


@mcp.tool()
def set_site_config(
    title: str = "",
    tagline: str = "",
    url: str = "",
    organization_name: str = "",
    project_name: str = "",
    copyright: str = "",
    footer_links: str = "",
):
    """Cấu hình thông tin site cho Docusaurus (title, tagline, url...).

    Args:
        title: Tên hiển thị của site
        tagline: Mô tả ngắn
        url: URL production
        organization_name: Tên tổ chức
        project_name: Tên project
        copyright: Nội dung copyright ở footer
        footer_links: JSON string array các link group cho footer, ví dụ:
            [{"title": "Docs", "items": [{"label": "Intro", "to": "/docs/intro"}]}]
    """
    db = load_db()
    cfg = db.get("site_config", {})

    if title:
        cfg["title"] = title
    if tagline:
        cfg["tagline"] = tagline
    if url:
        cfg["url"] = url
    if organization_name:
        cfg["organizationName"] = organization_name
    if project_name:
        cfg["projectName"] = project_name
    if copyright:
        cfg["copyright"] = copyright
    if footer_links:
        try:
            cfg["footerLinks"] = json.loads(footer_links)
        except json.JSONDecodeError:
            return "Lỗi: footer_links không phải JSON hợp lệ."

    db["site_config"] = cfg
    save_db(db)
    return json.dumps({"message": "Đã cập nhật site config", "config": cfg}, ensure_ascii=False)


@mcp.tool()
def get_site_config():
    """Lấy cấu hình site hiện tại."""
    db = load_db()
    cfg = db.get("site_config", {})
    if not cfg:
        return "Site config chưa được cấu hình. Dùng set_site_config để thiết lập."
    return json.dumps(cfg, ensure_ascii=False)


@mcp.tool()
def reset_docs():
    """Xóa toàn bộ docs, sidebar và site config để bắt đầu mới."""
    db = {"docs": [], "sidebar": [], "site_config": {}, "last_updated": ""}
    save_db(db)
    return "Đã reset toàn bộ docs, sidebar và site config."


@mcp.tool()
def get_docs_stats():
    """Lấy thống kê tổng quan về documentation."""
    db = load_db()
    docs = db["docs"]
    total = len(docs)

    if total == 0:
        return "DB trống, chưa có docs nào."

    by_status = {}
    by_category = {}
    for d in docs:
        st = d.get("status", "draft")
        by_status[st] = by_status.get(st, 0) + 1
        cat = d.get("category", "(uncategorized)")
        by_category[cat] = by_category.get(cat, 0) + 1

    return json.dumps({
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "last_updated": db.get("last_updated", ""),
    }, ensure_ascii=False)


# --------------- Build & Serve ---------------


@mcp.tool()
def build_docs():
    """Build markdown files + sidebars.js từ DB vào Docusaurus project.

    Yêu cầu env var DOCS_PROJECT_DIR trỏ tới thư mục Docusaurus project.
    Sẽ tạo các file .md trong docs/ và cập nhật sidebars.js.
    """
    if not DOCS_PROJECT_DIR:
        return "Lỗi: DOCS_PROJECT_DIR chưa được set."
    if not os.path.isdir(DOCS_PROJECT_DIR):
        return f"Lỗi: thư mục '{DOCS_PROJECT_DIR}' không tồn tại."

    db = load_db()
    docs = db["docs"]
    if not docs:
        return "Không có docs nào để build."

    docs_dir = os.path.join(DOCS_PROJECT_DIR, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    built = []
    for doc in docs:
        if doc.get("status") == "archived":
            continue

        # Build frontmatter
        frontmatter = {
            "title": doc["title"],
            "sidebar_position": doc.get("sidebar_position", 0),
        }
        if doc.get("description"):
            frontmatter["description"] = doc["description"]
        if doc.get("tags"):
            frontmatter["tags"] = doc["tags"]

        fm_lines = ["---"]
        for k, v in frontmatter.items():
            if isinstance(v, list):
                fm_lines.append(f"{k}:")
                for item in v:
                    fm_lines.append(f"  - {item}")
            else:
                fm_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        fm_lines.append("---")
        fm_str = "\n".join(fm_lines)

        content = f"{fm_str}\n\n{doc.get('content', '')}\n"

        # Write to file — handle category as subdirectory
        if doc.get("category"):
            cat_dir = os.path.join(docs_dir, doc["category"])
            os.makedirs(cat_dir, exist_ok=True)
            slug_name = doc["slug"].split("/")[-1] if "/" in doc["slug"] else doc["slug"]
            file_path = os.path.join(cat_dir, f"{slug_name}.md")
        else:
            file_path = os.path.join(docs_dir, f"{doc['slug']}.md")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        built.append(file_path)

    # Build sidebars.js
    sidebar = db.get("sidebar", [])
    if not sidebar:
        # Auto-generate if not configured
        auto_generate_sidebar()
        db = load_db()
        sidebar = db.get("sidebar", [])

    if sidebar:
        sidebars_content = (
            "// Auto-generated by Docusaurus-Docs MCP\n"
            "/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */\n"
            f"const sidebars = {{\n  docs: {json.dumps(sidebar, indent=4, ensure_ascii=False)}\n}};\n\n"
            "module.exports = sidebars;\n"
        )
        sidebars_path = os.path.join(DOCS_PROJECT_DIR, "sidebars.js")
        with open(sidebars_path, "w", encoding="utf-8") as f:
            f.write(sidebars_content)

    # Build site-config.json (dynamic config for docusaurus.config.js)
    site_config = db.get("site_config", {})
    config_path = os.path.join(DOCS_PROJECT_DIR, "site-config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(site_config, f, indent=2, ensure_ascii=False)

    return json.dumps({
        "message": f"Đã build {len(built)} docs vào {docs_dir}",
        "files": built,
        "site_config": config_path,
    }, ensure_ascii=False)


def _kill_port(port):
    """Kill any process occupying the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = result.stdout.strip().split("\n")
        for pid in pids:
            if pid.strip():
                os.kill(int(pid.strip()), signal.SIGTERM)
    except Exception:
        pass


@mcp.tool()
def serve_docs(port: int = 30031):
    """Chạy Docusaurus dev server. Tự động kill process cũ nếu port đang bị chiếm.

    Args:
        port: Port để chạy server, mặc định 30031
    """
    global _serve_process

    if not DOCS_PROJECT_DIR:
        return "Lỗi: DOCS_PROJECT_DIR chưa được set."
    if not os.path.isdir(DOCS_PROJECT_DIR):
        return f"Lỗi: thư mục '{DOCS_PROJECT_DIR}' không tồn tại."

    # Stop existing server tracked by this process
    if _serve_process and _serve_process.poll() is None:
        _serve_process.terminate()
        try:
            _serve_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _serve_process.kill()

    # Kill any process occupying the port (from previous runs, other MCP instances, etc.)
    _kill_port(port)

    # Check if node_modules exists
    node_modules = os.path.join(DOCS_PROJECT_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        return (
            f"Lỗi: node_modules chưa được cài. "
            f"Chạy 'cd {DOCS_PROJECT_DIR} && npm install' trước."
        )

    _serve_process = subprocess.Popen(
        ["npx", "docusaurus", "start", "--port", str(port), "--no-open"],
        cwd=DOCS_PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return json.dumps({
        "message": "Docusaurus dev server đang chạy",
        "url": f"http://localhost:{port}",
        "port": port,
        "pid": _serve_process.pid,
    }, ensure_ascii=False)


@mcp.tool()
def stop_docs_server():
    """Dừng Docusaurus dev server nếu đang chạy."""
    global _serve_process

    if _serve_process and _serve_process.poll() is None:
        _serve_process.terminate()
        try:
            _serve_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _serve_process.kill()
        _serve_process = None
        return "Đã dừng Docusaurus dev server."

    _serve_process = None
    return "Không có server nào đang chạy."


@mcp.tool()
def docs_server_status():
    """Kiểm tra trạng thái Docusaurus dev server."""
    if _serve_process and _serve_process.poll() is None:
        return json.dumps({
            "status": "running",
            "pid": _serve_process.pid,
        })
    return json.dumps({"status": "stopped"})


if __name__ == "__main__":
    mcp.run()
