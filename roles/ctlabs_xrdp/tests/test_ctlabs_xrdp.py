# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_xrdp/tests/test_ctlabs_xrdp.py
# Description : pytest tests for ctlabs_xrdp role
# ------------------------------------------------------------------------------

import os
import subprocess

import yaml

XRDP_INI_SECTION = "Xorg"
XRDP_INI_OPTION = "enable_dynamic_resizing"
XRDP_INI_VALUE = "false"
RESTART_HANDLER = "ctlabs_xrdp.handlers.service.restart"


def _read(path):
    with open(path) as f:
        return f.read()


def _run_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_xrdp.yml")
    repo_root = os.path.abspath(os.path.join(role_dir, "..", ".."))
    env = os.environ.copy()
    env["ANSIBLE_ROLES_PATH"] = os.path.join(repo_root, "roles")
    return subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )


def test_templates_exist(role_dir):
    for name in ["startwm.sh.j2", "terminalrc.j2", "tmux.conf.j2", "xsettings.xml.j2"]:
        path = os.path.join(role_dir, "templates", name)
        assert os.path.isfile(path), f"missing template: {name}"


def test_dynamic_resizing_disabled_for_xorg(role_dir):
    # Regression test. Dynamic resizing on xrdp 0.9.x segfaults the xrdp process
    # (neutrinolabs/xrdp#3590, fixed only in 0.10.5) or drops the connection
    # (xup shmat EINVAL). Flipping this back to "true" on 0.9.x reintroduces it.
    defaults = yaml.safe_load(_read(os.path.join(role_dir, "defaults", "main.yml")))
    xrdp_ini = defaults["ctlabs_xrdp"]["defaults"]["config"]["xrdp_ini"]

    settings = [
        item
        for item in xrdp_ini["settings"]
        if item["section"] == XRDP_INI_SECTION and item["option"] == XRDP_INI_OPTION
    ]
    assert settings, (
        f"defaults must pin {XRDP_INI_OPTION} in [{XRDP_INI_SECTION}] - without it "
        "every client resize triggers the 0.9.x xrdp crash"
    )
    for item in settings:
        assert str(item["value"]).lower() == XRDP_INI_VALUE, (
            f"{XRDP_INI_OPTION} must be {XRDP_INI_VALUE} while xrdp is < 0.10.5"
        )


def test_dynamic_resizing_setting_is_applied(role_dir):
    # The defaults entry is worthless if config.yml never writes it.
    tasks = yaml.safe_load(_read(os.path.join(role_dir, "tasks", "config.yml")))
    task = next(
        (t for t in tasks if t.get("name") == "ctlabs_xrdp.tasks.config.xrdp_ini"),
        None,
    )
    assert task is not None, "tasks/config.yml must apply the xrdp_ini settings"

    module = task.get("community.general.ini_file")
    assert module is not None, "xrdp_ini must be written with community.general.ini_file"
    assert module["path"] == "{{ ctlabs_xrdp.defaults.config.xrdp_ini.file }}"
    assert task.get("loop") == "{{ ctlabs_xrdp.defaults.config.xrdp_ini.settings }}"
    assert task.get("notify") == RESTART_HANDLER, (
        "changing xrdp.ini must restart xrdp or the fix never reaches the running process"
    )


def test_ansible_syntax_check(role_dir):
    result = _run_syntax_check(role_dir)
    assert result.returncode == 0, f"Syntax check failed: {result.stderr}"
