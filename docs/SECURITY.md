# Safety notes

## This repository contains a deliberately vulnerable application

`app/` has an unauthenticated remote code execution vulnerability **by
design**. It exists to be exploited, by you, on your own machine.

## Running it safely

- **Bind it to a private interface.** `.env.example` defaults to
  `127.0.0.1`. Use the host IP of your VM's virtual network so only the
  attacker VM can reach it. Never `0.0.0.0` on a network you share.
- **Don't deploy it anywhere public.** No cloud VM with a public IP, no port
  forward, no tunnel.
- **Don't reuse the image.** It's a lab, not a base image.

## What the container does to limit damage

Exploiting this lab gives you code execution *inside the container*. It is
configured to make that boring:

| Control | Effect |
|---|---|
| non-root user (`docs`, uid 1000) | no writes to app code |
| `read_only: true` | root filesystem immutable |
| `cap_drop: ALL` | no Linux capabilities |
| `no-new-privileges` | no setuid escalation |
| `pids_limit`, `mem_limit`, `cpus` | fork bombs and runaway loops are contained |
| tmpfs `/tmp` and cache dir | the only writable paths, both small |

This is a speed bump, not a sandbox boundary. Container escape is out of
scope for the lab, but don't run it next to anything you care about.

## Secrets and flags

Generated at **build time** by `app/gen_secrets.py` and never committed.
Every build produces different values, so publishing this repo doesn't
publish answers. `.gitignore` excludes `.env` and generated config.

## Responsible use

The techniques here — reading signed cookies, forging sessions, pickle
deserialization — are the same ones used in real assessments. Use them only
against systems you own or have **written** authorization to test. Bug
bounty programs define scope in writing for a reason; stay inside it, and
prove impact with the least invasive proof that works.

## Credit

The vulnerability class is modelled on a publicly disclosed Flask
session/pickle RCE write-up. The application here is original, fictional
code written for teaching; it is not derived from, and does not reproduce,
any real system.
