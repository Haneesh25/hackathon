# github_pr_fetch.py
# Fetch pull request metadata (including descriptions) from GitHub.
# Uses your filler PAT by default; prefer setting GITHUB_TOKEN in env.

import os, time, requests
from typing import List, Dict, Optional, Tuple

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "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"
)
BASE = "https://api.github.com"

def _headers() -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def _parse_link(link_header: Optional[str]) -> Dict[str, str]:
    out = {}
    if not link_header: return out
    for part in link_header.split(","):
        seg = [s.strip() for s in part.split(";")]
        if len(seg) < 2: continue
        url = seg[0].strip()[1:-1]
        rel = seg[1].split("=")[1].strip('"')
        out[rel] = url
    return out

def list_pull_requests(
    owner: str,
    repo: str,
    state: str = "open",   # 'open' | 'closed' | 'all'
    base: Optional[str] = None,   # filter by base branch (e.g., "main")
    sort: str = "created",        # 'created' | 'updated' | 'popularity' | 'long-running'
    direction: str = "desc",      # 'asc' | 'desc'
    since_iso: Optional[str] = None,  # filter client-side by updated_at >= since_iso
    per_page: int = 100,
    max_pages: int = 50
) -> List[Dict]:
    """
    Returns PR JSON objects. Important fields:
      - number, title, body (description), user.login, state, merged_at,
        base.ref, head.ref, created_at, updated_at, html_url
    """
    prs: List[Dict] = []
    url = f"{BASE}/repos/{owner}/{repo}/pulls"
    params: Dict[str, str] = {
        "state": state,
        "sort": sort,
        "direction": direction,
        "per_page": str(per_page),
    }
    if base: params["base"] = base

    for _ in range(max_pages):
        r = requests.get(url, headers=_headers(), params=params)
        if r.status_code == 404:
            raise RuntimeError(f"Repo not found or no access: {owner}/{repo}")
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = r.headers.get("X-RateLimit-Reset")
            raise RuntimeError(f"Rate-limited. X-RateLimit-Reset={reset}")
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list):
            # Sometimes GitHub returns an error object; surface it.
            raise RuntimeError(batch)
        if not batch:
            break

        # Optional client-side since filter (GitHub PRs API lacks direct 'since' param)
        if since_iso:
            batch = [pr for pr in batch if pr.get("updated_at", "") >= since_iso]

        prs.extend(batch)

        links = _parse_link(r.headers.get("Link"))
        if "next" not in links:
            break
        url, params = links["next"], {}  # 'next' already encodes params
        time.sleep(0.1)

    return prs

def list_multiple_repos_prs(
    repos: List[Tuple[str, str]],
    **kwargs
) -> Dict[str, List[Dict]]:
    """
    Convenience: pass list of (owner, repo); returns { 'owner/repo': [PRs...] }.
    kwargs passed to list_pull_requests (state, base, since_iso, etc.)
    """
    out: Dict[str, List[Dict]] = {}
    for owner, repo in repos:
        key = f"{owner}/{repo}"
        out[key] = list_pull_requests(owner, repo, **kwargs)
    return out

if __name__ == "__main__":
    # Example usage:
    # 1) Single repo: open PRs (default)
    prs = list_pull_requests(owner="octocat", repo="Hello-World", state="all", per_page=50, max_pages=2)
    print(f"octocat/Hello-World PRs: {len(prs)}")
    if prs:
        first = prs[0]
        print("Sample PR -> #", first.get("number"))
        print("Title:", first.get("title"))
        print("Description (body) preview:", (first.get("body") or "")[:200])
        print("URL:", first.get("html_url"))
        print("State:", first.get("state"), "Merged at:", first.get("merged_at"))

    # 2) Multiple repos, only PRs updated since a date, on main branch
    multi = list_multiple_repos_prs(
        [("octocat", "Hello-World"), ("torvalds", "linux")],
        state="all",
        base="main",
        since_iso="2025-11-01T00:00:00Z",
        per_page=50,
        max_pages=2
    )
    print("Multi keys:", list(multi.keys()))
