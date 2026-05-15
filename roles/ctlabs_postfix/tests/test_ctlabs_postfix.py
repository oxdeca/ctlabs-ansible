# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_postfix/tests/test_ctlabs_postfix.py
# Description : pytest tests for ctlabs_postfix role
# ------------------------------------------------------------------------------

import os
import subprocess


def test_template_exists(role_dir):
    path = os.path.join(role_dir, "templates", "main.cf.j2")
    assert os.path.isfile(path)


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_postfix.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
