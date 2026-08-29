# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_aide/tests/test_ctlabs_aide.py
# Description : pytest tests for ctlabs_aide role
# ------------------------------------------------------------------------------

import os
import subprocess


def test_templates_exist(role_dir):
    for name in [
        "aide.conf.j2",
        "aide-check.service.j2",
        "aide-check.timer.j2",
        "aide-check.sh.j2",
        "aide-update.service.j2",
        "aide-update.sh.j2",
    ]:
        path = os.path.join(role_dir, "templates", name)
        assert os.path.isfile(path), f"missing template: {name}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_aide.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
