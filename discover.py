"""
discover.py — auto-discovers candidate orgs instead of relying on a manual list.

Uses the GitHub Search API to find orgs whose public repos show the signals
Aviator cares about: high star count (real engineering org, not a toy repo),
recent activity, and GitHub Actions usage (searchable via `path:.github/workflows`).
"""

import time
import requests
from typing import Optional

GITHUB_API = "https://api.github.com"


def _headers(token: Optional[str]):
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get_with_retry(url, headers, params=None, timeout=15, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            return requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  [retry] connection dropped, retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


def discover_orgs(
    min_stars: int = 2000,
    language: Optional[str] = None,
    max_results: int = 20,
    token: Optional[str] = None,
) -> list[str]:
    """
    Search public repos above a star threshold (owned by orgs, not users),
    optionally filtered by language, and return a deduped list of org logins.
    Sorted by stars descending so the highest-signal candidates come first.
    """
    q = f"stars:>{min_stars} archived:false"
    if language:
        q += f" language:{language}"

    url = f"{GITHUB_API}/search/repositories"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": 50}
    r = _get_with_retry(url, headers=_headers(token), params=params, timeout=15)
    if r.status_code != 200:
        print(f"[discover] search failed: {r.status_code} {r.text[:200]}")
        return []

    orgs = []
    seen = set()
    for item in r.json().get("items", []):
        owner = item.get("owner", {})
        if owner.get("type") != "Organization":
            continue
        login = owner["login"]
        if login not in seen:
            seen.add(login)
            orgs.append(login)
        if len(orgs) >= max_results:
            break

    return orgs


if __name__ == "__main__":
    print(discover_orgs(min_stars=5000, language="typescript", max_results=10))