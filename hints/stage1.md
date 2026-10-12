# Stage 1 hints — Recon

Read one at a time.

---

**Hint 1.** You don't need to finish signing in. Just *starting* the flow is
enough. What does the server give you on the very first request?

---

**Hint 2.** Look at the size of the session cookie. A CSRF token and a return
URL is maybe 60 bytes of data. Why is this one over 500?

---

**Hint 3.** Flask session cookies are signed, not encrypted. Anyone holding
one can read it. The format is:

```
<payload>.<timestamp>.<signature>
```

each part base64url-encoded. If the whole thing starts with a `.`, the
payload is zlib-compressed — strip the dot, base64-decode, `zlib.decompress`.

---

**Hint 4.** The decoded payload is JSON. Flask tags non-JSON types: a value
like `{" b": "gASV..."}` means "these are bytes, base64-encoded."

---

**Hint 5.** Decode those bytes. `gASV` base64-decodes to `\x80\x04\x95` —
that's a pickle protocol 4 header. The server is storing a **pickled Python
object in your cookie**.

---

**Hint 6.** Don't `pickle.loads()` it — that executes it. Use `pickletools`
to read it safely:

```python
import pickletools
pickletools.dis(blob)                       # human-readable opcodes
[a for _, a, _ in pickletools.genops(blob)] # just the values
```

The flag is one of the strings. So is something considerably more
interesting — note the field names as you read.
