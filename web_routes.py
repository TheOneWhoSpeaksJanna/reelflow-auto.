"""ReelFlow dashboard status endpoint."""
import json
import os
from flask import Blueprint, jsonify
from integrations import cloud_configured
from store import db, get_setting

dashboard_api = Blueprint("dashboard_api", __name__, url_prefix="/api")


@dashboard_api.get("/state")
def state():
    with db() as c:
        jobs = [dict(row) for row in c.execute(
            "SELECT id,source_url,media_url,title,status,error,posts,created,changed FROM jobs ORDER BY id DESC LIMIT 500")]
        events = [dict(row) for row in c.execute(
            "SELECT job_id,message,created FROM events ORDER BY id DESC LIMIT 25")]
        counts = {row["status"]: row["total"] for row in c.execute(
            "SELECT status,count(*) AS total FROM jobs GROUP BY status")}
    for job in jobs:
        job["post_count"] = len(json.loads(job.pop("posts")))
    return jsonify(ok=True, jobs=jobs, events=events, counts=counts,
                   running=get_setting("running", "0") == "1",
                   channels=json.loads(get_setting("channels", "[]")),
                   caption=get_setting("caption", "New video #shorts"),
                   configured={"buffer": bool(os.getenv("BUFFER_API_KEY")),
                               "cloudinary": cloud_configured()})
