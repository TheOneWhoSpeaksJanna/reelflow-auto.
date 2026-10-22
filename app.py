"""ReelFlow dashboard entrypoint. Deploy with python app.py."""
import os
import secrets
from flask import Flask, jsonify, render_template, request, session, redirect
from web_routes import dashboard_api
from manage_routes import manage_api

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                  SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "1") == "1",
                  MAX_CONTENT_LENGTH=450000)


@app.before_request
def protect_api():
    if request.path.startswith("/api/"):
        if not os.environ.get("APP_PASSWORD"):
            return jsonify(ok=False, error="Set APP_PASSWORD on Wispbyte first"), 503
        if not session.get("login"):
            return jsonify(ok=False, error="Login required"), 401
        if request.method == "POST" and not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", ""), session.get("csrf", "_")):
            return jsonify(ok=False, error="Refresh your session"), 403


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    if not os.environ.get("APP_PASSWORD"):
        return render_template("setup.html"), 503
    if not session.get("login"):
        return render_template("login.html")
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return render_template("index.html", csrf=session["csrf"])


@app.post("/login")
def login():
    valid = os.environ.get("APP_PASSWORD", "")
    if valid and secrets.compare_digest(request.form.get("password", ""), valid):
        session.clear()
        session["login"] = True
        session["csrf"] = secrets.token_urlsafe(32)
        return redirect("/")
    return render_template("login.html", error="Incorrect password"), 401


@app.post("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.get("/healthz")
def health():
    return jsonify(status="ok")


app.register_blueprint(dashboard_api)
app.register_blueprint(manage_api)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("SERVER_PORT", "3000")))
    app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)
