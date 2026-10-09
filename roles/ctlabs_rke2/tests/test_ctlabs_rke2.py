# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_rke2/tests/test_ctlabs_rke2.py
# Description : pytest tests for ctlabs_rke2 role
# ------------------------------------------------------------------------------

import json
import os
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader

ROLE_TASKS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tasks"))
ROLE_TEMPLATES = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "templates"))


def _facts_env():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    env.filters["to_json"] = json.dumps
    env.filters["lower"] = str.lower
    return env


def test_template_exists(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "tasks/service.yml",
        "tasks/ca_configmap.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/rke2-server.service.j2",
        "templates/rke2-agent.service.j2",
        "templates/rke2-agent.sysconfig.j2",
        "templates/rke2.profile.j2",
        "templates/coredns-helmchartconfig.yml.j2",
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


def test_ca_configmap_default_is_opt_out():
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_rke2"]["defaults"]["config"]
    assert defaults["ca_configmaps"] == [], (
        "role default must stay empty: the lab-wide default lives in "
        "inventories/group_vars/all/ctlabs.yml (ctg_ca_configmaps) so cluster "
        "roles stay app-agnostic; a copy here would be the argoapp-vault_ca drift "
        "all over again"
    )


def test_ca_configmap_group_vars_system_default():
    with open(os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "inventories", "group_vars", "all", "ctlabs.yml"))) as f:
        group_vars = yaml.safe_load(f)
    assert group_vars["ctg_ca_configmaps"] == [
        {"name": "ca-ctlabs-crt", "namespace": "security-tools", "key": "ca.crt", "file": "/etc/ca-ctlabs/ca-ctlabs.crt"}
    ], "every cluster should publish the lab CA by default (ctlabs_ca runs first)"


def test_ca_configmap_facts_forward_only_when_set():
    env = _facts_env()
    tpl = env.get_template("facts.json.j2")
    opted_in = json.loads(
        tpl.render(
            ctlabs_role_facts={
                "ca_configmaps": [{"name": "ca-ctlabs-crt", "namespace": "security-tools", "key": "ca.crt"}]
            },
            CTLABS_HOST="rke21",
        )
    )
    assert opted_in["ca_configmaps"][0]["namespace"] == "security-tools"
    silent = json.loads(tpl.render(ctlabs_role_facts={}, CTLABS_HOST="rke21"))
    assert "ca_configmaps" not in silent, "a default written here would shadow precheck's fallback"


def test_ca_configmap_precheck_resolves_fact():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    resolve = next(t for t in precheck if t.get("name") == "ctlabs_rke2.tasks.precheck.ca_configmaps")
    expr = resolve["set_fact"]["ctlabs_rke2_ca_configmaps"]
    assert "ctg_facts.ctlabs_rke2.ca_configmaps" in expr
    assert "ctg_ca_configmaps" in expr
    assert "ctlabs_rke2.defaults.config.ca_configmaps" in expr


def test_ca_configmap_task_is_declarative_and_ordered(role_dir):
    with open(os.path.join(ROLE_TASKS, "ca_configmap.yml")) as f:
        block = yaml.safe_load(f)[0]
    assert block["when"].startswith("ctlabs_rke2_ca_configmaps | length > 0")
    read, namespace, apply = block["block"]

    assert read["slurp"]["src"] == "{{ item['file'] | default('/etc/ca-ctlabs/ca-ctlabs.crt') }}"
    assert read["become"] is True
    assert read["changed_when"] is False

    for task in (namespace, apply):
        assert task["environment"]["KUBECONFIG"] == "/etc/rancher/rke2/rke2.yaml"
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
    assert imp["when"] == "ctlabs_rke2_role == 'server'"
    assert "ctlabs_rke2.service" in imp["tags"]
    assert "ctlabs_rke2.ca_configmap" in imp["tags"]
