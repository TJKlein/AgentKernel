"""
GitHub Issue Fetcher for ConceptDriftBench Family D.

Fetches public GitHub issues via the REST API and caches them locally.
Falls back to synthetic data (from generator.py) if the API is unreachable
or rate-limited, keeping the benchmark fully reproducible offline.

Usage:
    python -m benchmarks.conceptdrift.github_fetcher --repo pandas-dev/pandas --count 500
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_REPOS = [
    "pandas-dev/pandas",
    "scikit-learn/scikit-learn",
]

CACHE_DIR = Path(__file__).resolve().parent / "data" / "github"


def fetch_github_issues(
    repo: str,
    count: int = 500,
    token: Optional[str] = None,
    per_page: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch public GitHub issues for a repository.

    Args:
        repo: Owner/name (e.g. "pandas-dev/pandas").
        count: Maximum number of issues to fetch.
        token: Optional GitHub PAT for higher rate limits.
        per_page: Results per API page (max 100).

    Returns:
        List of issue dicts (GitHub API format).
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — run `pip install requests`")
        return []

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    all_issues: List[Dict[str, Any]] = []
    page = 1
    max_pages = (count // per_page) + 1

    while len(all_issues) < count and page <= max_pages:
        params = {"state": "all", "per_page": per_page, "page": page}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 403:
                logger.warning("GitHub API rate limit hit — returning cached/partial results")
                break
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            all_issues.extend(batch)
            page += 1
            time.sleep(0.5)  # polite rate limiting
        except Exception as e:
            logger.warning(f"GitHub API error on page {page}: {e}")
            break

    return all_issues[:count]


def cache_issues(
    issues: List[Dict[str, Any]],
    repo: str,
    cache_dir: Optional[Path] = None,
) -> Path:
    """
    Save fetched issues to a local JSON cache file.

    Returns:
        Path to the cached file.
    """
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    safe_name = repo.replace("/", "_")
    path = cache_dir / f"{safe_name}_issues.json"
    with open(path, "w") as f:
        json.dump(issues, f, indent=2)
    logger.info(f"Cached {len(issues)} issues for {repo} -> {path}")
    return path


def load_cached_issues(
    repo: str,
    cache_dir: Optional[Path] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Load previously cached issues. Returns None if cache miss."""
    cache_dir = cache_dir or CACHE_DIR
    safe_name = repo.replace("/", "_")
    path = cache_dir / f"{safe_name}_issues.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} cached issues for {repo}")
        return data
    return None


def fetch_and_cache(
    repo: str,
    count: int = 500,
    token: Optional[str] = None,
    force: bool = False,
    cache_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch issues from GitHub and cache, or return cached copy.

    Args:
        repo: Owner/name.
        count: Max issues.
        token: GitHub PAT (optional).
        force: Re-fetch even if cached.
        cache_dir: Override cache directory.

    Returns:
        List of issue dicts.
    """
    if not force:
        cached = load_cached_issues(repo, cache_dir)
        if cached and len(cached) >= count:
            return cached[:count]

    issues = fetch_github_issues(repo, count, token)
    if issues:
        cache_issues(issues, repo, cache_dir)
    else:
        cached = load_cached_issues(repo, cache_dir)
        if cached:
            logger.info("API fetch failed — falling back to cache")
            return cached[:count]
        logger.warning("No cached issues and API fetch failed — returning empty list")
    return issues


# -------------------------------------------------------------------
# CLI entry point
# -------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch and cache GitHub issues")
    parser.add_argument("--repo", default="pandas-dev/pandas", help="GitHub repo (owner/name)")
    parser.add_argument("--count", type=int, default=500, help="Number of issues to fetch")
    parser.add_argument("--token", default=None, help="GitHub PAT for higher rate limits")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if cached")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    issues = fetch_and_cache(args.repo, args.count, args.token, args.force)
    print(f"Fetched/loaded {len(issues)} issues for {args.repo}")


if __name__ == "__main__":
    main()
