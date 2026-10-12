# Nimbus Developers — player brief

> **Scope:** `http://<LAB_BIND_IP>:8888/` and nothing else.
> **Goal:** three flags, format `FLAG{stage_hex}`.
> **Rules of engagement:** no brute force, no DoS. Everything needed is
> reachable without an account. If you find yourself writing a wordlist,
> you've left the intended path.

---

## The brief

Nimbus Cloud has asked you to assess their public developer documentation
portal. It's a marketing-adjacent site: docs, a search box, and a sign-in
button that uses the company's own OAuth provider ("Nimbus Accounts"). The
client insists it's "just static docs with a login" and low risk.

There is an admin console at `/admin` for docs editors. The client would like
to know whether an outsider can reach it.

## Stage 1 — Recon

Sign-in flows are a good place to start, because they create state before you
have an account. Walk the flow and *look at what the server hands you*, not
just where it sends you.

**You're done when:** you've found something in your own browser storage that
should never have left the server. `FLAG{recon_...}`

## Stage 2 — Become an admin

`/admin` requires `role: admin`. You cannot register as one.

**You're done when:** you can load `/admin` and read `FLAG{forge_...}`.

## Stage 3 — Code execution

The portal is Python. Somewhere in the sign-in flow, the server turns data
you control back into a live Python object.

Before you run a command, **prove execution safely** — make the server waste
a measurable amount of time and show the delay tracks a value you chose.
That's how you demonstrate impact in a real engagement without touching
production data.

**You're done when:** you've read the release flag from a file in the
container's filesystem root. `FLAG{rce_...}`

---

## Useful background

- Flask session cookies are **signed, not encrypted**.
- Python's `pickle` module reconstructs arbitrary objects, which means
  unpickling attacker-controlled bytes is equivalent to running their code.
- You don't need to *write* a pickle by hand. `__reduce__` is the supported
  way to say "when you load me, call this function with these arguments."

## Tooling

Nothing exotic: a browser, Burp (Repeater + Decoder), and Python with
`flask` and `requests` installed. `pickletools` ships with Python and lets
you *read* a pickle without executing it — a habit worth building.

## If you get stuck

In order of how much they give away:

1. **[hints/](../hints/)** — one file per stage, one nudge per paragraph.
   Read the first paragraph, go try it, come back only if you need to.
2. **[GUIDED.md](GUIDED.md)** — the full method, structured as
   predict-then-reveal. Switching here isn't giving up; it's the track that
   explains *why* each step follows from the last.
3. **[WRITEUP.md](WRITEUP.md)** — complete spoilers.

Being stuck for a while is the part where the learning happens. But being
stuck for an hour on the same wall isn't learning, it's just stuck — take
the hint.
