# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_manticore/tests/test_ctlabs_manticore.py
# Description : pytest tests for ctlabs_manticore role
# ------------------------------------------------------------------------------

import os
import subprocess


def test_template_exists(role_dir):
    path = os.path.join(role_dir, "defaults", "main.yml")
    assert os.path.isfile(path)


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_manticore.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
