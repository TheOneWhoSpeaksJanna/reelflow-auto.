"""Import up to 500 licensed media references without downloading files."""
from flask import Blueprint, jsonify, request
from integrations import validate_url, direct_video
from store import WAKE, db, event, now

import_api = Blueprint("import_api", __name__, url_prefix="/api")


@import_api.post("/import")
def import_links():
    payload = request.get_json(silent=True) or {}
    if payload.get("rights") is not True:
        return jsonify(ok=False, error="Confirm you own or may use the footage"), 400
    lines = [line.strip() for line in str(payload.get("links", "")).splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if not 1 <= len(lines) <= 500:
        return jsonify(ok=False, error="Paste between 1 and 500 links"), 400
    parsed = []
    try:
        for line in lines:
            urls = [piece.strip() for piece in line.split("|")]
            if len(urls) > 2:
                raise ValueError("Expected SOURCE_URL | DIRECT_VIDEO_URL")
            source = validate_url(urls[0])
            media = validate_url(urls[1]) if len(urls) == 2 and urls[1] else (
                source if direct_video(source) else "")
            if media and not direct_video(media):
                raise ValueError("Media must be a direct .mp4, .mov, .m4v or .webm link")
            parsed.append((source, media))
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    with db() as c:
        added = 0
        for source, media in parsed:
            if c.execute("SELECT count(*) FROM jobs").fetchone()[0] >= 500:
                break
            result = c.execute(
                "INSERT OR IGNORE INTO jobs(source_url,media_url,status,created,changed) VALUES (?,?,?,?,?)",
                (source, media, "pending" if media else "needs_source", now(), now()))
            added += result.rowcount
        event(c, "Imported " + str(added) + " jobs")
    WAKE.set()
    return jsonify(ok=True, added=added, duplicates=len(parsed)-added,
                   requires_media=sum(not bool(media) for _, media in parsed))
