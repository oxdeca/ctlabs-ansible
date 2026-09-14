# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_minikube/tests/test_ctlabs_minikube.py
# Description : pytest tests for ctlabs_minikube role
# ------------------------------------------------------------------------------

import json
import os
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = "/root/ctlabs-ansible/roles/ctlabs_minikube/templates"


def _iter_tasks(data):
    for entry in data:
        if isinstance(entry, dict) and "block" in entry:
            yield from _iter_tasks(entry["block"])
        elif isinstance(entry, dict):
            yield entry


def _uses_kubectl(task):
    for key in ("shell", "command"):
        val = task.get(key)
        if isinstance(val, str) and "kubectl" in val:
            return True
    return False


class _Joiner:
    def __init__(self, sep):
        self._first = True
        self._sep = sep

    def __call__(self):
        s = "" if self._first else self._sep
        self._first = False
        return s


def _facts_env():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    env.filters["to_json"] = json.dumps
    env.globals["joiner"] = lambda sep: _Joiner(sep)
    return env


def test_template_exists(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "tasks/facts.yml",
        "tasks/service.yml",
        "tasks/charts.yml",
        "tasks/prepull.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/facts.json.j2",
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
    env = dict(os.environ, ANSIBLE_ROLES_PATH=os.path.join(role_dir, os.pardir))
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_facts_repos_charts_passthrough():
    tpl = _facts_env().get_template("facts.json.j2")
    facts = {
        "repos": [{"name": "traefik", "repo_url": "https://traefik.github.io/charts"}],
        "charts": [
            {
                "name": "traefik",
                "chart": "traefik/traefik",
                "chart_version": "40.0.0",
                "namespace": "traefik",
                "skip_crds": True,
                "wait": True,
                "prepull": False,
            }
        ],
    }
    parsed = json.loads(tpl.render(ctlabs_role_facts=facts))
    assert parsed["repos"][0]["repo_url"] == "https://traefik.github.io/charts"
    assert parsed["charts"][0]["chart_version"] == "40.0.0"
    assert parsed["charts"][0]["skip_crds"] is True
    assert parsed["charts"][0]["prepull"] is False


def test_facts_empty_valid_json():
    parsed = json.loads(_facts_env().get_template("facts.json.j2").render(ctlabs_role_facts={}))
    assert parsed == {}


def test_facts_repos_only_valid_json():
    facts = {"repos": [{"name": "argo", "repo_url": "https://argoproj.github.io/argo-helm"}]}
    parsed = json.loads(_facts_env().get_template("facts.json.j2").render(ctlabs_role_facts=facts))
    assert len(parsed["repos"]) == 1


def test_raw_kubectl_tasks_set_kubeconfig(role_dir):
    offenders = []
    for tf in ("charts.yml", "proxy.yml"):
        path = os.path.join(role_dir, "tasks", tf)
        with open(path) as fh:
            data = yaml.safe_load(fh)
        for task in _iter_tasks(data):
            if not _uses_kubectl(task):
                continue
            env = task.get("environment")
            if not env or "KUBECONFIG" not in str(env):
                offenders.append((tf, task.get("name")))
    assert not offenders, "Raw kubectl tasks missing KUBECONFIG: " + repr(offenders)
