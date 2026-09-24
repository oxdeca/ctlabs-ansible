# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_ca/tests/test_ctlabs_ca.py
# Description : pytest tests for ctlabs_ca role
# ------------------------------------------------------------------------------

import os
import subprocess


def test_templates_exist(role_dir):
    for name in ["ca.cnf.j2", "certs.cnf.j2", "facts.json.j2"]:
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
