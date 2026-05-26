#!/usr/bin/env python3

"""Extract DKIM public key and write DNS TXT record."""
import base64, hashlib, os, struct, sys

private_key_path = sys.argv[1]
txt_path = sys.argv[2]
selector = sys.argv[3]
domain = sys.argv[4]
algorithm = sys.argv[5]

with open(private_key_path, "rb") as f:
    pem_data = f.read()

# Decode PEM to DER
b64_data = b"".join(
    line.strip() for line in pem_data.splitlines()
    if not line.startswith(b"-----") and line.strip()
)
der = base64.b64decode(b64_data)

# Extract public key from private key via openssl CLI (reliable cross-platform)
import subprocess
result = subprocess.run(
    ["openssl", "pkey", "-pubout", "-outform", "DER"],
    input=pem_data, capture_output=True, check=True
)
pubkey_der = result.stdout

if algorithm == "ed25519":
    # Raw 32-byte public key (last 32 bytes of DER)
    pubkey_raw = pubkey_der[-32:]
    pubkey_b64 = base64.b64encode(pubkey_raw).decode()
else:
    # Full SPKI DER for RSA
    pubkey_b64 = base64.b64encode(pubkey_der).decode()

record = f'{selector}._domainkey.{domain}. IN TXT "v=DKIM1; k={algorithm}; p={pubkey_b64}"\n'

with open(txt_path, "w") as f:
    f.write(record)

print(f"OK {algorithm} {selector}")
