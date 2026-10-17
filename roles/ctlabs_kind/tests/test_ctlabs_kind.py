# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_kind/tests/test_ctlabs_kind.py
# Description : pytest tests for ctlabs_kind role
# ------------------------------------------------------------------------------

import json
import os
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "templates"))
ROLE_TASKS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tasks"))


def _render_cluster_config(**overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template("kind-cluster.yml.j2")
    ctx = {
        "ctlabs_kind_name": "ctlabs",
        "ctlabs_kind_plane": "single",
        "ctlabs_kind_nodes": 1,
        "ctlabs_kind_ingress_enabled": False,
        "ctlabs_kind_gateway_api_enabled": False,
    }
    ctx.update(overrides)
    return tpl.render(ctx)


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
        "tasks/cilium.yml",
        "tasks/routing.yml",
        "tasks/proxy.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/facts.json.j2",
        "templates/kind-cluster.yml.j2",
        "templates/kind.profile.j2",
        "templates/gateway.yml.j2",
        "templates/gateway_ns.yml.j2",
        "templates/tls_secret.yml.j2",
        "templates/reference_grant.yml.j2",
        "templates/attachment_grant.yml.j2",
        "templates/httproute.yml.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_kind.yml")
    env = dict(os.environ, ANSIBLE_ROLES_PATH=os.path.join(role_dir, os.pardir))
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_cluster_single_node_no_ports():
    rendered = _render_cluster_config()
    assert "kind: Cluster" in rendered
    assert f"name: ctlabs" in rendered
    assert "- role: control-plane" in rendered
    assert "extraPortMappings" not in rendered
    assert "role: worker" not in rendered


def test_cluster_single_node_with_ports():
    rendered = _render_cluster_config(
        ctlabs_kind_ingress_enabled=True,
        ctlabs_kind_gateway_api_enabled=True,
    )
    assert "extraPortMappings" in rendered
    assert "containerPort: 80" in rendered
    assert "hostPort: 443" in rendered
    assert "role: worker" not in rendered


def test_cluster_multi_node():
    rendered = _render_cluster_config(
        ctlabs_kind_plane="multi",
        ctlabs_kind_nodes=3,
        ctlabs_kind_gateway_api_enabled=True,
    )
    assert "extraPortMappings" in rendered
    assert rendered.count("- role: worker") == 2
    assert rendered.count("- role: control-plane") == 1


def test_facts_charts_passthrough():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    env.filters["to_json"] = lambda v: json.dumps(v)
    env.filters["lower"] = str.lower
    tpl = env.get_template("facts.json.j2")
    facts = {
        "plane": "single",
        "repos": [{"name": "traefik", "repo_url": "https://traefik.github.io/charts"}],
        "charts": [
            {
                "name": "traefik",
                "chart": "traefik/traefik",
                "chart_version": "40.0.0",
                "namespace": "traefik",
                "skip_crds": True,
                "wait": True,
                "values": {"ports": {"web": {"hostPort": 80}}},
            }
        ],
    }
    parsed = json.loads(tpl.render(ctlabs_role_facts=facts, CTLABS_HOST="kind1", CTLABS_DOMAIN="ctlabs.internal"))
    assert parsed["repos"][0]["repo_url"] == "https://traefik.github.io/charts"
    assert parsed["charts"][0]["chart_version"] == "40.0.0"
    assert parsed["charts"][0]["skip_crds"] is True
    assert parsed["charts"][0]["values"]["ports"]["web"]["hostPort"] == 80


def test_ca_configmap_default_is_opt_out():
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_kind"]["defaults"]["config"]
    assert defaults["ca_configmaps"] == [], "role default is empty by design; the lab-wide default lives in group_vars/all/ctlabs.yml (ctg_ca_configmaps)"


def test_ca_configmap_facts_forward_only_when_set():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    env.filters["to_json"] = json.dumps
    env.filters["lower"] = str.lower
    tpl = env.get_template("facts.json.j2")
    opted_in = json.loads(
        tpl.render(
            ctlabs_role_facts={"ca_configmaps": [{"name": "ca-ctlabs-crt", "namespace": "security-tools", "key": "ca.crt"}]},
            CTLABS_HOST="kind1",
        )
    )
    assert opted_in["ca_configmaps"][0]["namespace"] == "security-tools"
    silent = json.loads(tpl.render(ctlabs_role_facts={}, CTLABS_HOST="kind1"))
    assert "ca_configmaps" not in silent, "a default written here would shadow precheck's fallback"


def test_ca_configmap_precheck_resolves_fact():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    resolve = next(t for t in precheck if t.get("name") == "ctlabs_kind.tasks.precheck.ca_configmaps")
    expr = resolve["set_fact"]["ctlabs_kind_ca_configmaps"]
    assert "ctg_facts.ctlabs_kind.ca_configmaps" in expr
    assert "ctg_ca_configmaps" in expr
    assert "ctlabs_kind.defaults.config.ca_configmaps" in expr


def test_ca_configmap_task_is_declarative_and_ordered():
    with open(os.path.join(ROLE_TASKS, "ca_configmap.yml")) as f:
        block = yaml.safe_load(f)[0]
    assert block["when"].startswith("ctlabs_kind_ca_configmaps | length > 0")
    read, namespace, apply = block["block"]

    assert read["slurp"]["src"] == "{{ item['file'] | default('/etc/ca-ctlabs/ca-ctlabs.crt') }}"
    assert read["become"] is True
    assert read["changed_when"] is False

    for task in (namespace, apply):
        assert task["environment"]["KUBECONFIG"] == "/root/.kube/config"
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
    assert "when" not in imp, "single-node kind: publish whenever the knob is non-empty"
    assert "ctlabs_kind.service" in imp["tags"]
    assert "ctlabs_kind.ca_configmap" in imp["tags"]


def _task_named(data, name):
    for entry in data:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    raise AssertionError(f"task {name!r} not found")


def test_cni_default_is_kindnet():
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)
    assert defaults["ctlabs_kind"]["defaults"]["config"]["cni"] == "kindnet"
    assert defaults["ctlabs_kind"]["defaults"]["config"]["cni_supported"] == ["kindnet", "cilium"]
    assert defaults["versions"]["cilium"] == "1.20.3"


def test_cni_facts_forward_only_when_set():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    env.filters["to_json"] = json.dumps
    env.filters["lower"] = str.lower
    tpl = env.get_template("facts.json.j2")
    opted_in = json.loads(tpl.render(ctlabs_role_facts={"cni": "cilium"}, CTLABS_HOST="kind1"))
    assert opted_in["cni"] == "cilium"
    silent = json.loads(tpl.render(ctlabs_role_facts={}, CTLABS_HOST="kind1"))
    assert "cni" not in silent, "a default written here would shadow precheck's fallback"


def test_cni_precheck_resolves_fact_and_validates():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    resolve = next(t for t in precheck if t.get("name") == "ctlabs_kind.tasks.precheck.cni")
    expr = resolve["set_fact"]["ctlabs_kind_cni"]
    assert "ctg_facts.ctlabs_kind.cni" in expr
    assert "ctlabs_kind.defaults.config.cni" in expr
    supported = next(t for t in precheck if t.get("name") == "ctlabs_kind.tasks.precheck.cni.supported")
    assert "ctlabs_kind_cni in ctlabs_kind.defaults.config.cni_supported" in supported["assert"]["that"]


def test_cluster_config_disable_default_cni_only_for_cilium():
    assert "networking" not in _render_cluster_config()
    assert "disableDefaultCNI" not in _render_cluster_config()
    cilium = _render_cluster_config(ctlabs_kind_cni="cilium")
    assert "networking" in cilium
    assert "disableDefaultCNI: true" in cilium


def test_cilium_installs_chart_with_kubernetes_ipam():
    with open(os.path.join(ROLE_TASKS, "cilium.yml")) as f:
        tasks = yaml.safe_load(f)
    install = _task_named(tasks, "ctlabs_kind.tasks.cilium.install")
    helm = install["kubernetes.core.helm"]
    assert helm["chart_ref"] == "cilium/cilium"
    assert helm["chart_version"] == "{{ versions.cilium }}"
    assert helm["release_namespace"] == "{{ ctlabs_kind.defaults.cilium.namespace }}"
    assert helm["values"] == "{{ ctlabs_kind.defaults.cilium.values }}"
    assert install["environment"]["KUBECONFIG"] == "/root/.kube/config"

    repo = _task_named(tasks, "ctlabs_kind.tasks.cilium.repo")
    assert repo["kubernetes.core.helm_repository"]["repo_url"] == "{{ ctlabs_kind.defaults.cilium.repo_url }}"

    load = _task_named(tasks, "ctlabs_kind.tasks.cilium.load")
    assert "kind load image-archive" in load["shell"]
    assert "--name {{ ctlabs_kind_name }}" in load["shell"]

    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        values = yaml.safe_load(f)["ctlabs_kind"]["defaults"]["cilium"]["values"]
    assert values["ipam"]["mode"] == "kubernetes", (
        "cluster-pool 10.0.0.0/8 overlaps kind's service subnet 10.96.0.0/12; use kubernetes IPAM"
    )
    assert values["image"]["pullPolicy"] == "IfNotPresent"


def test_cilium_included_in_service_before_ingress():
    with open(os.path.join(ROLE_TASKS, "service.yml")) as f:
        tasks = yaml.safe_load(f)
    names = [t.get("name") for t in tasks if isinstance(t, dict)]
    cilium = _task_named(tasks, "ctlabs_kind.tasks.service.cilium")
    assert cilium["when"] == 'ctlabs_kind_cni == "cilium"'
    assert cilium["include_tasks"] == "cilium.yml"
    assert names.index("ctlabs_kind.tasks.service.cilium") > names.index("ctlabs_kind.tasks.service.cluster.ready")
    assert names.index("ctlabs_kind.tasks.service.cilium") < names.index("ctlabs_kind.tasks.service.ingress")
