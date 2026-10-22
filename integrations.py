"""Official Buffer API and temporary Cloudinary media integration."""
import hashlib
import ipaddress
import json
import os
import re
import time
from urllib.parse import urlsplit
import requests

SESSION = requests.Session()
BUFFER_URL = "https://api.buffer.com"
VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".webm")


def validate_url(url):
    if not isinstance(url, str) or len(url) > 1600:
        raise ValueError("Invalid URL")
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("A public HTTPS URL is required")
    if parsed.port not in (None, 443) or host.endswith(".local") or host == "localhost":
        raise ValueError("Local addresses are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if re.fullmatch(r"[0-9a-f:.]+", host):
            raise ValueError("Invalid network address")
    else:
        if not address.is_global:
            raise ValueError("Private addresses are not allowed")
    return url


def direct_video(url):
    try:
        validate_url(url)
        return urlsplit(url).path.lower().endswith(VIDEO_SUFFIXES)
    except ValueError:
        return False


def buffer_query(query, variables=None):
    key = os.environ.get("BUFFER_API_KEY", "")
    if not key:
        raise RuntimeError("Set BUFFER_API_KEY in Wispbyte Startup")
    response = SESSION.post(BUFFER_URL, json={"query": query, "variables": variables or {}},
        headers={"Authorization": "Bearer " + key}, timeout=(10, 35))
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"][0].get("message", "Buffer request failed"))
    return data["data"]


def list_channels():
    result = []
    query = "query { account { organizations { id name } } }"
    organizations = buffer_query(query)["account"]["organizations"]
    for org in organizations:
        q = "query { channels(input: { organizationId: " + json.dumps(org["id"]) + " }) { id name displayName service isQueuePaused } }"
        for channel in buffer_query(q)["channels"]:
            channel["organizationName"] = org["name"]
            result.append(channel)
    return result


def schedule_video(channel_id, platform, video_url, caption, title):
    payload = {"channelId": channel_id, "schedulingType": "automatic", "mode": "addToQueue",
        "text": caption[:850], "assets": [{"video": {"url": video_url}}]}
    if platform == "youtube":
        payload["metadata"] = {"youtube": {"title": title[:100], "categoryId": "24"}}
    query = """mutation($input:CreatePostInput!){
        createPost(input:$input){
            ... on PostActionSuccess { post { id dueAt } }
            ... on MutationError { message }
        }
    }"""
    data = buffer_query(query, {"input": payload})["createPost"]
    post = data.get("post")
    if not post:
        raise RuntimeError("Buffer: " + data.get("message", "Failed to create post"))
    return post["id"]


def get_post_status(post_id):
    query = "query { post(input: { id: " + json.dumps(post_id) + " }) { id status } }"
    post = buffer_query(query).get("post")
    if not post:
        raise RuntimeError("Buffer post not found; check it manually")
    return str(post["status"]).lower()


def cloud_configured():
    return all(os.environ.get(k) for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"))


def sign_cloud(fields):
    secret = os.environ["CLOUDINARY_API_SECRET"]
    params = "&".join(k + "=" + str(fields[k]) for k in sorted(fields))
    return hashlib.sha1((params + secret).encode("utf-8")).hexdigest()


def cloud_url(path):
    return "https://api.cloudinary.com/v1_1/" + os.environ["CLOUDINARY_CLOUD_NAME"] + "/video/" + path


def host_video(url, job_id):
    """Copy directly between cloud providers; do not store source files on Wispbyte disk."""
    if not cloud_configured():
        return "", url
    payload = {"public_id": "reelflow/job_" + str(job_id),
        "timestamp": int(time.time()), "overwrite": "false"}
    payload["signature"] = sign_cloud(payload)
    payload["api_key"] = os.environ["CLOUDINARY_API_KEY"]
    payload["file"] = url
    response = SESSION.post(cloud_url("upload"), data=payload, timeout=(15, 120))
    response.raise_for_status()
    data = response.json()
    return data["public_id"], data["secure_url"]


def delete_hosted_video(public_id):
    """Delete cloud media only when all platforms report sent."""
    if not public_id:
        return
    payload = {"public_id": public_id, "timestamp": int(time.time()), "invalidate": "true"}
    payload["signature"] = sign_cloud(payload)
    payload["api_key"] = os.environ["CLOUDINARY_API_KEY"]
    response = SESSION.post(cloud_url("destroy"), data=payload, timeout=(10, 35))
    response.raise_for_status()
    if response.json().get("result") not in ("ok", "not found"):
        raise RuntimeError("Cloudinary deletion not confirmed")
