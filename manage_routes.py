from flask import Blueprint, jsonify, request
import json
import os
from store import WAKE, get_setting, set_setting, selected_channels
from integrations import list_channels

manage_api = Blueprint("manage_api", __name__, url_prefix="/api")

@manage_api.get("/channels")
def channels():
    try:
        return jsonify(ok=True, channels=list_channels())
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 502

@manage_api.post("/settings")
def settings():
    data = request.get_json(silent=True) or {}
    ids = data.get("channels", [])
    platforms = data.get("platforms", {})
    if not isinstance(ids, list) or len(ids)>3 or not isinstance(platforms,dict):
        return jsonify(ok=False,error="Choose up to three channels"),400
    if not all(isinstance(i,str) and platforms.get(i) in ("youtube","tiktok","instagram") for i in ids):
        return jsonify(ok=False,error="Invalid channels"),400
    set_setting("channels",json.dumps(ids))
    set_setting("platforms",json.dumps({i:platforms[i] for i in ids}))
    set_setting("caption",str(data.get("caption",""))[:850])
    return jsonify(ok=True)

@manage_api.post("/control")
def control():
    action=(request.get_json(silent=True) or {}).get("action")
    if action not in ("start","pause"):
        return jsonify(ok=False,error="Invalid action"),400
    if action=="start" and (not os.getenv("BUFFER_API_KEY") or not selected_channels()):
        return jsonify(ok=False,error="Configure Buffer channels first"),400
    set_setting("running","1" if action=="start" else "0")
    WAKE.set()
    return jsonify(ok=True)
