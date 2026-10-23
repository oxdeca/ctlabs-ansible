# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_ca/tests/test_ctlabs_ca.py
# Description : pytest tests for ctlabs_ca role
# ------------------------------------------------------------------------------

import os
import shutil
import subprocess

import pytest
import yaml


def _load(role_dir, *parts):
    with open(os.path.join(role_dir, *parts)) as fh:
        return yaml.safe_load(fh)


def _flatten(tasks, inherited=""):
    # flatten blocks (and their rescue/always parts) into (task, effective when)
    out = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        when = "{} {}".format(inherited, task.get("when", ""))
        if "block" in task:
            out.extend(_flatten(task["block"], when))
            for part in ("rescue", "always"):
                if part in task:
                    out.extend(_flatten(task[part], when))
            continue
        out.append((task, when))
    return out


# modules that need a posix shell/interpreter - they do not run on a windows
# host (ansible.windows.setup/win_file/... are the windows counterparts)
POSIX_ONLY = (
    "file",
    "stat",
    "template",
    "group",
    "user",
    "command",
    "copy",
    "script",
    "service",
    "systemd",
    "lineinfile",
    "useradd",
    "apt",
    "yum",
    "dnf",
    "package",
)


def test_templates_exist(role_dir):
    for name in ["ca.cnf.j2", "certs.cnf.j2", "facts.json.j2", "facts.ps1.j2"]:
        path = os.path.join(role_dir, "templates", name)
        assert os.path.isfile(path), f"missing template: {name}"


def test_scripts_exist(role_dir):
    for name in ["create_ctlabs_ca.sh", "create_server_cert.sh"]:
        path = os.path.join(role_dir, "files", name)
        assert os.path.isfile(path), f"missing script: {name}"


def test_ca_and_cert_scripts_randomize_serial(role_dir):
    # Regression test: both the CA self-sign and the leaf-cert sign must pass
    # -set_serial with a fresh value, otherwise two CAs/certs sharing the same
    # issuer CN (e.g. a lab run inside a lab) collide on serial and Firefox
    # rejects them with SEC_ERROR_REUSED_ISSUER_AND_SERIAL.
    for name in ["create_ctlabs_ca.sh", "create_server_cert.sh"]:
        path = os.path.join(role_dir, "files", name)
        with open(path) as f:
            content = f.read()
        assert "-set_serial" in content, f"{name} does not randomize the cert serial"


def test_windows_ca_dir_configured(role_dir):
    defaults = _load(role_dir, "defaults", "main.yml")
    windows = defaults["ctlabs_ca"]["defaults"]["config"]["windows"]
    assert windows["dir"] == "C:/ProgramData/ca-ctlabs"
    # the ca directory holds private keys - it must not be world readable
    assert windows["acl"], "windows ca directory needs an acl"


def test_windows_fact_template_prints_json(role_dir):
    path = os.path.join(role_dir, "templates", "facts.ps1.j2")
    with open(path) as fh:
        content = fh.read()
    # stdout of the script is parsed as json by ansible.windows.setup
    assert "$ProgressPreference = 'SilentlyContinue'" in content
    assert "ConvertTo-Json -Compress" in content


def test_windows_fact_written_as_ps1_and_reread(role_dir):
    facts = _flatten(_load(role_dir, "tasks", "facts.yml"))
    writers = [t for t, _ in facts if "ansible.windows.win_template" in t]
    assert writers, "no windows fact writer"
    dest = writers[0]["ansible.windows.win_template"]["dest"]
    assert dest.endswith("ctlabs_ca.ps1"), dest

    precheck = _flatten(_load(role_dir, "tasks", "precheck.yml"))
    setup = [t for t, _ in precheck if "ansible.windows.setup" in t]
    assert setup, "windows facts are never re-read (no default fact_path)"
    assert setup[0]["ansible.windows.setup"]["fact_path"] == "{{ ctg_facts_dir }}"


def test_windows_only_tasks_use_windows_modules(role_dir):
    for name in ("precheck.yml", "config.yml", "ca.yml", "certs.yml", "facts.yml"):
        for task, when in _flatten(_load(role_dir, "tasks", name)):
            if "== 'windows'" not in when:
                continue
            modules = [k for k in task if k in POSIX_ONLY]
            windows = [k for k in task if k.startswith("ansible.windows.")]
            assert not modules, f"{name}: posix module {modules} in a windows only task"
            assert windows, f"{name}: windows only task without a ansible.windows.* module"


def test_posix_tasks_are_gated_for_windows(role_dir):
    for name in ("precheck.yml", "config.yml", "ca.yml", "certs.yml", "facts.yml"):
        for task, when in _flatten(_load(role_dir, "tasks", name)):
            modules = [k for k in task if k in POSIX_ONLY]
            if not modules:
                continue
            if task.get("delegate_to") == "localhost":
                # runs on the controller (linux) - openssl lives there
                continue
            assert "windows" in when, (
                f"{name}: {modules} is not gated for windows hosts"
            )


def test_ca_is_created_on_the_controller_once(role_dir):
    ca = _flatten(_load(role_dir, "tasks", "ca.yml"))
    scripts = [t for t, _ in ca if "script" in t]
    assert scripts, "no ca/cert script"
    for task in scripts:
        assert task.get("delegate_to") == "localhost", "openssl scripts must run on the controller"


def test_linux_truststore_install_kept(role_dir):
    ca = _flatten(_load(role_dir, "tasks", "ca.yml"))
    copies = [t for t, _ in ca if "copy" in t]
    assert copies, "ca cert is not installed anywhere"
    dests = " ".join(str(t["copy"].get("dest", "")) for t in copies)
    assert "cacerts" in dests, "ca cert is not installed in the linux trust store"


def test_windows_fact_wired_in_group_vars(ansible_repo_root):
    path = os.path.join(
        ansible_repo_root, "inventories", "group_vars", "all", "ctlabs.yml"
    )
    with open(path) as fh:
        content = fh.read()
    assert "'ctlabs_ca'" in content, "ctlabs_ca fact is not wired into ctg_facts"


CA_CNF = """\
[ req ]
default_bits       = 2048
distinguished_name = dn
prompt             = no
x509_extensions    = v3_ca

[ dn ]
CN                 = ca-ctlabs

[ v3_ca ]
basicConstraints   = critical, CA:TRUE
"""


def _run_ca_script(tmp_path, role_dir):
    script = tmp_path / "create_ctlabs_ca.sh"
    script.write_text(open(os.path.join(role_dir, "files", "create_ctlabs_ca.sh")).read())
    script.chmod(0o755)
    (tmp_path / "ca-ctlabs.cnf").write_text(CA_CNF)
    result = subprocess.run(
        [str(script), "ca-ctlabs.cnf"], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")
def test_ca_script_keeps_an_existing_ca(role_dir, tmp_path):
    # regression: a host that lost its copy of the ca triggers the create block
    # again - the controller must keep (not rotate) the existing lab ca.
    _run_ca_script(tmp_path, role_dir)
    crt = tmp_path / "ca-ctlabs.crt"
    first = crt.read_bytes()

    _run_ca_script(tmp_path, role_dir)
    assert crt.read_bytes() == first, "existing ca was regenerated"

    (tmp_path / "ca-ctlabs.key").unlink()
    _run_ca_script(tmp_path, role_dir)
    assert crt.read_bytes() != first, "ca was not recreated after losing the key"


def test_ansible_syntax_check(role_dir):
    test_playbook = os.path.join(role_dir, "tests", "test_ca.yml")
    repo_root = os.path.abspath(os.path.join(role_dir, "..", ".."))
    env = os.environ.copy()
    env["ANSIBLE_ROLES_PATH"] = os.path.join(repo_root, "roles")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", test_playbook],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed: {result.stderr}"
