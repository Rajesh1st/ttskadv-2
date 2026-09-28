# -*- coding: utf-8 -*-
# sites/ef.py — ExtraFlix scraper (FIXED: HubDrive → HubCloud)

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from bot import load_config, HEADERS


_session = requests.Session()
_session.headers.update(HEADERS)

_BLOCKED = re.compile(r"\bUNRATED\b|\b18\+\b", re.I)


# =========================================================
# HELPERS
# =========================================================

def _clean_ef_filename(name):
    name = re.sub(r"[-_. ]*ExtraFlix\.Pw", "", name, flags=re.I)
    name = re.sub(r"\s*-\s*[\d.]+\s*(MB|GB)\s*$", "", name, flags=re.I)
    if not re.search(r"\.(mkv|mp4|avi)$", name, re.I):
        name += ".mkv"
    name = re.sub(r"\.mkv$", ".Esub.mkv", name, flags=re.I)
    return name.strip()


def _is_series(title):
    return bool(re.search(
        r'\b(season\s*\d+|s\d{1,2}\b|episode\s*\d+|ep\d{1,3}\b|complete)\b',
        title, re.I
    ))


# =========================================================
# POSTS LIST
# =========================================================

def get_ef_posts():
    cfg = load_config()
    base = cfg.get("ef_url", "https://e4.extraflix.mobi/").rstrip("/") + "/"
    posts = []
    try:
        r = _session.get(base, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(base, a["href"]).split("#")[0].split("?")[0]
            if not href.startswith(base):
                continue
            path = href[len(base):].strip("/")
            if not path or "/" in path:
                continue
            if any(path.startswith(p) for p in
                   ("category", "tag", "page", "wp-", "feed", "author", "search")):
                continue
            if href.rstrip("/") == base.rstrip("/"):
                continue
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text(" ", strip=True) or path.replace("-", " ").title()
            posts.append({"title": title, "url": href})
        print(f"[EF] Posts found: {len(posts)}")
    except Exception as e:
        print(f"[EF] get_ef_posts error: {e}")
    return posts


# =========================================================
# POST → LINKSHUB LINKS
# =========================================================

def get_ef_linkshub_links(movie_url):
    if _BLOCKED.search(movie_url):
        print(f"[EF] Blocked (UNRATED/18+): {movie_url}")
        return []
    try:
        r = _session.get(movie_url, timeout=30)
        r.raise_for_status()
        links = re.findall(
            r'https://links\.linkshub\.fun/view/[A-Za-z0-9]+',
            r.text, re.I
        )
        links = list(dict.fromkeys(links))
        print(f"[EF] Linkshub links: {len(links)} for {movie_url}")
        return links
    except Exception as e:
        print(f"[EF] get_ef_linkshub_links error: {e}")
        return []


# =========================================================
# LINKSHUB → DRIVEHUB + HUBDRIVE
# =========================================================

def _get_ef_file_links(linkshub_url):
    """Linkshub page se DriveHub aur HubDrive links nikaalo."""
    try:
        r = _session.get(linkshub_url, timeout=30, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        html = r.text

        # ----- Filename -----
        h2 = soup.find("h2")
        if h2:
            filename = h2.get_text(" ", strip=True)
        elif soup.title:
            filename = soup.title.get_text(strip=True)
        else:
            filename = "Movie.mkv"
        filename = _clean_ef_filename(filename)

        # ----- All /file/ID links -----
        all_file_links = re.findall(
            r'https?://[^"\'<>\s]+/file/\d+',
            html, re.I
        )
        all_file_links = list(dict.fromkeys(all_file_links))

        drivehub_links = [l for l in all_file_links
                          if re.search(r'drivehub\.', l, re.I)]
        hubdrive_links = [l for l in all_file_links
                          if re.search(r'hubdrive\.', l, re.I)]

        print(f"[EF] {linkshub_url}")
        print(f"     DriveHub: {len(drivehub_links)}  HubDrive: {len(hubdrive_links)}")

        return {
            "title": filename,
            "drivehub": drivehub_links,
            "hubdrive": hubdrive_links,
        }
    except Exception as e:
        print(f"[EF] _get_ef_file_links error: {e}")
        return None


# =========================================================
# HUBDRIVE → HUBCLOUD  (FIXED)
# =========================================================

def get_ef_hubcloud(hubdrive_url):
    """HubDrive page se HubCloud link nikaalo. 3 fallback methods."""
    try:
        r = _session.get(hubdrive_url, timeout=30, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        hubcloud_links = []

        # Method 1: <a href> containing "hubcloud."
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if re.search(r'hubcloud\.', href, re.I):
                hubcloud_links.append(href)

        # Method 2: raw regex on HTML (any hubcloud.* TLD)
        if not hubcloud_links:
            hubcloud_links = re.findall(
                r'https?://hubcloud\.[^"\'<>\s]+',
                r.text, re.I
            )

        # Method 3: anchor whose visible text has "hubcloud"
        if not hubcloud_links:
            for a in soup.find_all("a", href=True):
                if "hubcloud" in a.get_text(strip=True).lower():
                    href = a.get("href", "").strip()
                    if href:
                        hubcloud_links.append(href)

        hubcloud_links = list(dict.fromkeys(hubcloud_links))
        if hubcloud_links:
            print(f"[EF] HubCloud: {hubcloud_links[0]}")
            return hubcloud_links[0]

        print(f"[EF] HubCloud NOT found inside: {hubdrive_url}")
        return None
    except Exception as e:
        print(f"[EF] get_ef_hubcloud error: {e}")
        return None


# =========================================================
# MAIN: get_ef_final_links
# =========================================================

def get_ef_final_links(post_url, post_title, extractor="hubcloud"):
    """
    extractor options:
      "hubcloud" : HubDrive → HubCloud  (DEFAULT, fallback: hubdrive → drivehub)
      "hubdrive" : sirf HubDrive link
      "drivehub" : sirf DriveHub link
      "all"      : DriveHub + HubDrive + HubCloud (jo bhi mile)
    """
    linkshubs = get_ef_linkshub_links(post_url)
    if not linkshubs:
        return []

    results = []
    seen_links = set()

    for ls_url in linkshubs:
        data = _get_ef_file_links(ls_url)
        if not data:
            continue

        title = data["title"] or post_title
        drivehub_url = data["drivehub"][0] if data["drivehub"] else None
        hubdrive_url = data["hubdrive"][0] if data["hubdrive"] else None

        hubcloud_url = None
        if hubdrive_url and extractor in ("hubcloud", "all"):
            hubcloud_url = get_ef_hubcloud(hubdrive_url)

        candidates = []

        if extractor == "hubcloud":
            final = hubcloud_url or hubdrive_url or drivehub_url
            if final:
                used = ("hubcloud" if hubcloud_url
                        else "hubdrive" if hubdrive_url
                        else "drivehub")
                candidates.append((final, used))
        elif extractor == "hubdrive":
            if hubdrive_url:
                candidates.append((hubdrive_url, "hubdrive"))
        elif extractor == "drivehub":
            if drivehub_url:
                candidates.append((drivehub_url, "drivehub"))
        elif extractor == "all":
            if drivehub_url:
                candidates.append((drivehub_url, "drivehub"))
            if hubdrive_url:
                candidates.append((hubdrive_url, "hubdrive"))
            if hubcloud_url:
                candidates.append((hubcloud_url, "hubcloud"))

        for link, used in candidates:
            if link in seen_links:
                continue
            seen_links.add(link)
            results.append({
                "title": title,
                "link": link,
                "is_series": _is_series(title),
                "extractor_used": used,
            })

    print(f"[EF] Total links prepared: {len(results)} (extractor={extractor})")
    return results
