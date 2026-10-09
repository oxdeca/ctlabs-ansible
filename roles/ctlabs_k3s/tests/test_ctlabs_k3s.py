# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_k3s/tests/test_ctlabs_k3s.py
# Description : pytest tests for ctlabs_k3s role
# ------------------------------------------------------------------------------

import json
import os
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "templates"))
ROLE_TASKS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tasks"))

K3S_PATH = "/usr/bin/k3s"


def _render_server_unit(**overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template("k3s-server.service.j2")
    ctx = {
        "ctlabs_k3s": {"defaults": {"pkgs": {"k3s": {"path": K3S_PATH}}}},
        "ctlabs_k3s_ingress_enabled": False,
        "ctlabs_k3s_ingress_type": "nginx",
        "ctlabs_k3s_gateway_api_enabled": True,
        "ctlabs_k3s_gateway_api_provider": "traefik",
        "ctlabs_k3s_servicelb_enabled": True,
    }
    ctx.update(overrides)
    rendered = tpl.render(ctx)
    return rendered.split("ExecStart=")[1].split("\n")[0]


def test_template_exists(role_dir):
    files = [
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "tasks/facts.yml",
        "tasks/service.yml",
        "tasks/ca_configmap.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/k3s-server.service.j2",
        "templates/k3s-control.service.j2",
        "templates/k3s-agent.service.j2",
        "templates/k3s-agent.sysconfig.j2",
        "templates/k3s.profile.j2",
        "templates/k3s-traefik-config.yml.j2",
        "templates/ingress-controller-lb.yml.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_k3s.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_server_unit_traefik_servicelb_on():
    cmd = _render_server_unit()
    assert cmd == f"{K3S_PATH} server --cluster-init"


def test_server_unit_traefik_servicelb_off():
    cmd = _render_server_unit(ctlabs_k3s_servicelb_enabled=False)
    assert cmd == f"{K3S_PATH} server --cluster-init --disable=servicelb"


def test_server_unit_nginx_servicelb_on():
    cmd = _render_server_unit(
        ctlabs_k3s_ingress_enabled=True,
        ctlabs_k3s_ingress_type="nginx",
        ctlabs_k3s_gateway_api_enabled=False,
    )
    assert cmd == f"{K3S_PATH} server --cluster-init --disable=traefik"


def test_server_unit_nginx_servicelb_off():
    cmd = _render_server_unit(
        ctlabs_k3s_ingress_enabled=True,
        ctlabs_k3s_ingress_type="nginx",
        ctlabs_k3s_gateway_api_enabled=False,
        ctlabs_k3s_servicelb_enabled=False,
    )
    assert cmd == f"{K3S_PATH} server --cluster-init --disable=traefik --disable=servicelb"


def test_server_unit_traefik_ingress_servicelb_off():
    cmd = _render_server_unit(
        ctlabs_k3s_ingress_type="traefik",
        ctlabs_k3s_servicelb_enabled=False,
    )
    assert cmd == f"{K3S_PATH} server --cluster-init --disable=servicelb"


def _facts_env():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    env.filters["to_json"] = json.dumps
    env.filters["lower"] = str.lower
    return env


def test_ca_configmap_default_is_opt_out():
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_k3s"]["defaults"]["config"]
    assert defaults["ca_configmaps"] == [], "empty default: no lab gains a ConfigMap unless asked"


def test_ca_configmap_facts_forward_only_when_set():
    tpl = _facts_env().get_template("facts.json.j2")
    opted_in = json.loads(
        tpl.render(
            ctlabs_role_facts={"ca_configmaps": [{"name": "ca-ctlabs-crt", "namespace": "security-tools", "key": "ca.crt"}]},
            CTLABS_HOST="k3s1",
        )
    )
    assert opted_in["ca_configmaps"][0]["namespace"] == "security-tools"
    silent = json.loads(tpl.render(ctlabs_role_facts={}, CTLABS_HOST="k3s1"))
    assert "ca_configmaps" not in silent, "a default written here would shadow precheck's fallback"


def test_ca_configmap_precheck_resolves_fact():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    resolve = next(t for t in precheck if t.get("name") == "ctlabs_k3s.tasks.precheck.ca_configmaps")
    expr = resolve["set_fact"]["ctlabs_k3s_ca_configmaps"]
    assert "ctg_facts.ctlabs_k3s.ca_configmaps" in expr
    assert "ctlabs_k3s.defaults.config.ca_configmaps" in expr


def test_ca_configmap_task_is_declarative_and_ordered():
    with open(os.path.join(ROLE_TASKS, "ca_configmap.yml")) as f:
        block = yaml.safe_load(f)[0]
    assert block["when"].startswith("ctlabs_k3s_ca_configmaps | length > 0")
    read, namespace, apply = block["block"]

    assert read["slurp"]["src"] == "{{ item['file'] | default('/etc/ca-ctlabs/ca-ctlabs.crt') }}"
    assert read["become"] is True
    assert read["changed_when"] is False

    for task in (namespace, apply):
        assert task["environment"]["KUBECONFIG"] == "/etc/rancher/k3s/k3s.yaml"
        assert task["kubernetes.core.k8s"]["state"] == "present"
        assert "force" not in task["kubernetes.core.k8s"], "force needs a resourceVersion this task never reads"
        assert "command" not in task and "shell" not in task

    assert namespace["kubernetes.core.k8s"]["definition"]["kind"] == "Namespace"
    assert namespace["kubernetes.core.k8s"]["definition"]["metadata"]["name"] == "{{ item['namespace'] }}"
    assert apply["kubernetes.core.k8s"]["definition"]["kind"] == "ConfigMap"
    assert "b64decode" in str(apply["kubernetes.core.k8s"]["definition"]["data"])

    with open(os.path.join(ROLE_TASKS, "main.yml")) as f:
        main = yaml.safe_load(f)
    imports = [t["import_tasks"] for t in main if "import_tasks" in t]
    assert imports.index("ca_configmap.yml") > imports.index("service.yml"), "cluster must be up first"
    imp = next(t for t in main if t.get("import_tasks") == "ca_configmap.yml")
    assert imp["when"] == "ctlabs_k3s_role == 'server'"
    assert "ctlabs_k3s.service" in imp["tags"]
    assert "ctlabs_k3s.ca_configmap" in imp["tags"]
