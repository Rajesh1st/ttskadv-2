# -*- coding: utf-8 -*-
"""Deterministic posting policy engine.

Rules are intentionally pure functions so they can be tested without Telegram,
RSS, or MongoDB. Settings may be global per source and overridden per channel.
"""
import re

DEFAULT_RULE = {
    "max_posts_per_cycle": 0,
    "max_links_per_post": 0,
    "quality_mode": "all",          # all | selected
    "qualities": [],                 # e.g. ["1080p", "720p"]
    "series_quality_mode": "all",  # all | selected
    "series_qualities": [],
    "unknown_quality": "allow",
    "max_file_size_mb": 0,
    "max_zip_size_gb": 0,
    "post_gap_seconds": 0,
    "quality_gap_seconds": 0,
    "queue_enabled": True,
}

QUALITY_RE = re.compile(r"(?<!\d)(2160p|4k|1440p|1080p|720p|576p|480p|360p)(?!\d)", re.I)
SIZE_RE = re.compile(r"([\d.]+)\s*(gb|gib|mb|mib)", re.I)


def normalize_quality(value):
    value = str(value or "").strip().lower()
    return "2160p" if value == "4k" else value


def quality_from_item(item):
    explicit = normalize_quality(item.get("quality"))
    if explicit:
        return explicit
    match = QUALITY_RE.search(str(item.get("title", "")))
    return normalize_quality(match.group(1)) if match else ""


def size_mb(item):
    for key in ("size_mb", "file_size_mb"):
        try:
            if item.get(key) is not None:
                return float(item[key])
        except (TypeError, ValueError):
            pass
    text = str(item.get("size") or item.get("size_text") or "")
    match = SIZE_RE.search(text)
    if not match:
        return 0.0
    value = float(match.group(1))
    return value * 1024 if match.group(2).lower().startswith("g") else value


def is_series(item):
    if "is_series" in item:
        return bool(item["is_series"])
    return bool(re.search(r"\b(?:season|s\d{1,2}|episode|ep\d{1,3}|complete)\b", str(item.get("title", "")), re.I))


def rule_for(cfg, source, chat_id=None):
    base = dict(DEFAULT_RULE)
    base.update((cfg.get("posting_rules") or {}).get(source, {}))
    overrides = cfg.get("chat_overrides", {})
    if chat_id is not None:
        override = overrides.get(str(chat_id), {}).get("posting_rules", {}).get(source, {})
        base.update(override)
    base["qualities"] = [normalize_quality(x) for x in base.get("qualities", []) if str(x).strip()]
    base["series_qualities"] = [normalize_quality(x) for x in base.get("series_qualities", []) if str(x).strip()]
    return base


def filter_items(items, rule):
    """Return allowed items and a human-readable reason for each rejected item."""
    allowed, rejected = [], []
    for item in items:
        series = is_series(item)
        q = quality_from_item(item)
        mode = rule.get("series_quality_mode") if series else rule.get("quality_mode")
        selected = rule.get("series_qualities", []) if series else rule.get("qualities", [])
        if mode == "selected" and (q not in selected):
            if not q and rule.get("unknown_quality", "allow") == "allow":
                pass
            else:
                rejected.append((item, "quality")); continue
        limit = float(rule.get("max_file_size_mb") or 0)
        if limit and size_mb(item) > limit:
            rejected.append((item, "file_size")); continue
        zip_limit = float(rule.get("max_zip_size_gb") or 0)
        if zip_limit and ("zip" in str(item.get("link", "")).lower() or "zip" in str(item.get("title", "")).lower()):
            if size_mb(item) > zip_limit * 1024:
                rejected.append((item, "zip_size")); continue
        allowed.append(item)
    max_links = int(rule.get("max_links_per_post") or 0)
    if max_links > 0:
        allowed = allowed[:max_links]
    return allowed, rejected


def limit_posts(posts, rule):
    max_posts = int(rule.get("max_posts_per_cycle") or 0)
    return posts[:max_posts] if max_posts > 0 else posts
