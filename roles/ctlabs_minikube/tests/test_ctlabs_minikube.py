# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_minikube/tests/test_ctlabs_minikube.py
# Description : pytest tests for ctlabs_minikube role
# ------------------------------------------------------------------------------

import os
import subprocess


def test_template_exists(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "tasks/facts.yml",
        "tasks/service.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/minikube.profile.j2",
        "templates/minikube.service.j2",
        "templates/minikube-net.service.j2",
        "templates/minikube.sudo.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_minikube.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
