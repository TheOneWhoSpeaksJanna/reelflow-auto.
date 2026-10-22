"""SQLite queue and single-threaded publication worker."""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from integrations import delete_hosted_video, get_post_status, host_video, schedule_video

DATABASE = Path(os.environ.get("DATABASE_PATH", str(Path(__file__).parent / "data" / "reelflow.sqlite3")))
DATABASE.parent.mkdir(parents=True, exist_ok=True)
WAKE = threading.Event()
INTERVAL = max(30, int(os.environ.get("POLL_SECONDS", "90")))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def db():
    con = sqlite3.connect(DATABASE, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize():
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT NOT NULL UNIQUE,
            media_url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            error TEXT NOT NULL DEFAULT '',
            public_id TEXT NOT NULL DEFAULT '',
            hosted_url TEXT NOT NULL DEFAULT '',
            posts TEXT NOT NULL DEFAULT '{}',
            created TEXT NOT NULL,
            changed TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,id)")
        c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,job_id INTEGER,message TEXT,created TEXT)")
        c.execute("""UPDATE jobs SET status='review',error='Server restarted during upload.
            Check Buffer and cloud storage before retrying',changed=? WHERE status='processing'""", (now(),))


def event(c, message, job_id=None):
    c.execute("INSERT INTO events(job_id,message,created) VALUES(?,?,?)", (job_id, str(message)[:250], now()))
    c.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 250)")


def get_setting(key, default=""):
    with db() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def selected_channels():
    ids = json.loads(get_setting("channels", "[]"))
    platforms = json.loads(get_setting("platforms", "{}"))
    return [(cid, platforms.get(cid, "")) for cid in ids]


def process(row):
    job_id = row["id"]
    with db() as c:
        c.execute("UPDATE jobs SET status='processing',error='',changed=? WHERE id=?", (now(), job_id))
        event(c, "Started processing", job_id)
    attempts = 0
    pubid = ""
    try:
        channels = selected_channels()
        if not channels:
            raise RuntimeError("Choose publishing channels in Settings")
        if not os.getenv("BUFFER_API_KEY"):
            raise RuntimeError("BUFFER_API_KEY has not been set")
        pubid, hosted = host_video(row["media_url"], job_id)
        with db() as c:
            c.execute("UPDATE jobs SET public_id=?,hosted_url=?,changed=? WHERE id=?",
                      (pubid, hosted, now(), job_id))
        posts = {}
        for channel, platform in channels:
            attempts += 1
            post_id = schedule_video(channel, platform, hosted,
                                    get_setting("caption", "New video #shorts"),
                                    row["title"] or "New short video")
            posts[channel] = post_id
            with db() as c:
                c.execute("UPDATE jobs SET posts=?,changed=? WHERE id=?",
                          (json.dumps(posts), now(), job_id))
                event(c, "Added post to Buffer " + platform, job_id)
        with db() as c:
            c.execute("UPDATE jobs SET status='awaiting_publish',changed=? WHERE id=?",
                      (now(), job_id))
            event(c, "Scheduled; awaiting sent confirmation", job_id)
    except Exception as exc:
        # A network timeout might happen AFTER remote creation; never auto-retry blindly.
        state = "review" if attempts or pubid else "failed"
        with db() as c:
            c.execute("UPDATE jobs SET status=?,error=?,changed=? WHERE id=?",
                      (state, str(exc)[:350], now(), job_id))
            event(c, "Processing stopped: " + str(exc), job_id)


def cleanup(row):
    try:
        delete_hosted_video(row["public_id"])
        with db() as c:
            c.execute("""UPDATE jobs SET status='published',public_id='',hosted_url='',
                       error='',changed=? WHERE id=?""", (now(), row["id"]))
            event(c, "All posts sent; temporary media cleaned", row["id"])
        WAKE.set()
    except Exception as exc:
        with db() as c:
            c.execute("UPDATE jobs SET error=?,changed=? WHERE id=?",
                      ("Cleanup retry: " + str(exc)[:200], now(), row["id"]))


def verify(row):
    posts = json.loads(row["posts"])
    if not posts:
        with db() as c:
            c.execute("UPDATE jobs SET status='review',error=? WHERE id=?",
                      ("No Buffer post IDs were saved", row["id"]))
        return
    statuses = [get_post_status(pid) for pid in posts.values()]
    if any(s in ("error", "failed") for s in statuses):
        with db() as c:
            c.execute("UPDATE jobs SET status='review',error=?,changed=? WHERE id=?",
                      ("Buffer reports a failed post. Check Buffer manually.", now(), row["id"]))
            event(c, "A post failed; cloud media retained", row["id"])
    elif all(s == "sent" for s in statuses):
        with db() as c:
            c.execute("UPDATE jobs SET status='cleanup',changed=? WHERE id=?", (now(), row["id"]))
        cleanup(row)


def worker():
    while True:
        try:
            if get_setting("running", "0") == "1":
                with db() as c:
                    waiting = c.execute("SELECT * FROM jobs WHERE status='awaiting_publish' ORDER BY id LIMIT 1").fetchone()
                    cleaning = c.execute("SELECT * FROM jobs WHERE status='cleanup' ORDER BY id LIMIT 1").fetchone()
                    review = c.execute("SELECT id FROM jobs WHERE status='review' LIMIT 1").fetchone()
                    pending = None
                    if not waiting and not cleaning and not review:
                        pending = c.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
                if waiting:
                    try:
                        verify(waiting)
                    except Exception as exc:
                        with db() as c:
                            c.execute("UPDATE jobs SET error=?,changed=? WHERE id=?",
                                ("Status check: " + str(exc)[:220], now(), waiting["id"]))
                elif cleaning:
                    cleanup(cleaning)
                elif pending:
                    process(pending)
            WAKE.wait(INTERVAL)
            WAKE.clear()
        except Exception as exc:
            print("Worker error:", str(exc), flush=True)
            time.sleep(10)


initialize()
if os.environ.get("DISABLE_WORKER") != "1":
    threading.Thread(target=worker, name="reelflow-worker", daemon=True).start()
