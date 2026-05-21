# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_metallb/tests/test_ctlabs_metallb.py
# Description : tests
# ------------------------------------------------------------------------------

import pytest
import os
import subprocess


def test_template_existence(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "defaults/main.yml",
        "handlers/main.yml",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_syntax_check(role_dir, ansible_repo_root):
    playbook = os.path.join(role_dir, "tests", "test_metallb.yml")
    cmd = [
        "ansible-playbook",
        playbook,
        "--syntax-check",
    ]
    result = subprocess.run(cmd, cwd=ansible_repo_root, capture_output=True, text=True)
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
