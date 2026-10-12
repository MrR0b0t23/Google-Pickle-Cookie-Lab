"""Nimbus Developers: documentation portal (deliberately vulnerable lab)."""
import json
import logging
import os
import pickle
import secrets
from urllib.parse import urlencode

from flask import (Flask, abort, redirect, render_template, request, session,
                   url_for)

from oauth_flow import OAuthFlow, issue_code

CONFIG_PATH = os.environ.get("LAB_CONFIG", "/opt/lab/config.json")
CACHE_DIR = os.environ.get("LAB_CACHE_DIR",
                           os.path.join(os.path.dirname(__file__), "static", "cache"))

with open(CONFIG_PATH) as f:
    settings = json.load(f)

app = Flask(__name__)
# One less secret to manage in the deployment: the OAuth client secret is
# already random and private, so it doubles as the session signing key.
app.config["SECRET_KEY"] = settings["client_secret"]
app.config["SESSION_COOKIE_NAME"] = "nimbus_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
log = logging.getLogger("nimbus")

DOCS = {
    "getting-started": {
        "title": "Getting started",
        "summary": "Create a project and make your first API call.",
        "body": [
            "Every Nimbus project starts in the console. Create a project, "
            "enable the Storage API, and download a service account key.",
            "Install the SDK with <code>pip install nimbus-sdk</code>, then "
            "call <code>nimbus.storage.list_buckets()</code> to confirm your "
            "credentials work.",
        ],
    },
    "authentication": {
        "title": "Signing in to the docs",
        "summary": "How the docs portal signs you in with your Nimbus Account.",
        "body": [
            "Signing in lets you save pages, track quickstarts, and see "
            "content for your role. The portal is a standard OAuth 2.0 "
            "client of Nimbus Accounts.",
            "When you click <em>Sign in</em>, the portal creates the OAuth "
            "flow and sends you to Nimbus Accounts. After you approve, "
            "Nimbus Accounts redirects you to <code>/auth/callback</code> "
            "with an authorization code, which the portal exchanges for "
            "your profile.",
            "The portal runs on stateless pods behind a load balancer, so "
            "it keeps no server-side session store. Everything it needs "
            "between requests lives in your session cookie, which is "
            "signed so it can't be tampered with.",
        ],
    },
    "storage-quickstart": {
        "title": "Storage quickstart",
        "summary": "Upload, list and download objects.",
        "body": [
            "Buckets hold objects. Object names are flat, but a slash in a "
            "name is shown as a folder in the console.",
            "Use <code>bucket.upload(path)</code> to upload and "
            "<code>bucket.download(name)</code> to fetch an object back.",
        ],
    },
    "changelog": {
        "title": "Docs portal changelog",
        "summary": "What changed in the portal itself.",
        "body": [
            "<strong>v2.4</strong>: Added the admin console for docs "
            "editors.",
            "<strong>v2.3</strong>: Moved to stateless pods. OAuth flow "
            "state is now carried in the session cookie, so sign-in works "
            "no matter which pod serves the callback.",
            "<strong>v2.2</strong>: Search index is now pre-built at "
            "startup and served from <code>/static/cache/</code>.",
            "<strong>v2.1</strong>: Moved the portal to Flask.",
        ],
    },
}


def build_search_index():
    """Pre-build the client-side search index at startup."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    index = [{"slug": slug, "title": d["title"], "summary": d["summary"]}
             for slug, d in DOCS.items()]
    with open(os.path.join(CACHE_DIR, "search-index.json"), "w") as f:
        json.dump(index, f)


build_search_index()


@app.context_processor
def inject_user():
    return {"user": session.get("user")}


@app.route("/")
def index():
    return render_template("index.html", docs=DOCS)


@app.route("/docs/<slug>")
def doc(slug):
    page = DOCS.get(slug) or abort(404)
    return render_template("doc.html", page=page)


@app.route("/robots.txt")
def robots():
    return ("User-agent: *\nDisallow: /admin\nDisallow: /auth/\n",
            200, {"Content-Type": "text/plain"})


# --- Sign-in (OAuth client side) -----------------------------------------

@app.route("/auth/login")
def auth_login():
    next_url = request.args.get("next", "/")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"

    csrf = secrets.token_urlsafe(16)
    flow = OAuthFlow(
        client_id=settings["client_id"],
        client_secret=settings["client_secret"],
        redirect_uri=url_for("auth_callback"),
        scopes=["openid", "email", "profile"],
        state=csrf,
        next_url=next_url,
        debug_note=settings["flag_recon"],
    )
    session["csrf_token"] = csrf
    session["oauth_flows"] = {csrf: pickle.dumps(flow)}

    query = urlencode({
        "client_id": flow.client_id,
        "redirect_uri": flow.redirect_uri,
        "response_type": "code",
        "scope": " ".join(flow.scopes),
        "state": csrf,
    })
    return redirect(f"{url_for('idp_authorize')}?{query}")


@app.route("/auth/callback")
def auth_callback():
    csrf = session.get("csrf_token")
    blob = session.get("oauth_flows", {}).get(csrf)
    if blob is None:
        return render_template("error.html",
                               message="Your sign-in session expired. Please try again."), 400

    try:
        flow = pickle.loads(blob)
        userinfo = flow.exchange_code(request.args.get("code", ""))
    except Exception:
        log.exception("sign-in failed")
        return render_template("error.html",
                               message="Sign-in failed. Please try again."), 400

    session.pop("oauth_flows", None)
    session.pop("csrf_token", None)
    session["user"] = {
        "email": userinfo["email"],
        "name": userinfo["name"],
        "role": "viewer",
    }
    return redirect(flow.next_url)


@app.route("/auth/logout")
def auth_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/account")
def account():
    if not session.get("user"):
        return redirect(url_for("auth_login", next="/account"))
    return render_template("account.html")


@app.route("/admin")
def admin():
    user = session.get("user")
    if not user:
        return redirect(url_for("auth_login", next="/admin"))
    if user.get("role") != "admin":
        return render_template(
            "error.html",
            message=f"Admin console requires role 'admin' (your role: '{user.get('role')}')."), 403
    return render_template("admin.html", flag=settings["flag_forge"])


# --- Nimbus Accounts (mock identity provider) ---------------------------
# In real life this is a different service. It lives in the same app here
# so the lab is a single container.

@app.route("/accounts/o/oauth2/auth", methods=["GET", "POST"])
def idp_authorize():
    params = request.values
    redirect_uri = params.get("redirect_uri", "")
    if params.get("client_id") != settings["client_id"] or not redirect_uri.startswith("/"):
        return render_template("error.html", message="Invalid OAuth client."), 400

    if request.method == "GET":
        return render_template("idp_login.html", params=params)

    email = params.get("email", "").strip() or "guest@example.com"
    name = email.split("@")[0]
    code = issue_code(settings["client_id"], settings["client_secret"], email, name)
    query = urlencode({"code": code, "state": params.get("state", "")})
    return redirect(f"{redirect_uri}?{query}")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
