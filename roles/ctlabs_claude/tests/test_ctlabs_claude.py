---

# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_claude/tests/test_claude.yml
# Description : test playbook for ctlabs_claude (syntax-check target)
# ------------------------------------------------------------------------------

- name: ctlabs_claude.test.run
  hosts: localhost
  connection: local
  gather_facts: true
  vars:
    ctg_os: debian12
    ctg_os_family: debian
  roles:
    - role: ctlabs_claude
root@c9-1:~/2026-09-30/ctlabs-ansible/roles/ctlabs_claude# cat tests/test_ctlabs_claude.py 
import os
import subprocess


def test_template_existence(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "tasks/service.yml",
        "tasks/facts.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/settings.json.j2",
        "templates/command.md.j2",
        "templates/nodejs.pref.j2",
        "templates/facts.json.j2",
        "templates/dnsmasq-claude.conf.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_claude.yml")
    env = dict(os.environ, ANSIBLE_ROLES_PATH=os.path.join(role_dir, os.pardir))
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"
