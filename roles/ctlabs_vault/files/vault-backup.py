#!/usr/bin/env python3
"""
Automated Vault backup & restore for 'file' storage — SEALED ARCHIVE MODE.

The snapshot (.vback) is a single self-contained file that contains the Vault
storage data (plus optional config), the unseal key(s) and the root token,
encrypted at rest so the archive alone is useless without the passphrase:

    CTLABS_VAULT_BACKUP_V1 + salt(16) + Fernet( tar.gz {
        ctlabs-restore-meta.json   (keys, node, timestamp, ...)
        data/                      (contents of the file-storage dir)
        config/                    (contents of /etc/vault.d, full backups only)
    } )

    * Fernet = AES-128-CBC + HMAC-SHA256 (authenticated encryption), audited.
    * Key    = PBKDF2-HMAC-SHA256(passphrase, salt, 300k iters) — strong KDF.

Threat model / custody:
    - The passphrase is NEVER stored in the archive, on disk, or on the
      command line (argv would leak via `ps`). You provide it via
      VAULT_BACKUP_PASSPHRASE, --passphrase-file (mode 0600/0400), or an
      interactive prompt. Keep it out-of-band (password manager / custodian).
    - Attacker with the archive + no passphrase: nothing (confidentiality).
    - Any tampering or bit-rot in the archive: detected on open (authenticity).
    - The controller keyring (/root/ctlabs-ansible/.ctlabs_vault_init_output_*.yml,
      mode 0400) stays as the offline fallback copy of the keys.

Safety (updated danger model):
    - The backup refuses to stop the Vault when it would be left permanently
      sealed (running+unsealed but no unseal key available, or already sealed
      with no key) unless --force is given.
    - After every stop/start, the script re-unseals automatically with the
      embedded key and verifies the root token — which also proves the keyring
      still matches the Vault (catches post-rekey staleness).
    - Restore verifies the archive (magic, auth tag, key availability) BEFORE
      touching any live data, moves the existing data dir aside (not delete),
      then starts and unseals.

Requires: python3-cryptography (Fernet). stdlib otherwise.
"""

import argparse
import base64
import getpass
import hashlib
import io
import json
import logging
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    from cryptography.fernet import Fernet, InvalidToken
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

# ==========================================
# CONFIGURATION (overridable via CLI flags)
# ==========================================
MAGIC            = b"CTLABS_VAULT_BACKUP_V1\0"
KDF_ITERATIONS   = 300_000
BACKUP_DIR       = "/var/backups/vault"
DATA_DIR         = "/opt/vault/data"       # storage "file" { path = ... } block
CONFIG_DIR       = "/etc/vault.d"          # vault.hcl + certs live here
CONFIG_FILE      = "/etc/vault.d/vault.hcl"
VAULT_USER       = "vault"
VAULT_GROUP      = "vault"
RETENTION_DAYS   = 30
LOG_FILE         = "/var/log/vault-backup.log"

# ==========================================
# LOGGING / TOOLS
# ==========================================
def setup_logging(log_file=LOG_FILE):
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

def die(msg, code=1):
    logging.error(msg)
    sys.exit(code)

def check_root():
    if os.geteuid() != 0:
        die("This script must be run as root or with sudo.")

def run_cmd(cmd_list, shell=False):
    """Executes a system command and logs any errors."""
    try:
        subprocess.run(cmd_list, check=True, shell=shell,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        die(f"Command failed: {' '.join(cmd_list)}\nOutput: {e.stdout}")

# ==========================================
# CRYPTO ENVELOPE (Fernet + PBKDF2)
# ==========================================
def require_crypto():
    if not HAVE_CRYPTO:
        die("python3-cryptography is required (Fernet). Install it, e.g.: "
            "apt install python3-cryptography")

def derive_fernet_key(passphrase, salt):
    raw = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt,
                              KDF_ITERATIONS, dklen=32)
    return Fernet(base64.urlsafe_b64encode(raw))

def seal_archive(payload, passphrase):
    """Wrap a bytes payload in the sealed envelope. Returns full archive bytes."""
    require_crypto()
    salt = os.urandom(16)
    token = derive_fernet_key(passphrase, salt).encrypt(payload)
    return MAGIC + salt + token

def open_archive(data, passphrase):
    """Unseal and authenticate an archive. Raises ValueError on bad magic /
    wrong passphrase / tampering."""
    require_crypto()
    if not data.startswith(MAGIC):
        raise ValueError("not a ctlabs vault backup (bad magic)")
    salt, token = data[len(MAGIC):len(MAGIC) + 16], data[len(MAGIC) + 16:]
    try:
        return derive_fernet_key(passphrase, salt).decrypt(token)
    except InvalidToken:
        raise ValueError("wrong passphrase, or archive is tampered/corrupt")

# ==========================================
# TAR PAYLOAD BUILD / EXTRACT
# ==========================================
def build_payload(meta, data_dir, config_dir=None):
    """gzip tar of meta.json + data/ [+ config/]; returns in-memory bytes."""
    bio = io.BytesIO()
    with tarfile.open(mode="w:gz", fileobj=bio) as tf:
        meta_bytes = json.dumps(meta, indent=2, sort_keys=True).encode("utf-8")
        ti = tarfile.TarInfo("ctlabs-restore-meta.json")
        ti.size = len(meta_bytes)
        ti.mode = 0o600
        ti.mtime = int(time.time())
        tf.addfile(ti, io.BytesIO(meta_bytes))
        tf.add(data_dir, arcname="data")
        if config_dir:
            tf.add(config_dir, arcname="config")
    return bio.getvalue()

def read_payload_meta(payload):
    """Parse ctlabs-restore-meta.json WITHOUT writing anything to disk."""
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tf:
            m = tf.getmember("ctlabs-restore-meta.json")
            return json.loads(tf.extractfile(m).read().decode("utf-8"))
    except (KeyError, tarfile.TarError, EOFError, json.JSONDecodeError) as e:
        raise ValueError(f"archive is missing a valid ctlabs-restore-meta.json: {e}")

def _safe_join(dest, member_name):
    rdest = os.path.realpath(dest)
    rel = member_name.lstrip("/").replace("\\", "/")
    if rel.startswith("..") or "/../" in "/" + rel:
        raise ValueError(f"unsafe path in archive: {member_name}")
    full = os.path.realpath(os.path.join(dest, rel))
    if not (full == rdest or full.startswith(rdest + os.sep)):
        raise ValueError(f"unsafe path in archive: {member_name}")
    return rel, full

def safe_extract(payload, data_dest, config_dest=None):
    """Extract data/ (and config/) from an authenticated payload. Returns the
    parsed ctlabs-restore-meta.json. Path-traversal defensively checked."""
    meta = None
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tf:
        for m in tf.getmembers():
            name = m.name.replace("\\", "/")
            if name == "ctlabs-restore-meta.json":
                meta = json.loads(tf.extractfile(m).read().decode("utf-8"))
                continue
            if name == "data" or name.startswith("data/"):
                dest, arc = data_dest, name[len("data"):]
            elif config_dest and (name == "config" or name.startswith("config/")):
                dest, arc = config_dest, name[len("config"):]
            else:
                logging.warning("skipping unknown archive member: %s", name)
                continue
            rel, full = _safe_join(dest, arc)
            if rel == "":
                os.makedirs(dest, exist_ok=True)
                continue
            if m.isdir():
                os.makedirs(full, exist_ok=True)
                os.chmod(full, m.mode or 0o750)
            elif m.isfile():
                os.makedirs(os.path.dirname(full), exist_ok=True)
                src = tf.extractfile(m)
                with open(full, "wb") as out, src:
                    shutil.copyfileobj(src, out)
                if m.mode:
                    os.chmod(full, m.mode)
            elif m.issym():
                target = m.linkname.replace("\\", "/")
                lnk_full = os.path.normpath(os.path.join(os.path.dirname(full), target))
                if not lnk_full.startswith(os.path.realpath(dest) + os.sep):
                    raise ValueError(f"unsafe link target in archive: {name} -> {target}")
                os.makedirs(os.path.dirname(full), exist_ok=True)
                os.symlink(target, full)
            elif m.islnk() or m.isdev():
                raise ValueError(f"unsupported member in archive: {name}")
    if not meta:
        raise ValueError("archive has no ctlabs-restore-meta.json")
    return meta

# ==========================================
# KEYS + PASSPHRASE
# ==========================================
def _load_keys_from_file(path):
    if not os.path.isfile(path):
        die(f"keys file not found: {path}")
    content = open(path, "r").read()
    found = {}
    for key in ("vault_root_token", "vault_unseal_keys_b64", "vault_unseal_keys"):
        m = re.search(r'^\s*%s\s*:\s*["\']?([^"\'\n]+)["\']?\s*$' % re.escape(key),
                      content, re.MULTILINE)
        if m:
            found[key] = m.group(1)
    # YAML fallback when available (more robust for future keyring layouts)
    if not found:
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml:
            d = yaml.safe_load(content) or {}
            for key in ("vault_root_token", "vault_unseal_keys_b64", "vault_unseal_keys"):
                if key in d:
                    found[key] = d[key]
    unseal = found.get("vault_unseal_keys_b64", found.get("vault_unseal_keys"))
    if not unseal:
        die(f"no unseal keys found in {path} (looked for vault_unseal_keys_b64 / vault_unseal_keys)")
    if isinstance(unseal, str):
        unseal = [k.strip() for k in unseal.split(",") if k.strip()]
    root = found.get("vault_root_token")
    if not root:
        die(f"no vault_root_token found in {path}")
    return unseal, root

def load_keys(args):
    """Returns (unseal_key_list, root_token) from --keys-file or env."""
    if getattr(args, "keys_file", None):
        return _load_keys_from_file(args.keys_file)
    env_keys = os.environ.get("VAULT_BACKUP_UNSEAL_KEYS")
    env_root = os.environ.get("VAULT_BACKUP_ROOT_TOKEN")
    if env_keys and env_root:
        try:
            keys = json.loads(env_keys)
        except json.JSONDecodeError:
            keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        return keys, env_root
    return [], None

def load_passphrase(args):
    pf = getattr(args, "passphrase_file", None)
    if pf:
        if not os.path.isfile(pf):
            die(f"passphrase file not found: {pf}")
        mode = os.stat(pf).st_mode & 0o777
        if mode not in (0o600, 0o400):
            die(f"passphrase file must be mode 0600 or 0400 (got {mode:03o}): {pf}")
        with open(pf, "r") as f:
            pw = f.readline().rstrip("\n")
        if not pw:
            die(f"passphrase file is empty: {pf}")
        return pw
    env = os.environ.get("VAULT_BACKUP_PASSPHRASE")
    if env:
        return env
    return getpass.getpass("Backup passphrase: ")

# ==========================================
# VAULT HTTP API (stdlib urllib)
# ==========================================
def http_json(method, url, body=None, token=None, ca_cert=None, timeout=10):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, data=data, method=method)
    if token:
        req.add_header("X-Vault-Token", token)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if ca_cert:
        ctx = ssl.create_default_context(cafile=ca_cert)
    else:
        ctx = ssl._create_unverified_context()  # local node cert is for the hostname
    try:
        with urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except HTTPError as e:
        raw = e.read()
        try:
            j = json.loads(raw)
        except Exception:
            j = {}
        return e.code, j
    except Exception as e:
        logging.debug("http call failed: %s", e)
        return 0, {}

def resolve_api_addr(args):
    if getattr(args, "addr", None):
        return args.addr.rstrip("/")
    if os.environ.get("VAULT_ADDR"):
        return os.environ["VAULT_ADDR"].rstrip("/")
    if os.path.isfile(CONFIG_FILE):
        content = open(CONFIG_FILE, "r").read()
        m = re.search(r'api_addr\s*=\s*"(https?://[^"]+)"', content)
        if m:
            return m.group(1).rstrip("/")
        m = re.search(r'address\s*=\s*"([0-9.]+:[0-9]+)"', content)
        if m:
            return f"https://{m.group(1)}"
    return "https://127.0.0.1:8200"

def seal_status(addr, ca_cert=None):
    return http_json("GET", addr + "/v1/sys/seal-status", ca_cert=ca_cert)

def wait_vault_up(addr, timeout=90, ca_cert=None):
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        st, j = seal_status(addr, ca_cert)
        if 200 <= st < 300:
            return j
        last = j
        time.sleep(1)
    die(f"vault API did not come up at {addr} within {timeout}s: {last}")

def do_unseal(addr, keys, ca_cert=None):
    j = wait_vault_up(addr, ca_cert=ca_cert)
    if j.get("sealed") is False:
        return True
    for key in keys:
        st, jj = http_json("PUT", addr + "/v1/sys/unseal", body={"key": key},
                           ca_cert=ca_cert)
        if jj.get("sealed") is False:
            logging.info("vault unsealed")
            return True
    return False

def verify_root_token(addr, token, ca_cert=None):
    st, _ = http_json("GET", addr + "/v1/auth/token/lookup-self", token=token,
                      ca_cert=ca_cert)
    return st == 200

# ==========================================
# BACKUP
# ==========================================
def build_meta(args, full, keys, root):
    meta = {
        "format_version": 1,
        "kind": "full" if full else "snap",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "node": socket.getfqdn(),
        "storage_backend": "file",
        "data_dir": args.data_dir,
        "vault_unseal_keys_b64": keys,
        "vault_root_token": root,
    }
    if full:
        meta["config_dir"] = args.config_dir
    return meta

def preflight(args, keys):
    addr = resolve_api_addr(args)
    st, health = seal_status(addr, getattr(args, "ca_cert", None))
    if st >= 400:
        logging.warning("seal-status unavailable (%s): continuing, vault must be sealed/init?",
                        st)
        return addr, False, "unknown"
    return addr, health.get("sealed", True), ("uninitialized"
                                              if not health.get("initialized", True)
                                              else "initialized")

def cmd_backup(args, full):
    keys, root = load_keys(args)
    addr, currently_sealed, init_state = preflight(args, keys)

    if not keys:
        if not getattr(args, "force", False):
            die("no unseal keys available (use --keys-file <init-output.yml> or the "
                "VAULT_BACKUP_UNSEAL_KEYS/VAULT_BACKUP_ROOT_TOKEN env vars). Refusing to "
                "restart the vault, which would leave it permanently sealed and unlock "
                "the storage. Re-run with --force if you really want a key-less archive.")
        logging.warning("no unseal keys -> archive will NOT include keys and the vault "
                        "will be left SEALED after restart (--force given)")
    elif currently_sealed and init_state != "uninitialized":
        logging.warning("vault is currently sealed; keys supplied, will re-unseal "
                        "after backup")

    run_cmd(["systemctl", "stop", args.service])
    try:
        meta = build_meta(args, full, keys, root)
        payload = build_payload(meta, args.data_dir, args.config_dir if full else None)
        archive = seal_archive(payload, load_passphrase(args))
        os.makedirs(args.out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        kind = "full" if full else "snap"
        out = os.path.join(args.out_dir, f"vault-{kind}-{stamp}.vback")
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(archive)
    finally:
        run_cmd(["systemctl", "start", args.service])

    if keys and not getattr(args, "no_unseal", False):
        logging.info("re-unsealing vault after restart...")
        if not do_unseal(addr, keys, getattr(args, "ca_cert", None)):
            die("could not re-unseal the vault after backup — unseal manually!", code=2)
        if root and not verify_root_token(addr, root, getattr(args, "ca_cert", None)):
            die("vault unsealed but the embedded root token is NOT valid (keyring "
                "stale? rekeyed?) — refresh the keys file!", code=2)
        logging.info("backup complete, vault unsealed + root token verified: %s", out)
    else:
        logging.warning("vault left SEALED after backup — unseal it manually: %s", out)

    cleanup_old_backups(args.out_dir)
    logging.info("backup created successfully: %s", out)

def cleanup_old_backups(backup_dir):
    cutoff = time.time() - RETENTION_DAYS * 86400
    if not os.path.isdir(backup_dir):
        return
    removed = 0
    for name in os.listdir(backup_dir):
        if name.startswith("vault-") and name.endswith(".vback"):
            p = os.path.join(backup_dir, name)
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
                removed += 1
    if removed:
        logging.info("deleted %d expired backup(s) older than %s days",
                     removed, RETENTION_DAYS)

# ==========================================
# RESTORE
# ==========================================
def clear_directory(dir_path):
    """Empties a directory without deleting the directory itself."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return
    for name in os.listdir(dir_path):
        p = os.path.join(dir_path, name)
        try:
            if os.path.isfile(p) or os.path.islink(p):
                os.unlink(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)
        except Exception as e:
            die(f"failed to delete {p}: {e}")

def move_aside(directory):
    """Rename an existing (non-empty) dir to dir.pre-<ts>; delete older .pre-*."""
    if not os.path.isdir(directory) or not os.listdir(directory):
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    aside = f"{directory}.pre-{stamp}"
    shutil.move(directory, aside)
    for name in os.listdir(os.path.dirname(aside) or "."):
        p = os.path.join(os.path.dirname(aside) or ".", name)
        if name.startswith(os.path.basename(directory) + ".pre-") and p != aside:
            try:
                shutil.rmtree(p)
            except Exception:
                pass
    return aside

def cmd_restore(args, full):
    archive_path = args.file
    if not os.path.isfile(archive_path):
        die(f"invalid backup file: {archive_path}")
    if not os.path.getsize(archive_path):
        die(f"backup file is empty: {archive_path}")

    try:
        payload = open_archive(open(archive_path, "rb").read(), load_passphrase(args))
    except ValueError as e:
        die(f"cannot open archive: {e}")
    # meta read BEFORE any stop/destructive step; nothing is written yet
    try:
        meta = read_payload_meta(payload)
    except ValueError as e:
        die(f"archive unusable: {e}")
    keys = meta.get("vault_unseal_keys_b64") or []
    root = meta.get("vault_root_token")

    logging.info("archive meta: kind=%s node=%s created=%s unseal_keys=%d",
                 meta.get("kind"), meta.get("node"), meta.get("created_at"), len(keys))
    if full and not meta.get("kind") == "full":
        die("archive is a snapshot backup; use restore-snap")

    if not keys:
        die("archive contains no unseal keys — cannot restore it to a running vault")
    if not getattr(args, "yes", False):
        target = ", ".join([args.data_dir] + ([args.config_dir] if full else []))
        answer = input(f"This will REPLACE {target} from {archive_path}. "
                       "Type YES to continue: ")
        if answer.strip() != "YES":
            die("aborted by user")

    run_cmd(["systemctl", "stop", args.service])
    try:
        # extract into a fresh dir, then swap: the live data dir is only touched
        # after the authenticated extraction fully succeeded
        tmp_data = args.data_dir + ".restore-tmp"
        clear_directory(tmp_data)
        if full:
            clear_directory(args.config_dir)
        safe_extract(payload, tmp_data, args.config_dir if full else None)
        run_cmd(["chown", "-R", f"{VAULT_USER}:{VAULT_GROUP}", tmp_data])
        move_aside(args.data_dir)
        os.rename(tmp_data, args.data_dir)
        if full:
            run_cmd(["chown", "-R", f"{VAULT_USER}:{VAULT_GROUP}", args.config_dir])
    finally:
        run_cmd(["systemctl", "start", args.service])

    addr = resolve_api_addr(args)
    if not getattr(args, "no_unseal", False):
        if not do_unseal(addr, keys, getattr(args, "ca_cert", None)):
            die("restore finished, but could not re-unseal the vault — unseal manually!", code=2)
        if root and not verify_root_token(addr, root, getattr(args, "ca_cert", None)):
            die("vault unsealed but the archive root token does not authenticate — "
                "investigate before resuming work!", code=2)
        logging.info("restore complete; vault unsealed and root token verified.")
    else:
        logging.warning("restore complete; vault left SEALED — unseal manually.")

# ==========================================
# MAIN
# ==========================================
def make_parent():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--addr", help="vault API address (default: api_addr from "
                                  "vault.hcl, else VAULT_ADDR, else https://127.0.0.1:8200)")
    p.add_argument("--ca-cert", help="CA bundle to verify the vault TLS cert")
    p.add_argument("--passphrase-file", metavar="FILE",
                   help="file (mode 0600/0400) with the backup passphrase; "
                        "env VAULT_BACKUP_PASSPHRASE or an interactive prompt "
                        "are the alternatives")
    p.add_argument("--service", default="vault", help="systemd unit (default: vault)")
    p.add_argument("--data-dir", default=DATA_DIR, help=f"vault storage dir (default: {DATA_DIR})")
    p.add_argument("--config-dir", default=CONFIG_DIR, help=f"config dir (default: {CONFIG_DIR})")
    p.add_argument("--out-dir", default=BACKUP_DIR, help=f"backup dir (default: {BACKUP_DIR})")
    p.add_argument("--log-file", default=LOG_FILE, help=f"log file (default: {LOG_FILE})")
    return p

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Automated Vault backup & restore for 'file' storage — "
                    "sealed (encrypted, key-embedded) vault-(snap|full)-*.vback archives",
        parents=[make_parent()])
    sub = parser.add_subparsers(dest="command", required=True)
    parent = make_parent()

    for name, full in (("backup-snap", False), ("backup-full", True)):
        sp = sub.add_parser(name, parents=[parent],
                            help="encrypted backup of the data dir"
                                 + (" + config dir" if full else ""))
        sp.add_argument("--keys-file", metavar="FILE",
                        help="init-output keyring YAML (vault_unseal_keys_b64 + "
                             "vault_root_token); env VAULT_BACKUP_UNSEAL_KEYS + "
                             "VAULT_BACKUP_ROOT_TOKEN also work")
        sp.add_argument("--no-unseal", action="store_true",
                        help="do not re-unseal the vault after the restart")
        sp.add_argument("--force", action="store_true",
                        help="proceed even without unseal keys (archive will lack "
                             "keys; vault left sealed — DANGEROUS)")

    for name, full in (("restore-snap", False), ("restore-full", True)):
        sp = sub.add_parser(name, parents=[parent],
                            help="restore a sealed backup into the data dir"
                                 + (" + config dir" if full else ""))
        sp.add_argument("file", help="the .vback sealed archive to restore")
        sp.add_argument("--yes", action="store_true",
                        help="skip the destructive confirmation prompt")
        sp.add_argument("--no-unseal", action="store_true",
                        help="do not unseal the vault after restore")

    args = parser.parse_args(argv)
    setup_logging(getattr(args, "log_file", LOG_FILE))

    if args.command in ("backup-snap", "backup-full"):
        if os.geteuid() != 0:
            die("backup must be run as root (systemctl stop/start vault)")
        cmd_backup(args, args.command == "backup-full")
    elif args.command in ("restore-snap", "restore-full"):
        if os.geteuid() != 0:
            die("restore must be run as root (systemctl stop/start vault)")
        cmd_restore(args, args.command == "restore-full")

if __name__ == "__main__":
    main()
