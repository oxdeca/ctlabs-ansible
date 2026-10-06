# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_vault/tests/test_ctlabs_vault.py
# Description : pytest tests for ctlabs_vault role
# ------------------------------------------------------------------------------

import ast
import json
import os
import shutil
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


def test_bootstrap_reads_accept_vault_400_missing(role_dir):
    """Vault answers 400 (not 404) when an auth/mount path is missing; reads must
    accept it and the create gating must treat 400+404 as 'not found'."""
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    read_tasks = 0
    for t in _all_tasks(bootstrap):
        uri = t.get("uri") or {}
        if not uri or uri.get("method") in ("POST", "PUT"):
            continue
        read_tasks += 1
        assert 400 in uri["status_code"], f"read '{t.get('name')}' must accept 400"
        assert 404 in uri["status_code"], f"read '{t.get('name')}' must accept 404"
    assert read_tasks >= 8, f"expected >=8 read tasks, found {read_tasks}"
    write_tasks = [t for t in _all_tasks(bootstrap)
                   if (t.get("uri") or {}).get("method") in ("POST", "PUT")]
    for t in write_tasks:
        when = str(t["when"])
        assert ("in [400, 404]" in when) or ("200" in when), \
            f"write '{t.get('name')}' must gate on missing (in [400, 404]) or existing (200) status"


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


def test_bootstrap_kubernetes_items_default_to_empty(role_dir):
    """Absence of a 'kubernetes' key in the setup fact must not raise -- same
    contract as jwt.items, just via a plain | default([]) since kubernetes
    (unlike jwt) is naturally a list, not a single mapping."""
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    root = next(t for t in bootstrap if t.get("name") == "ctlabs_vault.tasks.bootstrap")
    items = next(t for t in _all_tasks([root]) if t.get("name") == "ctlabs_vault.tasks.bootstrap.kubernetes.items")
    expr = items["set_fact"]["ctlabs_vault_kubernetes_items"]
    assert "default([])" in expr


def test_bootstrap_kubernetes_tasks_all_no_log_not_just_the_write(role_dir):
    """The reviewer JWT rides along in `item` on EVERY task that loops over
    ctlabs_vault_kubernetes_items or its subelements, not just the task that
    uses it -- a plain `-v` run leaked it in plaintext via config.read's item
    echo (live incident, 2026-10-06) because only config.write had no_log."""
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    apply_block = next(t for t in bootstrap if t.get("name") == "ctlabs_vault.tasks.bootstrap.apply")
    kubernetes_tasks = [
        t for t in _all_tasks([apply_block])
        if str(t.get("name", "")).startswith("ctlabs_vault.tasks.bootstrap.kubernetes.")
    ]
    assert len(kubernetes_tasks) == 4, "expected config.read/write + role.read/create"
    for t in kubernetes_tasks:
        assert t.get("no_log") is True, f"{t['name']} loops over kubernetes items (carries the reviewer JWT) but has no no_log"


def test_bootstrap_kubernetes_config_write_never_logs_reviewer_jwt(role_dir):
    """The config write body carries token_reviewer_jwt -- a credential as
    sensitive as a userpass password or an OIDC signing key -- so the task
    must be no_log, same reasoning as the backup passphrase task."""
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    apply_block = next(t for t in bootstrap if t.get("name") == "ctlabs_vault.tasks.bootstrap.apply")
    write = next(
        t for t in _all_tasks([apply_block])
        if t.get("name") == "ctlabs_vault.tasks.bootstrap.kubernetes.config.write"
    )
    assert write.get("no_log") is True


def test_bootstrap_kubernetes_config_gates_on_host_or_ca_mismatch(role_dir):
    """token_reviewer_jwt is write-only (never returned on read, like an OIDC
    signing key), so idempotency can only compare kubernetes_host/ca_cert --
    this pins the when expression against both match and mismatch cases."""
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)

    with open(os.path.join(role_dir, "tasks", "bootstrap.yml")) as f:
        lines = f.read().splitlines()
    start = next(i for i, ln in enumerate(lines) if "ctlabs_vault.tasks.bootstrap.kubernetes.config.write" in ln)
    when_start = next(i for i in range(start, len(lines)) if lines[i].strip().startswith("when:"))
    assert lines[when_start].strip() == "when: >-"
    expr_lines = []
    for ln in lines[when_start + 1:]:
        if not ln.startswith(" " * 8) or not ln.strip():
            break
        expr_lines.append(ln.strip())
    expr = " ".join(expr_lines)
    got = env.compile_expression(expr)

    item_404 = {"status": 404, "item": {"host": "https://k8s:6443", "ca_cert": "CA"}}
    item_match = {"status": 200, "item": {"host": "https://k8s:6443", "ca_cert": "CA"},
                  "json": {"data": {"kubernetes_host": "https://k8s:6443", "kubernetes_ca_cert": "CA"}}}
    item_host_changed = {"status": 200, "item": {"host": "https://new:6443", "ca_cert": "CA"},
                          "json": {"data": {"kubernetes_host": "https://k8s:6443", "kubernetes_ca_cert": "CA"}}}
    item_ca_changed = {"status": 200, "item": {"host": "https://k8s:6443", "ca_cert": "NEWCA"},
                        "json": {"data": {"kubernetes_host": "https://k8s:6443", "kubernetes_ca_cert": "CA"}}}

    assert got(item=item_404) is True
    assert got(item=item_match) is False
    assert got(item=item_host_changed) is True
    assert got(item=item_ca_changed) is True


def test_bootstrap_kubernetes_role_create_accepts_200(role_dir):
    """Verified live against Vault 2.1.1: unlike approle/jwt role writes (204
    No Content), PUT auth/kubernetes/role/<name> returns 200 with a body. A
    204-only status_code makes a successful write look like a task failure."""
    bootstrap = _load_tasks(role_dir, "bootstrap.yml")
    apply_block = next(t for t in bootstrap if t.get("name") == "ctlabs_vault.tasks.bootstrap.apply")
    write = next(
        t for t in _all_tasks([apply_block])
        if t.get("name") == "ctlabs_vault.tasks.bootstrap.kubernetes.role.create"
    )
    assert write["uri"]["status_code"] == [200, 204]


def test_bootstrap_kubernetes_role_supports_multiple_roles_per_mount(role_dir):
    """Mirrors the jwt role pattern: one mount can have several roles (e.g. one
    per environment), so the read loop must use subelements, not a flat list."""
    with open(os.path.join(role_dir, "tasks", "bootstrap.yml")) as f:
        text = f.read()
    assert "ctlabs_vault_kubernetes_items | subelements('roles', skip_missing=True)" in text


def test_bootstrap_reads_from_ctlabs_vault_fact(role_dir):
    """The declarative setup now lives under ctlabs_vault.fact's 'bootstrap'
    key (this role's own <role_name>.fact, same convention every other role
    uses), not a separate ctlabs_vault_setup.fact -- that split was an
    inherited inconsistency, not a technical necessity."""
    with open(os.path.join(role_dir, "tasks", "bootstrap.yml")) as f:
        text = f.read()
    assert "ctg_facts.ctlabs_vault.bootstrap" in text
    assert "ctg_facts.ctlabs_vault_setup" not in text


def test_facts_task_sets_secure_mode(role_dir):
    """ctlabs_vault.fact can now carry bootstrap.users[].password -- it needs
    the same 0600 the old standalone ctlabs_vault_setup.fact had, not the
    template module's default mode."""
    with open(os.path.join(role_dir, "tasks", "facts.yml")) as f:
        text = f.read()
    assert "0600" in text


def _render_facts_json(role_dir, role_facts=None, ctg_os_version="9"):
    env = jinja2_env()
    with open(os.path.join(role_dir, "templates", "facts.json.j2")) as f:
        template = f.read()
    rendered = env.from_string(template).render(
        ctlabs_role_facts=role_facts, CTLABS_HOST="vdb1.ctlabs.internal"
    )
    return json.loads(rendered)


def test_facts_json_omits_bootstrap_when_absent(role_dir):
    """Omitted, not {} or null -- a written-but-empty value would shadow
    bootstrap.yml's own `| default(...)` fallback to the role default, same
    reasoning as ctlabs_argoapp's facts.json.j2 for its own optional knobs."""
    got = _render_facts_json(role_dir, role_facts={})
    assert "bootstrap" not in got
    assert got["install_type"] == "cli"


def test_facts_json_includes_bootstrap_when_present(role_dir):
    bootstrap = {
        "auth": [{"path": "userpass", "type": "userpass"}],
        "users": [{"username": "ctlabs", "password": "secret123!", "policies": ["ctlabs"]}],
    }
    got = _render_facts_json(role_dir, role_facts={"bootstrap": bootstrap})
    assert got["bootstrap"] == bootstrap


def test_export_write_bootstrap_creates_new_file(role_dir, tmp_path):
    mod = _load_export_module()
    path = str(tmp_path / "ctlabs_vault.fact")
    data = {"auth": [{"path": "userpass", "type": "userpass"}]}
    mod.write_bootstrap(path, data)
    with open(path) as f:
        written = json.load(f)
    assert written == {"bootstrap": data}
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"


def test_export_write_bootstrap_preserves_existing_keys(role_dir, tmp_path):
    """Must merge, not overwrite -- address/install_type live in the same
    file and have nothing to do with vault-export.py."""
    mod = _load_export_module()
    path = str(tmp_path / "ctlabs_vault.fact")
    with open(path, "w") as f:
        json.dump({"address": "https://vdb1:8200", "install_type": "server"}, f)
    data = {"auth": [{"path": "userpass", "type": "userpass"}]}
    mod.write_bootstrap(path, data)
    with open(path) as f:
        written = json.load(f)
    assert written["address"] == "https://vdb1:8200"
    assert written["install_type"] == "server"
    assert written["bootstrap"] == data


def test_export_write_bootstrap_refuses_invalid_existing_json(role_dir, tmp_path):
    mod = _load_export_module()
    path = str(tmp_path / "ctlabs_vault.fact")
    with open(path, "w") as f:
        f.write("not json at all")
    with pytest.raises(SystemExit):
        mod.write_bootstrap(path, {"auth": []})


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


def _load_export_module():
    import importlib.util
    here = os.path.dirname(__file__)
    script = os.path.join(here, "..", "files", "vault-export.py")
    spec = importlib.util.spec_from_file_location("ctlabs_vault_export", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeVault:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, addr, token, path, method="GET", body=None, ctx=None):
        self.calls.append(path)
        if path in self.routes:
            return self.routes[path]
        return None


def _export_identity_oidc(routes):
    """Run export_identity_oidc against canned API responses."""
    mod = _load_export_module()
    vault = _FakeVault(routes)
    mod.api = vault
    return mod.export_identity_oidc("https://v:8200", "tok", None), vault


def test_export_inventory_records_identity_oidc_without_reproducing_it(role_dir):
    got, _ = _export_identity_oidc(
        {
            "/v1/identity/oidc/config": {"data": {"issuer": "https://v:8200/"}},
            "/v1/identity/oidc/key?list=true": {"data": {"keys": ["default", "gcp-wif-key"]}},
            "/v1/identity/oidc/role?list=true": {"data": {"keys": ["gcp-wif"]}},
        }
    )
    assert got["covered"] is False
    assert got["issuer"] == "https://v:8200"
    assert got["signing_keys"] == ["gcp-wif-key"]
    assert got["roles"] == ["gcp-wif"]


def test_export_inventory_omits_builtin_default_signing_key(role_dir):
    got, _ = _export_identity_oidc(
        {"/v1/identity/oidc/key?list=true": {"data": {"keys": ["default"]}}}
    )
    assert got is None, "a vault with only the builtin default key is not a WIF setup"


def test_export_inventory_never_carries_key_or_role_config(role_dir):
    """The marker must stay an inventory: a faithful reproduction is impossible
    (write-only signing key, filtered role read-back). If someone later adds
    real key/role config here it would silently produce a broken WIF."""
    got, _ = _export_identity_oidc(
        {
            "/v1/identity/oidc/config": {"data": {"issuer": "https://v:8200"}},
            "/v1/identity/oidc/key?list=true": {"data": {"keys": ["gcp-wif-key"]}},
            "/v1/identity/oidc/role?list=true": {"data": {"keys": ["gcp-wif"]}},
        }
    )
    blob = json.dumps(got)
    for forbidden in ("bundle", "private_key", "token_policies", "bound_claims"):
        assert forbidden not in blob, "identity_oidc marker must not carry config: " + forbidden


def test_export_never_reads_signing_key_material(role_dir):
    """Pins the write-only assumption: the exporter must never issue a read that
    could pick up key material, and must rely on list endpoints instead."""
    _, vault = _export_identity_oidc(
        {
            "/v1/identity/oidc/config": {"data": {"issuer": "https://v:8200"}},
            "/v1/identity/oidc/key?list=true": {"data": {"keys": ["gcp-wif-key"]}},
        }
    )
    assert vault.calls == [
        "/v1/identity/oidc/config",
        "/v1/identity/oidc/key?list=true",
        "/v1/identity/oidc/role?list=true",
    ]
    for call in vault.calls:
        assert "?list=true" in call or call.endswith("/config")


def test_export_script_warns_that_identity_oidc_is_not_covered(role_dir):
    script = os.path.join(role_dir, "files", "vault-export.py")
    with open(script) as f:
        text = f.read()
    assert "identity/oidc/* is NOT covered" in text
    assert "vault_oidc_setup.py" in text
    assert "signing_keys" in text


def test_bootstrap_warns_when_vault_has_no_oidc_issuer(role_dir):
    with open(os.path.join(role_dir, "tasks", "bootstrap.yml")) as f:
        text = f.read()
    assert "/identity/oidc/config" in text, "bootstrap must inspect the OIDC issuer"
    assert "identity_oidc.missing_issuer" in text
    assert "vault_oidc_setup.py" in text, "the notice must name the owning script"


def test_bootstrap_oidc_issuer_when_survives_missing_and_null_issuer(role_dir):
    """`| default('')` only replaces *undefined*, not None -- so a 200 response
    with no issuer key (or a null issuer) made `| length` raise TypeError and
    took the whole play down. The boolean-default form must handle both."""
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)

    with open(os.path.join(role_dir, "tasks", "bootstrap.yml")) as f:
        text = f.read()
    extract = [
        ln
        for ln in text.splitlines()
        if "{{" in ln and ".get('issuer')" in ln
    ]
    assert extract, "could not find the issuer set_fact expression"
    got = env.compile_expression(
        extract[0].split("{{", 1)[1].split("}}", 1)[0].strip()
    )
    assert got(vault_bootstrap_identity_oidc={"json": {"data": {"issuer": ""}}}) == ""
    assert got(vault_bootstrap_identity_oidc={"json": {"data": {}}}) == ""
    assert got(vault_bootstrap_identity_oidc={"json": {"data": {"issuer": None}}}) == ""
    assert got(vault_bootstrap_identity_oidc={"json": {"errors": ["x"]}}) == ""
    assert got(vault_bootstrap_identity_oidc={}) == ""
    assert (
        got(vault_bootstrap_identity_oidc={"json": {"data": {"issuer": "https://v:8200"}}})
        == "https://v:8200"
    )


def test_bootstrap_when_expressions_are_balanced_and_parse(role_dir):
    """An unbalanced paren inside a quoted `when:` scalar made the WHOLE task
    file fail to parse, which silently killed every other bootstrap task too."""
    with open(os.path.join(role_dir, "tasks", "bootstrap.yml")) as f:
        text = f.read()
    assert yaml.safe_load(text) is not None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("when:"):
            continue
        expr = stripped[len("when:") :].strip().strip('"').strip("'")
        assert expr.count("(") == expr.count(")"), "unbalanced parens in: " + stripped


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


def test_backup_requires_keys_unless_force(role_dir, tmp_path):
    mod = _load_backup_module()
    old_env = os.environ.get("VAULT_BACKUP_UNSEAL_KEYS")
    for var in ("VAULT_BACKUP_UNSEAL_KEYS", "VAULT_BACKUP_ROOT_TOKEN"):
        os.environ.pop(var, None)
    real_default = mod.KEYRING_FILE
    mod.KEYRING_FILE = str(tmp_path / "absent.gpg")
    try:
        args = type("Args", (), {"keys_file": None, "keyring": None, "force": False})()
        assert mod.load_keys(args) == ([], None, None)
    finally:
        mod.KEYRING_FILE = real_default
    if old_env is not None:
        os.environ["VAULT_BACKUP_UNSEAL_KEYS"] = old_env


@pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg not installed")
def test_backup_autodiscovers_default_keyring(role_dir, tmp_path):
    """With no --keyring and no --keys-file, backup must find the keyring that
    restore wrote to the DEFAULT path — the flag default is None, so the
    fallback has to live in load_keys, not in argparse."""
    mod = _load_backup_module()
    real_default = mod.KEYRING_FILE
    default_path = str(tmp_path / "vault-backup" / "keys.gpg")
    mod.KEYRING_FILE = default_path
    try:
        mod.write_keyrings([default_path], ["dk1"], "hvs.default")
        for var in ("VAULT_BACKUP_UNSEAL_KEYS", "VAULT_BACKUP_ROOT_TOKEN"):
            os.environ.pop(var, None)
        args = type("Args", (), {"keys_file": None, "keyring": None, "force": False})()
        assert mod.load_keys(args) == (["dk1"], "hvs.default", default_path)
    finally:
        mod.KEYRING_FILE = real_default


def test_backup_keyring_codec_inferred_from_suffix(role_dir):
    """A .gpg path is the gpg keyring, anything else a plaintext 0400 file."""
    mod = _load_backup_module()
    assert mod._is_gpg_keyring("/etc/vault-backup/keys.gpg")
    assert not mod._is_gpg_keyring("{{ ctlabs_ansible_repo_dir }}/.ctlabs_vault_init_output_vdb1.yml")
    assert mod._key_file_for("/etc/vault-backup/keys.gpg") == \
        "/etc/vault-backup/passphrase"


def test_backup_keyring_never_shares_ctlabs_tools_session_cache(role_dir):
    """The unseal key + root token must NOT live in ctlabs-tools' session-cache
    dir: 'vault-login clear' deletes that passphrase file and 'vault-login user'
    overwrites it, either of which would destroy the only copy of the keys."""
    mod = _load_backup_module()
    tools_dir = os.path.expanduser("~/.ctlabs_vault")
    for path in (mod.KEYRING_DIR, mod.KEYRING_FILE, mod.KEYRING_KEY_FILE,
                 os.path.dirname(mod._key_file_for(mod.KEYRING_FILE))):
        assert os.path.abspath(path) != os.path.abspath(tools_dir)
        assert not os.path.abspath(path).startswith(os.path.abspath(tools_dir) + os.sep), \
            f"{path} is inside the ctlabs-tools session cache dir ({tools_dir})"
    assert os.path.basename(mod.KEYRING_KEY_FILE) != ".vault_key"
    assert os.path.basename(mod.KEYRING_FILE) != ".env.gpg"


@pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg not installed")
def test_backup_keyring_gpg_roundtrip(role_dir, tmp_path):
    """Restore's persisted keyring must be readable by a later backup: no
    plaintext token on disk, and the passphrase stays out of argv."""
    mod = _load_backup_module()
    path = str(tmp_path / "keys.gpg")
    keys = ["dG9rZW4xMjNIMDAwMTIzNA=="]
    root = "hvs.rootToken"
    mod.write_keyrings([path], keys, root)

    assert open(path, "rb").read().find(root.encode()) == -1, "token must not be plaintext"
    key_file = mod._key_file_for(path)
    assert oct(os.stat(key_file).st_mode & 0o777) == "0o600"

    args = type("Args", (), {"keys_file": None, "keyring": [path], "force": False})()
    for var in ("VAULT_BACKUP_UNSEAL_KEYS", "VAULT_BACKUP_ROOT_TOKEN"):
        os.environ.pop(var, None)
    assert mod.load_keys(args) == (keys, root, path)


@pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg not installed")
def test_backup_keyring_passphrase_not_on_argv(role_dir, tmp_path):
    """The passphrase must reach gpg via --passphrase-file, never argv: argv is
    world-readable through ps for the life of the process."""
    mod = _load_backup_module()
    seen = []
    real = subprocess.run

    def spy(argv, **kw):
        seen.append(argv)
        return real(argv, **kw)

    mod.subprocess.run = spy
    try:
        mod.seal_keyring(str(tmp_path / "keys.gpg"), ["k1"], "hvs.tok")
    finally:
        mod.subprocess.run = real
    assert seen, "gpg was never invoked"
    for argv in seen:
        assert "--passphrase-file" in argv
        assert "hvs.tok" not in " ".join(argv)


def test_backup_keyring_plain_codec_matches_init_output_format(role_dir, tmp_path):
    """The plaintext codec writes the init-output shape so bootstrap.yml
    (from_yaml) and --keys-file can consume the same file."""
    mod = _load_backup_module()
    path = str(tmp_path / "init-output.yml")
    keys = ["aaa", "bbb"]
    mod.write_keyrings([path], keys, "hvs.tok")
    assert oct(os.stat(path).st_mode & 0o777) == "0o400"
    assert mod.open_keyring(path) == (keys, "hvs.tok")
    assert mod._load_keys_from_file(path) == (keys, "hvs.tok")


def test_backup_keyring_write_is_idempotent_and_preserves_old(role_dir, tmp_path):
    """Re-running restore with the same keys must not churn the file; different
    keys must keep a copy of the previous keyring (it may be the only working
    one for a vault the operator did not mean to replace)."""
    mod = _load_backup_module()
    path = str(tmp_path / "keys.gpg")
    mod.write_keyrings([path], ["k1"], "hvs.a")
    first = open(path, "rb").read()
    mod.write_keyrings([path], ["k1"], "hvs.a")
    assert open(path, "rb").read() == first
    assert not [p for p in os.listdir(tmp_path) if ".pre-" in p]

    mod.write_keyrings([path], ["k2"], "hvs.b")
    assert mod.open_keyring(path) == (["k2"], "hvs.b")
    kept = [p for p in os.listdir(tmp_path) if ".pre-" in p]
    assert len(kept) == 1, "the replaced keyring must be kept"
    assert oct(os.stat(os.path.join(tmp_path, kept[0])).st_mode & 0o777) == "0o600"


def test_backup_restore_writes_keyring_then_backup_needs_no_flags(role_dir, tmp_path):
    """The reported bug end-to-end at the unit level: the keys that come out of
    an archive are the only ones that can unlock the restored vault, so restore
    must persist them and backup must find them without --keys-file."""
    mod = _load_backup_module()
    data = tmp_path / "data"
    data.mkdir()
    (data / "core").write_text("vault core")
    keys, root = ["SGVsbG8xMjNIMDA9=="], "hvs.restoredRoot"
    payload = mod.build_payload({"kind": "full", "node": "t",
                                 "vault_unseal_keys_b64": keys,
                                 "vault_root_token": root}, str(data))

    keyring = str(tmp_path / "keys.gpg")
    meta = mod.read_payload_meta(payload)
    mod.write_keyrings([keyring], meta["vault_unseal_keys_b64"], meta["vault_root_token"])

    for var in ("VAULT_BACKUP_UNSEAL_KEYS", "VAULT_BACKUP_ROOT_TOKEN"):
        os.environ.pop(var, None)
    args = type("Args", (), {"keys_file": None, "keyring": [keyring], "force": False})()
    assert mod.load_keys(args) == (keys, root, keyring)

    archived = mod.build_payload({"kind": "full", "node": "t",
                                  "vault_unseal_keys_b64": keys,
                                  "vault_root_token": root}, str(data))
    assert mod.read_payload_meta(archived)["vault_unseal_keys_b64"] == keys


def test_backup_keyring_write_survives_corrupt_existing(role_dir, tmp_path):
    """A corrupt pre-existing keyring must not abort the restore's last step:
    it is preserved and overwritten, not fatal."""
    mod = _load_backup_module()
    path = str(tmp_path / "keys.gpg")
    with open(path, "wb") as f:
        f.write(b"not a gpg message at all")
    mod.write_keyrings([path], ["k9"], "hvs.t9")
    assert mod.open_keyring(path) == (["k9"], "hvs.t9")
    assert [p for p in os.listdir(tmp_path) if ".pre-" in p]


def test_backup_keyring_no_keyring_flag_skips_write(role_dir):
    mod = _load_backup_module()
    assert mod.write_keyrings([], ["k"], "hvs.t") == []


def jinja2_env():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _render_timer(role_dir, name, **overrides):
    env = jinja2_env()
    ctx = {
        "ctlabs_vault": {
            "defaults": {
                "files": {
                    "backup": {
                        "script": "vault-backup.py",
                        "dst": "/usr/sbin/vault-backup.py",
                    }
                },
                "config": {
                    "backup": dict(
                        {
                            "passphrase": "",
                            "passphrase_file": "/etc/vault-backup.pw",
                            "command": "backup-full",
                            "on_calendar": "*-*-* 03:17:00",
                            "random_delay": "15m",
                            "persistent": True,
                            "out_dir": "/var/backups/vault",
                            "log_file": "/var/log/vault-backup.log",
                        },
                        **overrides
                    )
                },
                "service": {
                    "backup": {
                        "service": "vault-backup.service",
                        "timer": "vault-backup.timer",
                    }
                },
            }
        }
    }
    with open(os.path.join(role_dir, "templates", name)) as f:
        return env.from_string(f.read()).render(**ctx)


def test_backup_timer_renders_onschedule_and_unit(role_dir):
    out = _render_timer(role_dir, "vault-backup.timer.j2")
    assert "OnCalendar=*-*-* 03:17:00" in out
    assert "RandomizedDelaySec=15m" in out
    assert "Unit=vault-backup.service" in out
    assert "WantedBy=timers.target" in out


def test_backup_timer_catches_up_after_downtime(role_dir):
    """Persistent=true is what makes a backup happen at all if the box was off
    at 03:17 -- a backup that silently skips a day is worse than a late one."""
    assert "Persistent=true" in _render_timer(role_dir, "vault-backup.timer.j2")


def test_backup_timer_persistent_is_optional(role_dir):
    out = _render_timer(role_dir, "vault-backup.timer.j2", persistent=False)
    assert "Persistent" not in out


def test_backup_service_runs_backup_full_with_passphrase_file(role_dir):
    out = _render_timer(role_dir, "vault-backup.service.j2")
    assert "/usr/sbin/vault-backup.py backup-full" in out
    assert "--passphrase-file /etc/vault-backup.pw" in out
    assert "Type=oneshot" in out


def test_backup_service_never_contains_the_passphrase(role_dir):
    """The unit passes a FILE PATH; the secret itself must never reach argv
    (it would be world-readable in `ps`) or the unit file (0644)."""
    out = _render_timer(role_dir, "vault-backup.service.j2", passphrase="s3cr3t-passphrase")
    assert "s3cr3t-passphrase" not in out


def test_backup_service_does_not_require_vault_service(role_dir):
    """vault-backup.py stops the vault mid-run. A `Requires=vault.service` would
    make that explicit stop propagate and systemd would kill the job before the
    archive is written, so only After= is correct."""
    out = _render_timer(role_dir, "vault-backup.service.j2")
    # real directives only -- the unit carries a comment explaining this very trap
    directives = [
        ln.strip()
        for ln in out.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    unit = directives[: directives.index("[Service]")]
    assert any(d.startswith("After=") for d in unit), "want After="
    assert not any(
        d.startswith(("Requires=", "BindsTo=", "PartOf=")) for d in unit
    ), "no hard dependency on vault.service, or the mid-run stop kills this job"


def test_backup_timer_is_skipped_not_failed_without_passphrase(role_dir):
    with open(os.path.join(role_dir, "tasks", "timer.yml")) as f:
        text = f.read()
    assert "timer.skip.no_passphrase" in text
    assert "passphrase | default('') | length) > 0" in text
    assert "no_log" in text, "writing the passphrase must not echo it into the log"


def test_backup_timer_asserts_passphrase_mode(role_dir):
    with open(os.path.join(role_dir, "tasks", "timer.yml")) as f:
        text = f.read()
    assert "0o600" in text and "0o400" in text
    assert "passphrase.mode_ok" in text


def test_backup_timer_only_enables_the_timer_not_the_service(role_dir):
    """Type=oneshot service must be left to the timer, not 'started' by the role."""
    tasks = _load_tasks(role_dir, "timer.yml")

    def names(block):
        return [t.get("name", "") for t in _all_tasks(block)]

    started = [n for n in names(tasks) if "timer.enable" in n]
    assert started, "expected an enable task for the timer"
    svc_tasks = [
        t
        for t in _all_tasks(tasks)
        if t.get("service", {}).get("enabled") is True
    ]
    assert len(svc_tasks) == 1, "only the timer should be enabled/started"
    name = svc_tasks[0]["service"]["name"]
    assert "service.backup.timer" in name
    assert "service.backup.service" not in name


def test_main_imports_timer(role_dir):
    with open(os.path.join(role_dir, "tasks", "main.yml")) as f:
        text = f.read()
    assert "import_tasks: timer.yml" in text
    assert "ctlabs_vault.timer" in text
