# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_vault/tests/test_ctlabs_vault.py
# Description : pytest tests for ctlabs_vault role
# ------------------------------------------------------------------------------

import os
import subprocess


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
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
