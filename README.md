# Pickled Cookie Lab 🍪

A self-contained web CTF that recreates a real class of vulnerability: a
**Flask session cookie that leaks its own signing key and feeds a
`pickle.loads()`**, turning cookie forgery into unauthenticated remote code
execution.

You attack a fictional docs portal ("Nimbus Developers") running in Docker,
using your own proxy (Burp Suite or Caido) and a bit of Python. Three flags,
three stages, and a guided track that teaches the *thinking*, not just the
commands.

> ⚠️ **This app is intentionally vulnerable.** Run it only on a machine and
> network you control. Never expose it to the internet or a shared network.
> See [Safety](#safety--scope).

---

## What you'll learn

The stages mirror how a real finding unfolds, one small observation at a time:

| Stage | Flag | Skill |
|---|---|---|
| **1. Recon** | `FLAG{recon_…}` | Notice an oversized cookie, decode an *unencrypted* Flask session, and recognize a pickle with secrets inside it |
| **2. Forge** | `FLAG{forge_…}` | Test a leaked credential against other secrets, re-sign a session, and become an admin |
| **3. RCE** | `FLAG{rce_…}` | Find a deserialization sink, prove execution safely, then get output back from a blind context |

Along the way: why *signed* isn't *encrypted*, why credential reuse chains
vulnerabilities together, why order of operations is a bug class of its own,
and how to demonstrate impact without causing any.

## Requirements

**Host (runs the target):** Docker with Compose v2.

**Attacker machine:** a browser, an intercepting proxy
([Burp Suite](https://portswigger.net/burp) or [Caido](https://caido.io)), and
Python 3.9+ with `flask` and `requests` for stages 2 and 3.

The target and attacker can be the same machine, or, as this lab was built,
a Docker host with a separate Kali VM. See
[docs/NETWORKING.md](docs/NETWORKING.md) for VM setups.

## Quick start

```bash
git clone https://github.com/<you>/pickled-cookie-lab.git
cd pickled-cookie-lab

cp .env.example .env
./scripts/host-ips.sh        # lists IPs your VM can reach
# edit .env and set LAB_BIND_IP (leave 127.0.0.1 if attacking from the same machine)

docker compose up -d --build
```

Then browse to `http://<LAB_BIND_IP>:8888/`.

```
  Attacker VM ──HTTP / proxy──►  host:8888  ──►  Docker container
   (Kali)                        (bound to one interface only)
```

`LAB_BIND_IP` controls who can reach the lab. `127.0.0.1` means only the host
itself. The host's address on your VM's virtual network means only that VM.
**Do not use `0.0.0.0`.**

The default port is **8888**, deliberately not 8080, so it doesn't share a
number with Burp's and Caido's default listeners in your proxy history.

### Handy commands

```bash
make up        # build and start
make down      # stop and remove
make rebuild   # re-roll all secrets and flags, then start
make logs      # follow container logs
make ips       # list candidate LAB_BIND_IP values
```

Secrets and flags are generated **at build time**, so every build has its own
and nothing sensitive lives in this repository. Rebuild whenever you want a
fresh instance.

## How to play — pick a track

Choose before you start. Dropping to an easier track mid-way is fine. The
reverse isn't, because you can't un-read a spoiler.

### 🔍 Challenge: figure it out yourself

[docs/CHALLENGE.md](docs/CHALLENGE.md) gives you a scope, a goal, and
nothing else. If you get stuck, [hints/](hints/) has one file per stage,
written so you can read a paragraph and stop.

*Best if you've done a few web CTFs and want the real discovery experience.*

### 🧭 Guided: learn the method

[docs/GUIDED.md](docs/GUIDED.md) walks every step as **look → predict →
check**. You commit to a prediction before looking up the answer, and every
step ends with *why it matters*, the part that transfers to targets that
aren't this one. Answers sit at the end of each stage, so you control when
you see them.

*Best if you're newer to this, or you want the reasoning rather than just the
flags.*

### 📖 Write-up: read the whole thing

[docs/WRITEUP.md](docs/WRITEUP.md) is the complete analysis, and
[solutions/solve.py](solutions/solve.py) is a working exploit that solves
all three stages against a fresh build.

*Best for review after you've played, or if you're here for the bug class
rather than the practice.*

## Project layout

```
app/          the vulnerable Flask app and its Dockerfile
docs/         CHALLENGE, GUIDED, WRITEUP, NETWORKING, SECURITY
hints/        graduated hints, one file per stage
solutions/    reference solver (spoilers)
scripts/      host-ips.sh: find the IP your VM can reach
```

## Safety & scope

Exploiting this lab gives you code execution **inside the container**. It's
configured to keep that boring:

- runs as an unprivileged user, on a read-only root filesystem
- all Linux capabilities dropped, `no-new-privileges` set
- memory, CPU and process limits applied
- the only writable paths are two small tmpfs mounts

Be clear about what this is *not*. It is a speed bump, not a security
boundary. Containers share a kernel with the host, and **outbound network
access is not blocked**, so code running in the container can reach the
internet. Don't run it next to anything you care about, and don't put it on
a shared or public network.

The techniques here are the same ones used in real assessments. Use them
only against systems you own or have **written** authorization to test. More
in [docs/SECURITY.md](docs/SECURITY.md).

## Credit

The vulnerability class is modelled on Simon Koeck's public write-up of a
Flask session/pickle RCE in a large docs platform:
[google-devsite-flask-session-pickle-rce](https://simonkoeck.com/writeups/google-devsite-flask-session-pickle-rce).
Go read it, since it covers a real disclosure and fix timeline that this lab
doesn't.

This lab is independent, original code with an invented target ("Nimbus").
It contains no code, data, or secrets from any real system, and isn't
affiliated with or endorsed by the author or any company mentioned.

## License

MIT, see [LICENSE](LICENSE). Educational use and forks welcome.
