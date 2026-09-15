# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_helm/tests/test_ctlabs_helm.py
# Description : pytest tests for ctlabs_helm role
# ------------------------------------------------------------------------------

import os
import subprocess

import yaml

ROLE_TASKS = "/root/ctlabs-ansible/roles/ctlabs_helm/tasks"


def test_template_exists(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/charts.yml",
        "tasks/facts.yml",
        "defaults/main.yml",
        "templates/facts.json.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_helm.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_longhorn_guard_present():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    guard = next(t for t in precheck if t.get("name") == "ctlabs_helm.tasks.precheck.longhorn.guard")
    assert "play_setup['k8s'] is defined" in guard["when"]
    inner = [t.get("name") for t in guard["block"]]
    assert "ctlabs_helm.tasks.precheck.longhorn.engine.fact" in inner
    assert "ctlabs_helm.tasks.precheck.longhorn.chart.fact" in inner
    assert "ctlabs_helm.tasks.precheck.longhorn.engine.required" in inner
    asrt = next(
        t for t in guard["block"]
        if t.get("name") == "ctlabs_helm.tasks.precheck.longhorn.engine.required"
    )
    that = asrt["assert"]["that"]
    cond = that if isinstance(that, str) else that[0]
    assert "ctlabs_helm_has_longhorn_chart" in cond
    assert "ctlabs_k8s_master_storage" in cond
    assert "'longhorn'" in cond


def test_longhorn_guard_chart_detection():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    guard = next(t for t in precheck if t.get("name") == "ctlabs_helm.tasks.precheck.longhorn.guard")
    fact = next(
        t for t in guard["block"]
        if t.get("name") == "ctlabs_helm.tasks.precheck.longhorn.chart.fact"
    )
    expr = fact["set_fact"]["ctlabs_helm_has_longhorn_chart"]
    assert "selectattr('chart', 'search', 'longhorn')" in expr
    assert "selectattr('name', 'equalto', 'longhorn')" in exp
