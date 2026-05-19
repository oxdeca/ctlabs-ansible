# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_opendkim/tests/test_ctlabs_opendkim.py
# Description : pytest tests
# ------------------------------------------------------------------------------

import pytest
import os
import subprocess

def test_template_exists(role_dir):
    templates_dir = os.path.join(role_dir, 'templates')
    assert os.path.exists(os.path.join(templates_dir, 'opendkim.conf.j2'))
    assert os.path.exists(os.path.join(templates_dir, 'KeyTable.j2'))
    assert os.path.exists(os.path.join(templates_dir, 'SigningTable.j2'))
    assert os.path.exists(os.path.join(templates_dir, 'TrustedHosts.j2'))

def test_ansible_syntax_check(role_dir):
    test_playbook = os.path.join(role_dir, 'tests', 'test_opendkim.yml')
    # Run from repo root so roles/ can be found
    repo_root = os.path.abspath(os.path.join(role_dir, '..', '..'))
    env = os.environ.copy()
    env['ANSIBLE_ROLES_PATH'] = os.path.join(repo_root, 'roles')
    result = subprocess.run(
        ['ansible-playbook', '--syntax-check', test_playbook],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Syntax check failed: {result.stderr}"
