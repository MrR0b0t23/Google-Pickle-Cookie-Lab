# Reaching the lab from your attacker VM

The container runs on the **host**. The attacker (Kali) is a **guest VM**.
The only thing you need to get right is *which host IP Docker publishes on*.

## The rule

Docker's `ports:` mapping can bind to a specific host address:

```yaml
ports:
  - "${LAB_BIND_IP}:${LAB_PORT}:5000"
```

- `127.0.0.1` → only the host itself can reach it. The VM cannot.
- `0.0.0.0` → **everything on your Wi-Fi can reach it.** Don't do this with a
  deliberately vulnerable app.
- *the host's IP on the VM's virtual network* → exactly the VM, nothing else.
  This is what you want.

## Finding the right IP

On the host:

```bash
./scripts/host-ips.sh
```

Interfaces named `bridge*`, `vmnet*`, `vboxnet*` or `virbr*` are virtual
networks. Typical values:

| Hypervisor | Mode | Host IP |
|---|---|---|
| VMware Fusion | NAT (`vmnet8`) | `192.168.60.1`-ish (`bridge101`) |
| VMware Fusion | Host-only (`vmnet1`) | `172.16.x.1`-ish (`bridge100`) |
| UTM | Shared Network | `192.168.64.1` |
| Parallels | Shared | `10.211.55.2` |
| VirtualBox | Host-only | `192.168.56.1` |

Confirm from inside Kali:

```bash
ip route        # "default via 192.168.60.2" on VMware NAT
```

VMware's NAT gateway is `.2`; the **host** is `.1` on that subnet. So a
default route via `192.168.60.2` means you want `LAB_BIND_IP=192.168.60.1`.

Put it in `.env`:

```
LAB_BIND_IP=192.168.60.1
LAB_PORT=8888
```

Then `docker compose up -d`. Verify from Kali:

```bash
curl -I http://192.168.60.1:8888/
```

## Why the lab uses port 8888

Burp and Caido both listen on `127.0.0.1:8080` inside Kali by default. The
lab is on a *different host* (`192.168.60.1`), so `8080` would not actually
conflict — but having two unrelated things on the same port number makes
proxy history confusing to read. The lab uses **8888** to keep them
visually distinct. Change `LAB_PORT` in `.env` if you prefer something else.

## Proxy setup (in Kali)

**Burp:** use the embedded browser, or point Firefox at the
`127.0.0.1:8080` listener. **Caido:** same idea — its default listener is
also `127.0.0.1:8080`.

Then browse to `http://192.168.60.1:8888/` and confirm traffic appears in
**HTTP history** (Burp) or **Intercept/History** (Caido).

The whole challenge is plain HTTP, so you don't need to install a CA
certificate.

You'll lean on two features:

- **Repeater** (Burp) / **Replay** (Caido) — to resend `/auth/callback`
  with modified cookies, which is most of stages 2 and 3.
- **Decoder** (Burp) / **Inspector** (Caido) — a fast way to base64-decode
  the cookie before you commit to writing a script.

Burp is genuinely the nicest way to do this lab: you'll want **Repeater** to
replay `/auth/callback` with modified cookies, and the **Decoder** tab is a
quick way to look at base64 before you write any code.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `curl` from Kali times out | `LAB_BIND_IP` is `127.0.0.1`; set it to the bridge IP and `docker compose up -d` |
| "port is already allocated" | Something else uses `LAB_PORT`; change it in `.env` |
| Works on host, not in VM | Check the VM is on the same virtual network you bound to (`ip route` in Kali) |
| macOS firewall prompt | Allow Docker to accept incoming connections |
