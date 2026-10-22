"""Automatic captions for videos supplied by the rights holder.

Generates sensible fallback copy at zero API cost. No claims of AI analysis.
"""
import re
from urllib.parse import unquote, urlsplit

HASHTAGS = {
    "youtube": "#shorts #video",
    "tiktok": "#fyp #video",
    "instagram": "#reels #video",
}

def title_from_url(url):
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    name = re.sub(r"\.(mp4|mov|m4v|webm)$", "", name, flags=re.I)
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100].title() if name else "New Video"

def compose(title, media_url, platform, template=""):
    heading = (title or title_from_url(media_url)).strip()[:100]
    if template.strip():
        return template.replace("{title}", heading).replace("{platform}", platform)[:850]
    return (heading + "\n\n" + HASHTAGS.get(platform, "#video"))[:850]
