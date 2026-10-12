# Stage 3 hints — Remote code execution

---

**Hint 1.** Stage 1 told you the server *stores* a pickle in the session.
Something has to turn it back into an object. Which endpoint consumes the
flow? What does it have to do to it first?

---

**Hint 2.** `/auth/callback` looks up the flow by the CSRF token in your
session and unpickles it. You control the session, so you control **both**
the key it looks up and the bytes it unpickles. You never need a valid
`code`, `state`, or redirect from the IdP — the unpickle happens *before* any
of that is checked.

---

**Hint 3.** You don't hand-craft pickle opcodes. Define a class with
`__reduce__`, which returns `(callable, args_tuple)`. On load, pickle calls
it:

```python
class Boom:
    def __reduce__(self):
        return (some_function, ("argument",))
```

Both the callable and the argument must be importable/representable on the
*server* — stick to the standard library.

---

**Hint 4.** Prove it harmlessly first. Make `__reduce__` return
`(time.sleep, (5,))`, send it, and time the response. Then vary the number.
If the response time tracks your value, the server is calling your function.

Run the controls too, so you can rule out a coincidentally slow endpoint:
no cookie, a tampered signature, a valid signature with no flow entry. Each
should fail differently and fast.

---

**Hint 5.** Now swap the gadget for something that runs a command —
`os.system` is the blunt one. But the callback returns an error page either
way, so you won't see stdout. You need an **out-of-band** way to read output.

---

**Hint 6.** The container is read-only... except for one directory the app
writes to at startup, which also happens to be served over HTTP. The
changelog mentions it. Redirect your command's output there, then fetch it.

```
(your command) > /app/static/cache/note.txt 2>&1
```

then `GET /static/cache/note.txt`.

---

**Hint 7.** The flag file is in `/` with a random name. `ls /` first, then
read it. Clean up after yourself — good habit, and it keeps the lab tidy for
your next run.
