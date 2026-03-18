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


if __name__ == "__main__":
    mcp.run()
