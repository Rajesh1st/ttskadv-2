# -*- coding: utf-8 -*-
"""Small persistence adapter: MongoDB when configured, JSON fallback otherwise."""
import json
import os
import threading
import time

_LOCK = threading.RLock()
_CLIENT = None
_DB = None


def _mongo():
    global _CLIENT, _DB
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return None
    if _DB is not None:
        return _DB
    try:
        from pymongo import MongoClient
        _CLIENT = MongoClient(uri, serverSelectionTimeoutMS=1500)
        _CLIENT.admin.command("ping")
        _DB = _CLIENT[os.getenv("MONGODB_DB", "rss_bot")]
        return _DB
    except Exception as exc:
        print(f"MongoDB unavailable, using JSON fallback: {exc}")
        return None


def load_settings(path, default):
    db = _mongo()
    if db is not None:
        doc = db.settings.find_one({"_id": "config"})
        if doc and doc.get("value"):
            return doc["value"]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_settings(path, value):
    db = _mongo()
    if db is not None:
        db.settings.replace_one({"_id": "config"}, {"_id": "config", "value": value}, upsert=True)
    with _LOCK, open(path, "w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=2)


def load_seen(path):
    db = _mongo()
    if db is not None:
        return {x["url"] for x in db.seen_posts.find({}, {"url": 1})}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return set(json.load(fh))
    except Exception:
        return set()


def save_seen(path, seen):
    db = _mongo()
    if db is not None:
        db.seen_posts.delete_many({})
        if seen:
            db.seen_posts.insert_many([{"url": url} for url in seen])
    with _LOCK, open(path, "w", encoding="utf-8") as fh:
        json.dump(sorted(seen), fh)


def load_stats(path, default):
    db = _mongo()
    if db is not None:
        doc = db.stats.find_one({"_id": "daily"})
        if doc and doc.get("value"):
            return doc["value"]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_stats(path, value):
    db = _mongo()
    if db is not None:
        db.stats.replace_one({"_id": "daily"}, {"_id": "daily", "value": value}, upsert=True)
    with _LOCK, open(path, "w", encoding="utf-8") as fh:
        json.dump(value, fh)


def enqueue(item, source, chat_id, path="queue.json"):
    db = _mongo()
    payload = dict(item, source=source, chat_id=int(chat_id), queued_at=time.time())
    if db is not None:
        result = db.queue.insert_one(payload)
        return str(result.inserted_id)
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8") as fh: rows = json.load(fh)
        except Exception: rows = []
        payload["id"] = f"{source}:{chat_id}:{payload['queued_at']}"
        rows.append(payload)
        with open(path, "w", encoding="utf-8") as fh: json.dump(rows, fh, indent=2)
        return payload["id"]


def pending(limit=100, path="queue.json"):
    db = _mongo()
    if db is not None:
        return list(db.queue.find().sort("queued_at", 1).limit(limit))
    try:
        with open(path, "r", encoding="utf-8") as fh: return json.load(fh)[:limit]
    except Exception: return []


def remove_queue(item_id, path="queue.json"):
    db = _mongo()
    if db is not None:
        from bson import ObjectId
        try: db.queue.delete_one({"_id": ObjectId(item_id)})
        except Exception: pass
        return
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8") as fh: rows = json.load(fh)
            rows = [x for x in rows if x.get("id") != item_id]
            with open(path, "w", encoding="utf-8") as fh: json.dump(rows, fh, indent=2)
        except Exception: pass
