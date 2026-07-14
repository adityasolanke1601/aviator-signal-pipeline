"""
enrich.py — pulls GitHub engineering signals for a company/org.

Signals we care about (from Aviator's ICP): large monorepos, high PR throughput,
heavy CI usage, GitHub-native workflows, recent DevEx/platform activity.
"""

import os
import time
import requests
from datetime import datetime, timedelta

GITHUB_API = "https://api.github.com"


def _get_with_retry(url, headers, params=None, timeout=15, retries=3):
    """GitHub calls die on flaky wifi; retry a few times with backoff before giving up."""
    last_err = None
    for attempt in range(retries):
        try:
            return requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            last_err = e
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"  [retry] connection dropped, retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


def _headers(token: str | None):
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_org_repos(org: str, token: str | None, max_repos: int = 8):
    """Top repos by size for an org (proxy: biggest repos = likely monorepo candidates)."""
    url = f"{GITHUB_API}/orgs/{org}/repos"
    params = {"per_page": 100, "type": "public", "sort": "updated"}
    r = _get_with_retry(url, headers=_headers(token), params=params, timeout=15)
    if r.status_code != 200:
        return []
    repos = r.json()
    repos.sort(key=lambda x: x.get("size", 0), reverse=True)
    return repos[:max_repos]


def has_ci_workflows(owner: str, repo: str, token: str | None) -> bool:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/.github/workflows"
    r = _get_with_retry(url, headers=_headers(token), timeout=15)
    return r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0


def pr_throughput_30d(owner: str, repo: str, token: str | None) -> int:
    """Count PRs opened in the last 30 days via the search API."""
    since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    q = f"repo:{owner}/{repo} type:pr created:>={since}"
    url = f"{GITHUB_API}/search/issues"
    r = _get_with_retry(url, headers=_headers(token), params={"q": q, "per_page": 1}, timeout=15)
    if r.status_code != 200:
        return 0
    return r.json().get("total_count", 0)


def enrich_org(org: str, token: str | None = None) -> dict:
    repos = get_org_repos(org, token)
    if not repos:
        return {"org": org, "found": False}

    total_size_kb = sum(r.get("size", 0) for r in repos)
    ci_count = 0
    pr_total = 0
    langs = set()

    for r in repos:
        owner_login = r["owner"]["login"]
        name = r["name"]
        langs.add(r.get("language") or "")
        if has_ci_workflows(owner_login, name, token):
            ci_count += 1
        pr_total += pr_throughput_30d(owner_login, name, token)
        time.sleep(0.3)  # be polite / avoid secondary rate limits

    biggest_repo = repos[0]["name"]
    ci_pct = round(100 * ci_count / len(repos), 1) if repos else 0

    # simple weighted fit score, 0-100
    score = 0
    score += min(total_size_kb / 5000, 40)          # monorepo size
    score += min(pr_total / 2, 30)                    # PR throughput
    score += ci_pct * 0.3                              # CI adoption

    return {
        "org": org,
        "found": True,
        "repos_analyzed": len(repos),
        "biggest_repo": biggest_repo,
        "total_size_kb": total_size_kb,
        "ci_adoption_pct": ci_pct,
        "pr_throughput_30d": pr_total,
        "languages": ", ".join(sorted(l for l in langs if l)),
        "fit_score": round(min(score, 100), 1),
    }


if __name__ == "__main__":
    token = os.getenv("GITHUB_TOKEN")
    for test_org in ["vercel", "supabase"]:
        print(enrich_org(test_org, token))