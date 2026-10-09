# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_minikube/tests/test_ctlabs_minikube.py
# Description : pytest tests for ctlabs_minikube role
# ------------------------------------------------------------------------------

import json
import os
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "templates"))
ROLE_TASKS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tasks"))


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
        "tasks/ca_configmap.yml",
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


def test_ca_configmap_default_is_opt_out():
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_minikube"]["defaults"]["config"]
    assert defaults["ca_configmaps"] == [], "role default is empty by design; the lab-wide default lives in group_vars/all/ctlabs.yml (ctg_ca_configmaps)"


def test_ca_configmap_facts_forward_only_when_set():
    tpl = _facts_env().get_template("facts.json.j2")
    opted_in = json.loads(
        tpl.render(ctlabs_role_facts={"ca_configmaps": [{"name": "ca-ctlabs-crt", "namespace": "security-tools", "key": "ca.crt"}]})
    )
    assert opted_in["ca_configmaps"][0]["namespace"] == "security-tools"
    silent = json.loads(tpl.render(ctlabs_role_facts={}))
    assert "ca_configmaps" not in silent, "a default written here would shadow precheck's fallback"


def test_ca_configmap_precheck_resolves_fact():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    resolve = next(t for t in precheck if t.get("name") == "ctlabs_minikube.tasks.precheck.ca_configmaps")
    expr = resolve["set_fact"]["ctlabs_minikube_ca_configmaps"]
    assert "ctg_facts.ctlabs_minikube.ca_configmaps" in expr
    assert "ctg_ca_configmaps" in expr
    assert "ctlabs_minikube.defaults.config.ca_configmaps" in expr


def test_ca_configmap_task_is_declarative_and_ordered():
    with open(os.path.join(ROLE_TASKS, "ca_configmap.yml")) as f:
        block = yaml.safe_load(f)[0]
    assert block["when"].startswith("ctlabs_minikube_ca_configmaps | length > 0")
    read, namespace, apply = block["block"]

    assert read["slurp"]["src"] == "{{ item['file'] | default('/etc/ca-ctlabs/ca-ctlabs.crt') }}"
    assert read["become"] is True
    assert read["changed_when"] is False

    for task in (namespace, apply):
        assert "KUBECONFIG" in str(task["environment"])
        assert "ctlabs_minikube.defaults.proxy.kubeconfig" in task["environment"]["KUBECONFIG"]
        assert task["kubernetes.core.k8s"]["state"] == "present"
        assert "force" not in task["kubernetes.core.k8s"], "force needs a resourceVersion this task never reads"
        assert "command" not in task and "shell" not in task

    assert namespace["kubernetes.core.k8s"]["definition"]["kind"] == "Namespace"
    assert namespace["kubernetes.core.k8s"]["definition"]["metadata"]["name"] == "{{ item['namespace'] }}"
    assert apply["kubernetes.core.k8s"]["definition"]["kind"] == "ConfigMap"
    assert "b64decode" in str(apply["kubernetes.core.k8s"]["definition"]["data"])
    assert (
        apply["kubernetes.core.k8s"]["definition"]["data"] == "{{ {item['key']: (_crt | b64decode)} }}"
    ), "config key must be built via the dict-filter: a literal YAML mapping key \"{{ item['key'] }}\": keeps the braces (data[{{ item['key'] }}] 422)"

    with open(os.path.join(ROLE_TASKS, "main.yml")) as f:
        main = yaml.safe_load(f)
    imports = [t["import_tasks"] for t in main if "import_tasks" in t]
    assert imports.index("ca_configmap.yml") > imports.index("service.yml"), "cluster must be up first"
    imp = next(t for t in main if t.get("import_tasks") == "ca_configmap.yml")
    assert "when" not in imp, "single-node minikube: publish whenever the knob is non-empty"
    assert "ctlabs_minikube.service" in imp["tags"]
    assert "ctlabs_minikube.ca_configmap" in imp["tags"]
