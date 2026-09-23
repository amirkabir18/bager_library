"""
GitHub contributor statistics service for Bager Library.
Fetches real contributor metrics and calculates lines-of-code percentage.
"""

import json
import logging
import os
import tempfile
import time
import urllib.error
import urllib.request
from typing import Optional

from updater import load_app_info

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(tempfile.gettempdir(), "bager_contributors_cache.json")
DEFAULT_CACHE_TTL = 86400  # 24 hours

KNOWN_NAMES = {
    "amirkabir18": "امیرحسین اسدی",
    "aliomosavi": "سید محمد حسن موسوی",
    "arush221617": "امیررضا یونس‌زاده شیرازی",
}

DEFAULT_CONTRIBUTORS = [
    {
        "login": "amirkabir18",
        "name": "امیرحسین اسدی",
        "percent": 0.0,
        "html_url": "https://github.com/amirkabir18",
    },
    {
        "login": "Aliomosavi",
        "name": "سید محمد حسن موسوی",
        "percent": 0.0,
        "html_url": "https://github.com/Aliomosavi",
    },
    {
        "login": "ARUSH221617",
        "name": "امیررضا یونس‌زاده شیرازی",
        "percent": 0.0,
        "html_url": "https://github.com/ARUSH221617",
    },
]


def get_contributor_display_name(login: str) -> str:
    """Returns mapped Persian name or GitHub login."""
    return KNOWN_NAMES.get(login.lower(), login)


def calculate_code_percentages(stats_items: list[dict]) -> list[dict]:
    """
    Calculates code written percentage per contributor based on lines added.
    ponytail: calculates lines added ('a'); upgrade to net diff ('a' - 'd') when deletions matter.
    """
    entries = []
    total_lines = 0

    for item in stats_items:
        if not isinstance(item, dict):
            continue
        author = item.get("author") or {}
        login = author.get("login")
        if not login:
            continue

        weeks = item.get("weeks", [])
        lines_added = sum(int(w.get("a", 0)) for w in weeks if isinstance(w, dict))
        total_lines += lines_added

        entries.append({
            "login": login,
            "name": get_contributor_display_name(login),
            "html_url": author.get("html_url") or f"https://github.com/{login}",
            "avatar_url": author.get("avatar_url", ""),
            "lines_added": lines_added,
        })

    for entry in entries:
        if total_lines > 0:
            entry["percent"] = round((entry["lines_added"] / total_lines) * 100, 1)
        else:
            entry["percent"] = 0.0

    entries.sort(key=lambda x: (x["percent"], x.get("lines_added", 0)), reverse=True)
    return entries


def calculate_commit_percentages(contributors_items: list[dict]) -> list[dict]:
    """
    Fallback: calculates percentage based on commit count if stats API unavailable.
    """
    entries = []
    total_commits = 0

    for item in contributors_items:
        if not isinstance(item, dict):
            continue
        login = item.get("login")
        if not login:
            continue
        commits = int(item.get("contributions", 0))
        total_commits += commits
        entries.append({
            "login": login,
            "name": get_contributor_display_name(login),
            "html_url": item.get("html_url") or f"https://github.com/{login}",
            "avatar_url": item.get("avatar_url", ""),
            "commits": commits,
            "lines_added": 0,
        })

    for entry in entries:
        if total_commits > 0:
            entry["percent"] = round((entry["commits"] / total_commits) * 100, 1)
        else:
            entry["percent"] = 0.0

    entries.sort(key=lambda x: x["percent"], reverse=True)
    return entries


def fetch_contributors_from_github(repo: Optional[str] = None, timeout: int = 6) -> list[dict]:
    """
    Queries GitHub API for contributor code stats with fallback to commit count.
    """
    repo = repo or load_app_info().get("github_repo", "amirkabir18/bager_library")
    headers = {
        "User-Agent": "BagerLibrary-App",
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Primary: /stats/contributors (lines of code added)
    stats_url = f"https://api.github.com/repos/{repo}/stats/contributors"
    req = urllib.request.Request(stats_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and data:
                    return calculate_code_percentages(data)
    except urllib.error.HTTPError as he:
        if he.code != 202:
            logger.debug("Stats API HTTP %d for %s", he.code, repo)
    except Exception as e:
        logger.debug("Stats API failed: %s", e)

    # 2. Fallback: /contributors (commit counts)
    fallback_url = f"https://api.github.com/repos/{repo}/contributors?per_page=100"
    req_fb = urllib.request.Request(fallback_url, headers=headers)
    try:
        with urllib.request.urlopen(req_fb, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and data:
                    return calculate_commit_percentages(data)
    except Exception as e:
        logger.debug("Contributors API failed: %s", e)

    return list(DEFAULT_CONTRIBUTORS)


def load_cached_contributors(cache_path: str = CACHE_FILE, ttl: int = DEFAULT_CACHE_TTL) -> Optional[list[dict]]:
    """Loads cached contributor statistics if valid and unexpired."""
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            cached_time = data.get("timestamp", 0)
            if time.time() - cached_time <= ttl:
                items = data.get("contributors")
                if isinstance(items, list) and items:
                    return items
    except Exception:
        pass
    return None


def save_cached_contributors(contributors: list[dict], cache_path: str = CACHE_FILE) -> None:
    """Saves contributor statistics to local cache."""
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time(), "contributors": contributors}, f, ensure_ascii=False)
    except Exception:
        pass


def get_contributors_stats(
    repo: Optional[str] = None,
    cache_path: str = CACHE_FILE,
    cache_ttl: int = DEFAULT_CACHE_TTL,
    force_refresh: bool = False,
    timeout: int = 6,
) -> list[dict]:
    """
    Returns contributor stats with percentage of code written.
    Uses local cache, calls GitHub API, and falls back gracefully.
    """
    if not force_refresh:
        cached = load_cached_contributors(cache_path, ttl=cache_ttl)
        if cached:
            return cached

    contributors = fetch_contributors_from_github(repo=repo, timeout=timeout)
    if contributors:
        save_cached_contributors(contributors, cache_path=cache_path)
        return contributors

    cached_expired = load_cached_contributors(cache_path, ttl=float("inf"))
    if cached_expired:
        return cached_expired

    return list(DEFAULT_CONTRIBUTORS)
