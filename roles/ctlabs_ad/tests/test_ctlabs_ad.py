# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_ad/tests/test_ctlabs_ad.py
# Description : pytest tests for ctlabs_ad role
# ------------------------------------------------------------------------------

import os
import subprocess

import yaml


def _load(role_dir, *parts):
    with open(os.path.join(role_dir, *parts)) as fh:
        return yaml.safe_load(fh)


def test_template_exists(role_dir):
    path = os.path.join(role_dir, "templates", "facts.ps1.j2")
    assert os.path.isfile(path)


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_ad.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_main_branches_dc_and_member(role_dir):
    main = _load(role_dir, "tasks", "main.yml")
    imported = {}
    for task in main:
        if "import_tasks" in task:
            imported[task["import_tasks"]] = task

    # the DC path is gated on the resolved role
    assert "dc.yml" in imported
    assert "master" in str(imported["dc.yml"].get("when"))

    # join/leave/service remain member-only
    for name in ("join.yml", "leave.yml", "service.yml"):
        assert "member" in str(imported[name].get("when"))

    # leave is additionally gated on the per-host leave flag
    assert "ctlabs_ad_leave" in str(imported["leave.yml"].get("when"))


def test_no_global_env_vars(role_dir):
    # configuration is per-host (local fact) / role-scoped vars, never the
    # global CTLABS_AD_* environment variables (they leak across all roles).
    offenders = []
    for root, _dirs, files in os.walk(role_dir):
        if "__pycache__" in root or os.sep + "tests" in root:
            continue
        for name in files:
            if not name.endswith((".yml", ".j2")):
                continue
            path = os.path.join(root, name)
            with open(path) as fh:
                for lineno, line in enumerate(fh, 1):
                    if "CTLABS_AD_" in line:
                        offenders.append(f"{path}:{lineno}")
    assert not offenders, f"global CTLABS_AD_* vars found: {offenders}"


def test_dc_promotion_modules(role_dir):
    dc = _load(role_dir, "tasks", "dc.yml")
    used = {key for task in dc[0]["block"] for key in task}
    assert "microsoft.ad.domain" in used
    assert "microsoft.ad.domain_controller" in used
    assert "microsoft.ad.ou" in used
