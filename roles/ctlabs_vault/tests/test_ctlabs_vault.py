# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_vault/tests/test_ctlabs_vault.py
# Description : pytest tests for ctlabs_vault role
# ------------------------------------------------------------------------------

import ast
import os
import subprocess

import pytest
import yaml


def _load_tasks(role_dir, name):
    with open(os.path.join(role_dir, "tasks", name)) as f:
        return yaml.safe_load(f)


def _all_tasks(tasks):
    for t in tasks:
        yield t
        if isinstance(t.get("block"), list):
            yield from _all_tasks(t["block"])


def test_template_exists(role_dir):
    templates = [
        "vault.hcl.j2",
        "vault-agent.hcl.j2",
        "vault-proxy.hcl.j2",
        "vault.service.j2",
        "vault-agent.service.j2",
        "vault-proxy.service.j2",
    ]
    for tpl in templates:
        path = os.path.join(role_dir, "templates", tpl)
        assert os.path.isfile(path), f"Missing template: {tpl}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_vault.yml")
    env = dict(os.environ, ANSIBLE_ROLES_PATH=os.path.join(role_dir, os.pardir))
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_main_imports_bootstrap_with_tag(role_dir):
    main = _load_tasks(role_dir, "main.yml")
    bootstrap = next(t for t in main if "bootstrap.yml" in str(t.get("import_tasks", "")))
    assert "ctlabs_vault.bootstrap" in bootstrap["tags"]
    init = next(t for t in main if "init.yml" in str(t.get("import_tasks", "")))
    assert "ctlabs_vault.init" in init["tags"]
    assert main.index(bootstrap) > main.index(init)


def test_bootstrap_apply_server_only(role_dir):
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    root = next(t for t in bootstrap if t.get("name") == "ctlabs_vault.tasks.bootstrap")
    assert "ctlabs_vault_install_type == 'server'" in " ".join(_as_list(root["when"]))
    apply = next(t for t in bootstrap if t.get("name") == "ctlabs_vault.tasks.bootstrap.apply")
    assert "ctlabs_vault_install_type == 'server'" in " ".join(_as_list(apply["when"]))
    assert "ctlabs_vault_bootstrap_token_ok" in " ".join(_as_list(apply["when"]))


def test_bootstrap_root_token_from_init_output(role_dir):
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    root = next(t for t in bootstrap if t.get("name") == "ctlabs_vault.tasks.bootstrap")
    names = [t.get("name") for t in _all_tasks([root])]
    assert "ctlabs_vault.tasks.bootstrap.root_token.slurp" in names
    assert "ctlabs_vault.tasks.bootstrap.root_token.fact" in names
    assert "ctlabs_vault.tasks.bootstrap.token.ok" in names
    slurp = next(t for t in _all_tasks([root]) if t.get("name") == "ctlabs_vault.tasks.bootstrap.root_token.slurp")
    assert ".ctlabs_vault_init_output_" in slurp["slurp"]["src"]
    assert "delegate_to" in slurp and slurp["delegate_to"] == "localhost"


def test_bootstrap_no_command(role_dir):
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    for t in _all_tasks(bootstrap):
        assert "command" not in t, f"bootstrap task '{t.get('name')}' must not use command"
        assert "shell" not in t, f"bootstrap task '{t.get('name')}' must not use shell"


def test_bootstrap_idempotent_read_before_write(role_dir):
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    for t in _all_tasks(bootstrap):
        method = (t.get("uri") or {}).get("method")
        if method not in ("POST", "PUT"):
            continue
        assert "when" in t, f"write task '{t.get('name')}' must be gated on a prior read"
        assert "status" in str(t["when"]), f"write task '{t.get('name')}' must check read result status"


def test_bootstrap_defaults_fallback(role_dir):
    with open(os.path.join(role_dir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)
    setup = defaults["ctlabs_vault_setup"]
    auth = next(a for a in setup["auth"] if a["path"] == "userpass")
    assert auth["type"] == "userpass"
    user = next(u for u in setup["users"] if u["username"] == "ctlabs")
    assert "ctlabs" in user["policies"]
    assert "secret123!" == user["password"]
    policy = next(p for p in setup["policies"] if p["name"] == "ctlabs")
    assert policy["source"] == "template"
    assert policy["template"] == "ctlabs.hcl.j2"


def test_init_has_no_hardcoded_bootstrap(role_dir):
    init = _load_tasks(role_dir, "init.yml")
    names = [t.get("name") for t in _all_tasks(init)]
    for forbidden in [
        "userpass.enable",
        "userpass.add_user",
        "userpass.policy.ctlabs",
        "secrets.userpass.enable",
    ]:
        assert not any(forbidden in n for n in names), f"init.yml must not hard-bootstrap ({forbidden})"


def test_export_script_present_and_valid(role_dir):
    script = os.path.join(role_dir, "files", "vault-export.py")
    assert os.path.isfile(script)
    with open(script) as f:
        ast.parse(f.read())


def _as_list(value):
    return value if isinstance(value, list) else [value]


def _load_backup_module():
    import importlib.util
    here = os.path.dirname(__file__)
    script = os.path.join(here, "..", "files", "vault-backup.py")
    spec = importlib.util.spec_from_file_location("ctlabs_vault_backup", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backup_script_present_and_valid(role_dir):
    script = os.path.join(role_dir, "files", "vault-backup.py")
    assert os.path.isfile(script)
    with open(script) as f:
        ast.parse(f.read())


def test_backup_crypto_roundtrip(role_dir):
    mod = _load_backup_module()
    payload = b"vault storage \x00\x01\x02"
    archive = mod.seal_archive(payload, "pw")
    assert archive.startswith(mod.MAGIC)
    assert mod.open_archive(archive, "pw") == payload


def test_backup_wrong_passphrase_rejected(role_dir):
    mod = _load_backup_module()
    archive = mod.seal_archive(b"secret", "right")
    for pw in ("", "wrong", "RIGHT"):
        with pytest.raises(ValueError):
            mod.open_archive(archive, pw)


def test_backup_tamper_and_bad_magic_rejected(role_dir):
    mod = _load_backup_module()
    archive = bytearray(mod.seal_archive(b"secret", "pw"))
    archive[-1] ^= 0xFF
    with pytest.raises(ValueError):
        mod.open_archive(bytes(archive), "pw")
    with pytest.raises(ValueError):
        mod.open_archive(b"not-a-backup", "pw")


def test_backup_payload_roundtrip_and_meta(role_dir, tmp_path):
    mod = _load_backup_module()
    data = tmp_path / "data"
    (data / "sub").mkdir(parents=True)
    (data / "core").write_text("vault core")
    (data / "sub" / "f").write_bytes(b"\x00\x01bin")
    config = tmp_path / "config"
    config.mkdir()
    (config / "vault.hcl").write_text("storage file")
    meta = {
        "kind": "full",
        "node": "t",
        "vault_unseal_keys_b64": ["unseal-key-b64"],
        "vault_root_token": "hvs.fake",
    }
    payload = mod.build_payload(meta, str(data), str(config))
    assert mod.read_payload_meta(payload) == meta

    out_data = tmp_path / "out_data"
    out_config = tmp_path / "out_config"
    assert mod.safe_extract(payload, str(out_data), str(out_config)) == meta
    assert (out_data / "core").read_text() == "vault core"
    assert (out_data / "sub" / "f").read_bytes() == b"\x00\x01bin"
    assert (out_config / "vault.hcl").read_text() == "storage file"


def test_backup_safe_extract_rejects_traversal(role_dir, tmp_path):
    import io as _io
    import tarfile
    mod = _load_backup_module()
    buf = _io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        ti = tarfile.TarInfo("data/../../../pwned")
        ti.size = 3
        ti.mode = 0o644
        tf.addfile(ti, _io.BytesIO(b"abc"))
    with pytest.raises(ValueError):
        mod.safe_extract(buf.getvalue(), str(tmp_path / "dest"))


def test_backup_keys_file_parse(role_dir, tmp_path):
    mod = _load_backup_module()
    keyring = tmp_path / "init-output.yml"
    keyring.write_text(
        "ctlabs_vault_initialized: true\n"
        'vault_root_token        : "hvs.fakeToken"\n'
        'vault_unseal_keys_b64   : "SGVsbG8xMjNIMDA9==X"\n'
        'vault_unseal_keys       : "hex-thing"\n'
    )
    keys, root = mod._load_keys_from_file(str(keyring))
    assert root == "hvs.fakeToken"
    assert keys == ["SGVsbG8xMjNIMDA9==X"]


def test_backup_requires_keys_unless_force(role_dir):
    mod = _load_backup_module()
    old_env = os.environ.get("VAULT_BACKUP_UNSEAL_KEYS")
    for var in ("VAULT_BACKUP_UNSEAL_KEYS", "VAULT_BACKUP_ROOT_TOKEN"):
        os.environ.pop(var, None)
    args = type("Args", (), {"keys_file": None, "force": False})()
    assert mod.load_keys(args) == ([], None)
    if old_env is not None:
        os.environ["VAULT_BACKUP_UNSEAL_KEYS"] = old_env
