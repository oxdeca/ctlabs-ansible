#!/usr/bin/env python3
"""
Export Vault *configuration* to a ctlabs_vault_setup fact file.

Dumps secrets engines, auth methods, ACL policies, userpass users (names +
current policies only), approle roles (incl. secret_id_ttl /
secret_id_bound_cidrs / token_ttl) and jwt/oidc mount config + roles from a
live Vault, so a brand-new host can reproduce the same setup declaratively
(tasks/bootstrap.yml) after a fresh init -- WITHOUT the seal keys
(config-restore, not storage-restore).

By design it does NOT export KV/secret data, and userpass passwords cannot
be read back by Vault at all, so user entries are exported WITHOUT
passwords -- add them to the fact file manually.

Output is the local-fact JSON expected at
/etc/ansible/facts.d/ctlabs_vault_setup.fact (-> ctg_facts.ctlabs_vault_setup).
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


def build_context(args):
    if args.insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if args.ca_cert:
        return ssl.create_default_context(cafile=args.ca_cert)
    return ssl.create_default_context()


def api(addr, token, path, method="GET", body=None, ctx=None):
    url = addr.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Vault-Token", token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = ""
        raise SystemExit("Vault API error {0} on {1} {2}: {3}".format(e.code, method, path, detail))


def export(addr, token, ctx):
    out = {}

    #
    # Secrets Engines
    #
    mounts = api(addr, token, "/v1/sys/mounts", ctx=ctx) or {}
    engines = []
    for path, info in sorted((mounts.get("data") or {}).items()):
        p = path.rstrip("/")
        if p in ("sys", "identity"):
            continue
        engines.append(
            {
                "path": p,
                "type": info.get("type", ""),
                "description": info.get("description", ""),
                "options": info.get("options") or {},
            }
        )
    if engines:
        out["engines"] = engines

    #
    # Auth Methods
    #
    auths = api(addr, token, "/v1/sys/auth", ctx=ctx) or {}
    auth_methods = []
    for path, info in sorted((auths.get("data") or {}).items()):
        p = path.rstrip("/")
        if p == "token":
            continue
        auth_methods.append(
            {
                "path": p,
                "type": info.get("type", ""),
                "description": info.get("description", ""),
            }
        )
    if auth_methods:
        out["auth"] = auth_methods

    #
    # ACL Policies
    #
    pol = api(addr, token, "/v1/sys/policies/acl?list=true", ctx=ctx) or {}
    policies = []
    for name in sorted((pol.get("data") or {}).get("keys", [])):
        if name in ("default", "root"):
            continue
        p = api(addr, token, "/v1/sys/policies/acl/" + urllib.parse.quote(name), ctx=ctx) or {}
        code = ((p.get("data") or {}).get("policy") or "").rstrip()
        policies.append({"name": name, "policy": code, "source": "inline"})
    if policies:
        out["policies"] = policies

    #
    # Userpass Users (names + policies only; passwords are not readable)
    #
    users = []
    for a in [m for m in auth_methods if m["type"] == "userpass"]:
        path = a["path"]
        ul = api(addr, token, "/v1/auth/{0}/users?list=true".format(path), ctx=ctx) or {}
        for name in sorted((ul.get("data") or {}).get("keys", [])):
            u = api(addr, token, "/v1/auth/{0}/users/{1}".format(path, urllib.parse.quote(name)), ctx=ctx) or {}
            users.append(
                {
                    "username": name,
                    "policies": (u.get("data") or {}).get("policies") or [],
                    "auth_path": path,
                }
            )
    if users:
        out["users"] = users

    #
    # AppRole Roles
    #
    roles = []
    for a in [m for m in auth_methods if m["type"] == "approle"]:
        path = a["path"]
        rl = api(addr, token, "/v1/auth/{0}/role?list=true".format(path), ctx=ctx) or {}
        for name in sorted((rl.get("data") or {}).get("keys", [])):
            r = api(addr, token, "/v1/auth/{0}/role/{1}".format(path, urllib.parse.quote(name)), ctx=ctx) or {}
            d = r.get("data") or {}
            role = {"name": name, "auth_path": path}
            for k in (
                "token_policies",
                "token_ttl",
                "token_max_ttl",
                "secret_id_ttl",
                "secret_id_num_uses",
                "secret_id_bound_cidrs",
                "bind_secret_id",
            ):
                if k in d:
                    role[k] = d[k]
            roles.append(role)
    if roles:
        out["approle_roles"] = roles

    #
    # JWT / OIDC
    #
    for a in [m for m in auth_methods if m["type"] == "jwt"]:
        path = a["path"]
        cfg = api(addr, token, "/v1/auth/{0}/config".format(path), ctx=ctx) or {}
        d = cfg.get("data") or {}
        j = {"mount": path}
        if d.get("oidc_discovery_url"):
            j["discovery_url"] = d["oidc_discovery_url"]
        if d.get("default_role"):
            j["default_role"] = d["default_role"]
        rl = api(addr, token, "/v1/auth/{0}/role?list=true".format(path), ctx=ctx) or {}
        jwt_roles = []
        for name in sorted((rl.get("data") or {}).get("keys", [])):
            r = api(addr, token, "/v1/auth/{0}/role/{1}".format(path, urllib.parse.quote(name)), ctx=ctx) or {}
            rd = r.get("data") or {}
            role = {"name": name}
            for k in ("bound_audiences", "user_claim", "claim_mappings", "token_policies"):
                if k in rd:
                    role[k] = rd[k]
            jwt_roles.append(role)
        if jwt_roles:
            j["roles"] = jwt_roles
        out["jwt"] = j

    return out


def main():
    parser = argparse.ArgumentParser(
        description="Export Vault configuration to a ctlabs_vault_setup fact file (config-restore, no secret data)"
    )
    parser.add_argument("--addr", default=os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200"), help="Vault address (default VAULT_ADDR env or https://127.0.0.1:8200)")
    parser.add_argument("--token", default=os.environ.get("VAULT_TOKEN"), help="privileged Vault token (default VAULT_TOKEN env)")
    parser.add_argument("--out", help="write the fact JSON to this file (default: stdout; e.g. /etc/ansible/facts.d/ctlabs_vault_setup.fact)")
    parser.add_argument("--insecure", action="store_true", help="skip TLS certificate verification (self-signed lab CA)")
    parser.add_argument("--ca-cert", help="CA bundle to verify the Vault TLS cert (e.g. /etc/ca-ctlabs/ca.crt)")
    args = parser.parse_args()

    if not args.token:
        parser.error("missing token (pass --token or set VAULT_TOKEN)")

    data = export(args.addr, args.token, build_context(args))
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"

    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        os.chmod(args.out, 0o600)
        sys.stderr.write("Wrote vault setup fact to {0}\n".format(args.out))
    else:
        sys.stdout.write(text)

    if data.get("users"):
        sys.stderr.write(
            "NOTE: userpass passwords cannot be read back by Vault; the exported "
            "users have no 'password' field -- add passwords to the fact file\n"
        )


if __name__ == "__main__":
    main()
