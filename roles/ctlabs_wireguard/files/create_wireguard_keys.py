#!/usr/bin/env python3
# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_wireguard/files/create_wireguard_keys.py
# Description : generate WireGuard X25519 keypairs for server & client
# ------------------------------------------------------------------------------

import base64
import os
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519


def generate_keypair(target_dir, prefix):
    key_path = os.path.join(target_dir, f"{prefix}.key")
    pub_path = os.path.join(target_dir, f"{prefix}.pub")

    if os.path.isfile(key_path) and os.path.isfile(pub_path):
        return

    priv = x25519.X25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    with open(key_path, "w") as f:
        f.write(base64.b64encode(priv_bytes).decode("ascii") + "\n")
    with open(pub_path, "w") as f:
        f.write(base64.b64encode(pub_bytes).decode("ascii") + "\n")

    os.chmod(key_path, 0o600)
    os.chmod(pub_path, 0o644)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <target_dir>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    os.makedirs(target_dir, mode=0o700, exist_ok=True)
    generate_keypair(target_dir, "server")
    generate_keypair(target_dir, "client")


if __name__ == "__main__":
    main()
