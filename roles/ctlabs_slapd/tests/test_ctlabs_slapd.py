# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_slapd/tests/test_ctlabs_slapd.py
# Description : pytest tests for ctlabs_slapd role
# ------------------------------------------------------------------------------

import os
import subprocess

import yaml


def _load(role_dir, *parts):
    with open(os.path.join(role_dir, *parts)) as fh:
        return yaml.safe_load(fh)


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_slapd.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_default_bind_method_is_simple(role_dir):
    # the weaker method stays the default - sasl/gssapi is opt-in
    defaults = _load(role_dir, "defaults", "main.yml")
    bind = defaults["ctlabs_slapd"]["defaults"]["config"]["dbs"]["ldap"]["bind"]
    assert bind["method"] == "simple"


def test_template_uses_nested_bind_map(role_dir):
    # the db entry's `bind` is a nested map (method/user/pass or
    # method/saslmech/authcid/realm/keytab), not flat bind_method/bind_user/
    # bind_pass keys - the template must read that same nested shape.
    with open(os.path.join(role_dir, "templates", "slapd.conf.j2")) as fh:
        text = fh.read()
    assert "db.bind.method" in text
    assert "db.bind_method" not in text


def test_gssapi_tasks_are_opt_in(role_dir):
    config = _load(role_dir, "tasks", "config.yml")
    krb5_task = next(t for t in config if t["name"].endswith("krb5.install"))
    assert "ctlabs_slapd_krb5.manage" in str(krb5_task["when"])
    assert "ctlabs_slapd_gssapi_enabled" in str(krb5_task["when"])
    for name in ("keytab.dir.exists", "keytab.install"):
        task = next(t for t in config if t["name"].endswith(name))
        assert "ctlabs_slapd_gssapi_enabled" in str(task["when"])


def test_client_keytab_not_server_keytab(role_dir):
    # this role binds TO the AD DC as a GSSAPI client (idassert-bind), so the
    # env var must be the *client* keytab, not the server acceptor keytab.
    with open(os.path.join(role_dir, "templates", "slapd.default.j2")) as fh:
        text = fh.read()
    assert "KRB5_CLIENT_KTNAME=" in text


def test_dbs_merged_by_suffix_before_gssapi_detection(role_dir):
    # lists append across profile levels (defaults + host), so partial items for
    # the same suffix must be merged before anything reads db.uri / db.bind.
    precheck = _load(role_dir, "tasks", "precheck.yml")
    names = [t["name"] for t in precheck if "name" in t]
    merge = next(n for n in names if n.endswith("dbs.merge"))
    assert names.index(merge) < next(i for i, n in enumerate(names) if n.endswith("gssapi.dbs"))
    task = next(t for t in precheck if t.get("name") == merge)
    assert "suffix" in str(task["set_fact"]["ctlabs_slapd_dbs"])


def test_client_keytab_reaches_the_daemon_via_systemd_dropin(role_dir):
    # RedHat's slapd.service has no EnvironmentFile, so /etc/default/slapd alone
    # leaves slapd without credentials ("No Kerberos credentials available").
    config = _load(role_dir, "tasks", "config.yml")
    task = next(t for t in config if t["name"].endswith("keytab.env"))
    assert "ctlabs_slapd_gssapi_enabled" in str(task["when"])
    assert "KRB5_CLIENT_KTNAME" in task["copy"]["content"]


def test_gssapi_over_ldaps_disables_the_sasl_security_layer(role_dir):
    # AD refuses SASL signing/sealing inside TLS; without maxssf=0 slapd fails
    # with "encoded packet size too big".
    with open(os.path.join(role_dir, "templates", "slapd.conf.j2")) as fh:
        assert "maxssf=0" in fh.read()
