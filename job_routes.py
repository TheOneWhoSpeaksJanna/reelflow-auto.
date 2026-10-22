"""Maintain queued jobs; avoid duplicate posts on uncertain failures."""
from flask import Blueprint, jsonify, request
from integrations import validate_url, direct_video
from store import WAKE, db, event, now

job_api = Blueprint("job_api", __name__, url_prefix="/api/jobs")


def bad(message, code=400):
    return jsonify(ok=False, error=message), code


@job_api.post("/<int:job_id>/source")
def source(job_id):
    data = request.get_json(silent=True) or {}
    try:
        url = validate_url(str(data.get("media_url", "")))
    except ValueError as exc:
        return bad(str(exc))
    if not direct_video(url):
        return bad("Provide a public HTTPS direct video file URL")
    title = str(data.get("title", "New video")).strip()[:100]
    with db() as c:
        row = c.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return bad("Job not found", 404)
        if row["status"] not in ("needs_source", "failed"):
            return bad("This job is not editable")
        c.execute("UPDATE jobs SET media_url=?,title=?,status='pending',error='',changed=? WHERE id=?",
                  (url, title, now(), job_id))
        event(c, "Video source added", job_id)
    WAKE.set()
    return jsonify(ok=True)


@job_api.post("/<int:job_id>/retry")
def retry(job_id):
    with db() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return bad("Job not found", 404)
        if row["status"] != "failed" or row["public_id"] or row["posts"] != "{}":
            return bad("Review Buffer/cloud media before retrying")
        c.execute("UPDATE jobs SET status=?,error='',changed=? WHERE id=?",
                  ("pending" if row["media_url"] else "needs_source", now(), job_id))
    WAKE.set()
    return jsonify(ok=True)


@job_api.post("/<int:job_id>/delete")
def remove(job_id):
    with db() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return bad("Job not found", 404)
        if row["status"] not in ("needs_source", "pending", "failed", "published"):
            return bad("Job may still be publishing")
        if row["public_id"] or (row["posts"] != "{}" and row["status"] != "published"):
            return bad("Remote media requires manual review before deletion")
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        event(c, "Removed job " + str(job_id))
    return jsonify(ok=True)
