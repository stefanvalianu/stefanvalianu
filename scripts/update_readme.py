#!/usr/bin/env python3
"""Fetch latest Bluesky posts and update README.md.

No external dependencies -- uses only Python stdlib.

Usage:
    python update_readme.py [handle]

    handle  Bluesky handle (default: BLUESKY_HANDLE env var)
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime


README_PATH = "README.md"
POST_LIMIT = 5
API_BASE = "https://public.api.bsky.app/xrpc"


def fetch_posts(handle, limit=5):
    """Fetch recent posts from the public Bluesky API (no auth required)."""
    url = (
        f"{API_BASE}/app.bsky.feed.getAuthorFeed"
        f"?actor={handle}&limit={limit}&filter=posts_no_replies"
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def format_posts_md(data, handle):
    """Format feed data as a markdown snippet using blockquotes."""
    entries = []

    for item in data.get("feed", []):
        # Skip reposts
        if item.get("reason"):
            continue

        post = item.get("post", {})
        record = post.get("record", {})

        text = record.get("text", "").strip()
        if not text:
            continue

        # Truncate long posts and flatten newlines
        display = text.replace("\n", " ")
        if len(display) > 140:
            display = display[:137] + "..."

        # Parse date
        created = record.get("createdAt", "")
        date_str = ""
        if created:
            try:
                dt = datetime.strptime(created[:10], "%Y-%m-%d")
                date_str = f"{dt.strftime('%b')} {dt.day}"
            except (ValueError, IndexError):
                pass

        # Post URL from AT URI
        uri = post.get("uri", "")
        rkey = uri.rsplit("/", 1)[-1] if "/" in uri else ""
        post_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

        # Engagement stats
        likes = post.get("likeCount", 0)
        reposts = post.get("repostCount", 0)

        lines = [f"> {display}", ">"]
        meta_parts = []
        if date_str:
            meta_parts.append(f"[{date_str}]({post_url})")
        else:
            meta_parts.append(f"[link]({post_url})")
        if likes:
            meta_parts.append(f"{likes} likes")
        if reposts:
            meta_parts.append(f"{reposts} reposts")
        lines.append(f'> {" \u00b7 ".join(meta_parts)}')

        entries.append("\n".join(lines))

    if not entries:
        return "_No recent posts found._"

    return "\n\n".join(entries)


def update_section(section_id, content):
    """Replace content between <!-- SECTION:START --> and <!-- SECTION:END --> markers."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    start_marker = f"<!-- {section_id}:START -->"
    end_marker = f"<!-- {section_id}:END -->"

    si = readme.find(start_marker)
    ei = readme.find(end_marker)

    if si == -1 or ei == -1:
        print(f"Warning: {section_id} markers not found in {README_PATH}")
        return False

    new = readme[: si + len(start_marker)] + "\n" + content + "\n" + readme[ei:]

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new)

    return True


def main():
    handle = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("BLUESKY_HANDLE", "")
    )

    if not handle:
        print("No Bluesky handle provided. Skipping.")
        return

    try:
        data = fetch_posts(handle, POST_LIMIT)
        content = format_posts_md(data, handle)
        n = len([i for i in data.get("feed", []) if not i.get("reason")])
        print(f"Fetched {n} posts from @{handle}")
    except urllib.error.HTTPError as e:
        print(f"HTTP error fetching posts: {e.code} {e.reason}")
        content = "_Could not load posts right now._"
    except Exception as e:
        print(f"Error: {e}")
        content = "_Could not load posts right now._"

    if update_section("BLUESKY", content):
        print(f"Updated {README_PATH}")


if __name__ == "__main__":
    main()
