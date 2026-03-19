import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("GitHub-Issues")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"


def _github_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


@mcp.tool()
def list_github_issues(
    owner: str,
    repo: str,
    state: str = "open",
    labels: str = "",
    per_page: int = 30,
    page: int = 1,
):
    """Lấy danh sách issues từ một GitHub repo (hỗ trợ private repo qua GITHUB_TOKEN).

    Args:
        owner: Chủ sở hữu repo (user hoặc org), ví dụ "octocat"
        repo: Tên repo, ví dụ "Hello-World"
        state: Trạng thái issue: "open", "closed", hoặc "all"
        labels: Lọc theo labels, phân cách bằng dấu phẩy, ví dụ "bug,enhancement"
        per_page: Số issues trên mỗi trang (tối đa 100)
        page: Số trang
    """
    params = {"state": state, "per_page": min(per_page, 100), "page": page}
    if labels:
        params["labels"] = labels

    resp = httpx.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues",
        headers=_github_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()

    issues = []
    for item in resp.json():
        # GitHub API trả cả pull requests trong /issues, lọc bỏ
        if "pull_request" in item:
            continue
        issues.append(
            {
                "number": item["number"],
                "title": item["title"],
                "state": item["state"],
                "labels": [l["name"] for l in item.get("labels", [])],
                "assignees": [a["login"] for a in item.get("assignees", [])],
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
                "url": item["html_url"],
            }
        )
    return issues if issues else "Không tìm thấy issue nào."


@mcp.tool()
def get_github_issue(owner: str, repo: str, issue_number: int):
    """Lấy chi tiết một issue cụ thể, bao gồm cả comments.

    Args:
        owner: Chủ sở hữu repo (user hoặc org)
        repo: Tên repo
        issue_number: Số issue
    """
    # Lấy issue detail
    resp = httpx.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}",
        headers=_github_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    item = resp.json()

    # Lấy comments
    comments_resp = httpx.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments",
        headers=_github_headers(),
        params={"per_page": 50},
        timeout=30,
    )
    comments_resp.raise_for_status()

    comments = [
        {
            "author": c["user"]["login"],
            "body": c["body"],
            "created_at": c["created_at"],
        }
        for c in comments_resp.json()
    ]

    return {
        "number": item["number"],
        "title": item["title"],
        "state": item["state"],
        "body": item.get("body", ""),
        "labels": [l["name"] for l in item.get("labels", [])],
        "assignees": [a["login"] for a in item.get("assignees", [])],
        "milestone": item["milestone"]["title"] if item.get("milestone") else None,
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
        "url": item["html_url"],
        "comments": comments,
    }


@mcp.tool()
def search_github_issues(
    query: str,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    per_page: int = 30,
):
    """Tìm kiếm issues trên GitHub bằng query.

    Args:
        query: Từ khóa tìm kiếm, ví dụ "login bug"
        owner: (Tuỳ chọn) Giới hạn tìm trong repo của owner này
        repo: (Tuỳ chọn) Giới hạn tìm trong repo cụ thể (cần cả owner)
        per_page: Số kết quả tối đa
    """
    q = query
    if owner and repo:
        q += f" repo:{owner}/{repo}"
    elif owner:
        q += f" user:{owner}"

    resp = httpx.get(
        f"{GITHUB_API}/search/issues",
        headers=_github_headers(),
        params={"q": q, "per_page": min(per_page, 100)},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("items", []):
        if "pull_request" in item:
            continue
        results.append(
            {
                "number": item["number"],
                "title": item["title"],
                "state": item["state"],
                "repo": item["repository_url"].split("/repos/")[-1],
                "labels": [l["name"] for l in item.get("labels", [])],
                "url": item["html_url"],
            }
        )
    return results if results else "Không tìm thấy issue nào."


@mcp.tool()
def add_comment_to_issue(owner: str, repo: str, issue_number: int, body: str):
    """Thêm comment vào một issue trên GitHub.

    Args:
        owner: Chủ sở hữu repo (user hoặc org)
        repo: Tên repo
        issue_number: Số issue
        body: Nội dung comment (hỗ trợ Markdown)
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN để thêm comment."

    resp = httpx.post(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments",
        headers=_github_headers(),
        json={"body": body},
        timeout=30,
    )
    resp.raise_for_status()
    comment = resp.json()
    return {
        "id": comment["id"],
        "url": comment["html_url"],
        "message": f"Đã thêm comment vào issue #{issue_number}.",
    }


@mcp.tool()
def create_pull_request(
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
    issue_number: int = 0,
    draft: bool = False,
):
    """Tạo Pull Request từ branch hiện tại.

    Args:
        owner: Chủ sở hữu repo
        repo: Tên repo
        title: Tiêu đề PR
        head: Branch chứa code (branch đang code), ví dụ "feature/login"
        base: Branch đích để merge vào, mặc định "main"
        body: Mô tả PR (hỗ trợ Markdown)
        issue_number: (Tuỳ chọn) Số issue để link vào PR. Nếu > 0 sẽ thêm "Closes #N" vào body
        draft: Tạo PR dạng draft hay không
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN để tạo PR."

    if issue_number > 0:
        close_ref = f"\n\nCloses #{issue_number}"
        body = body + close_ref if body else f"Closes #{issue_number}"

    payload = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "draft": draft,
    }

    resp = httpx.post(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
        headers=_github_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    pr = resp.json()
    return {
        "number": pr["number"],
        "url": pr["html_url"],
        "state": pr["state"],
        "message": f"Đã tạo PR #{pr['number']}: {pr['title']}",
    }


@mcp.tool()
def link_issue_to_pr(
    owner: str,
    repo: str,
    pr_number: int,
    issue_number: int,
):
    """Gắn issue vào PR bằng cách thêm "Closes #issue" vào body của PR.

    Args:
        owner: Chủ sở hữu repo
        repo: Tên repo
        pr_number: Số PR
        issue_number: Số issue cần link
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN."

    # Lấy PR hiện tại
    resp = httpx.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=_github_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    pr = resp.json()

    current_body = pr.get("body") or ""
    close_ref = f"Closes #{issue_number}"
    if close_ref.lower() in current_body.lower():
        return f"PR #{pr_number} đã link với issue #{issue_number} rồi."

    new_body = f"{current_body}\n\n{close_ref}".strip()
    resp = httpx.patch(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=_github_headers(),
        json={"body": new_body},
        timeout=30,
    )
    resp.raise_for_status()
    return f"Đã link issue #{issue_number} vào PR #{pr_number}."


@mcp.tool()
def add_comment_to_pr(owner: str, repo: str, pr_number: int, body: str):
    """Thêm comment vào một Pull Request.

    Args:
        owner: Chủ sở hữu repo
        repo: Tên repo
        pr_number: Số PR
        body: Nội dung comment (hỗ trợ Markdown)
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN."

    resp = httpx.post(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments",
        headers=_github_headers(),
        json={"body": body},
        timeout=30,
    )
    resp.raise_for_status()
    comment = resp.json()
    return {
        "id": comment["id"],
        "url": comment["html_url"],
        "message": f"Đã thêm comment vào PR #{pr_number}.",
    }


@mcp.tool()
def get_pr_review_comments(owner: str, repo: str, pr_number: int):
    """Lấy toàn bộ review comments trên PR (inline comments trên code).

    Args:
        owner: Chủ sở hữu repo
        repo: Tên repo
        pr_number: Số PR

    Returns:
        Danh sách comments kèm context: file, line, nội dung, trạng thái,
        và phân tích mức độ ưu tiên để giúp developer quyết định xử lý.
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN."

    # Lấy review comments (inline trên code)
    comments = []
    page = 1
    while True:
        resp = httpx.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            headers=_github_headers(),
            params={"per_page": 100, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        comments.extend(batch)
        page += 1

    if not comments:
        return "Không có review comments nào trên PR này."

    # Nhóm comments theo thread (in_reply_to_id)
    threads = {}
    for c in comments:
        thread_id = c.get("in_reply_to_id") or c["id"]
        if thread_id not in threads:
            threads[thread_id] = {
                "file": c.get("path", ""),
                "line": c.get("original_line") or c.get("line"),
                "diff_hunk": c.get("diff_hunk", ""),
                "comments": [],
            }
        threads[thread_id]["comments"].append(
            {
                "id": c["id"],
                "author": c["user"]["login"],
                "body": c["body"],
                "created_at": c["created_at"],
            }
        )

    result = []
    for tid, thread in threads.items():
        # Phân loại comment dựa trên nội dung
        first_body = thread["comments"][0]["body"].lower()
        category = _categorize_comment(first_body)
        result.append(
            {
                "thread_id": tid,
                "file": thread["file"],
                "line": thread["line"],
                "category": category,
                "diff_hunk": thread["diff_hunk"][:200],
                "comments": thread["comments"],
            }
        )

    return result


def _categorize_comment(body: str) -> str:
    """Phân loại comment theo mức độ ưu tiên."""
    body = body.lower()

    # Các pattern cho từng loại
    blocking_patterns = ["bug", "security", "vulnerability", "crash", "error",
                         "break", "fix this", "must", "critical", "blocker"]
    suggestion_patterns = ["nit", "suggestion", "consider", "maybe", "could",
                           "might", "optional", "minor", "nitpick", "style"]
    question_patterns = ["why", "what", "how", "?", "wondering", "curious",
                         "can you explain"]

    for p in blocking_patterns:
        if p in body:
            return "blocking"
    for p in question_patterns:
        if p in body:
            return "question"
    for p in suggestion_patterns:
        if p in body:
            return "suggestion"
    return "feedback"


@mcp.tool()
def reply_to_review_comment(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    body: str,
):
    """Trả lời một review comment trên PR.

    Args:
        owner: Chủ sở hữu repo
        repo: Tên repo
        pr_number: Số PR
        comment_id: ID của comment gốc cần reply
        body: Nội dung trả lời (hỗ trợ Markdown)
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN."

    resp = httpx.post(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies",
        headers=_github_headers(),
        json={"body": body},
        timeout=30,
    )
    resp.raise_for_status()
    reply = resp.json()
    return {
        "id": reply["id"],
        "url": reply["html_url"],
        "message": f"Đã reply comment #{comment_id}.",
    }


@mcp.tool()
def resolve_pr_review_thread(thread_id: str):
    """Resolve (thu gọn) một review thread trên PR bằng GraphQL API.

    Args:
        thread_id: Node ID của review thread (lấy từ get_pr_review_comments_with_thread_ids)
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN."

    # GitHub REST API không hỗ trợ resolve thread, phải dùng GraphQL
    query = """
    mutation($threadId: ID!) {
        resolveReviewThread(input: {threadId: $threadId}) {
            thread {
                isResolved
            }
        }
    }
    """
    resp = httpx.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {GITHUB_TOKEN}"},
        json={"query": query, "variables": {"threadId": thread_id}},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        return f"Lỗi GraphQL: {data['errors']}"
    return f"Đã resolve thread {thread_id}."


@mcp.tool()
def get_pr_review_comments_with_thread_ids(owner: str, repo: str, pr_number: int):
    """Lấy review comments kèm thread node IDs (cần để resolve threads).

    Dùng GraphQL để lấy node_id của thread, REST API không cung cấp thông tin này.

    Args:
        owner: Chủ sở hữu repo
        repo: Tên repo
        pr_number: Số PR
    """
    if not GITHUB_TOKEN:
        return "Lỗi: Cần GITHUB_TOKEN."

    query = """
    query($owner: String!, $repo: String!, $pr: Int!) {
        repository(owner: $owner, name: $repo) {
            pullRequest(number: $pr) {
                reviewThreads(first: 100) {
                    nodes {
                        id
                        isResolved
                        path
                        line
                        comments(first: 50) {
                            nodes {
                                id
                                databaseId
                                author { login }
                                body
                                createdAt
                            }
                        }
                    }
                }
            }
        }
    }
    """
    resp = httpx.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {GITHUB_TOKEN}"},
        json={
            "query": query,
            "variables": {"owner": owner, "repo": repo, "pr": pr_number},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        return f"Lỗi GraphQL: {data['errors']}"

    threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    result = []
    for t in threads:
        first_body = ""
        if t["comments"]["nodes"]:
            first_body = t["comments"]["nodes"][0]["body"]
        category = _categorize_comment(first_body)
        result.append(
            {
                "thread_node_id": t["id"],
                "is_resolved": t["isResolved"],
                "file": t.get("path", ""),
                "line": t.get("line"),
                "category": category,
                "comments": [
                    {
                        "id": c["databaseId"],
                        "author": c["author"]["login"] if c.get("author") else "ghost",
                        "body": c["body"],
                        "created_at": c["createdAt"],
                    }
                    for c in t["comments"]["nodes"]
                ],
            }
        )

    return result if result else "Không có review threads nào."


if __name__ == "__main__":
    mcp.run()
