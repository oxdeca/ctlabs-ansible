# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_rke2/tests/test_ctlabs_rke2.py
# Description : pytest tests for ctlabs_rke2 role
# ------------------------------------------------------------------------------

import os
import subprocess


def test_template_exists(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "tasks/service.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/rke2-server.service.j2",
        "templates/rke2-agent.service.j2",
        "templates/rke2-agent.sysconfig.j2",
        "templates/rke2.profile.j2",
        "templates/traefik-values.yml.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_rke2.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
