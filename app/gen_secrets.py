"""Generate per-build secrets and flags.

Runs once during `docker build`, so every player who builds the lab gets
their own OAuth client secret and their own flag values. Nothing secret is
committed to the repository.

Usage: python gen_secrets.py <config_dir> <flag_dir>
"""
import json
import os
import secrets
import sys


def flag(stage):
    return f"FLAG{{{stage}_{secrets.token_hex(12)}}}"


def main():
    config_dir, flag_dir = sys.argv[1], sys.argv[2]
    os.makedirs(config_dir, exist_ok=True)

    config = {
        "client_id": f"{secrets.randbelow(10**12):012d}-docs.apps.nimbuscloud.dev",
        "client_secret": "NMBS-" + secrets.token_urlsafe(24),
        "flag_recon": flag("recon"),
        "flag_forge": flag("forge"),
    }
    config_path = os.path.join(config_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(config_path, 0o444)

    # The final flag lives at an unguessable path in the filesystem root,
    # so reading it needs real command execution rather than a lucky guess.
    flag_path = os.path.join(flag_dir, f"flag_{secrets.token_hex(8)}.txt")
    with open(flag_path, "w") as f:
        f.write(flag("rce") + "\n")
    os.chmod(flag_path, 0o444)


if __name__ == "__main__":
    main()
