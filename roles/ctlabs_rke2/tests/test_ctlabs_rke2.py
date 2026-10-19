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
    env.filters["lower"] = lambda v: str(v).lower()
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
        "templates/rke2-control.service.j2",
        "templates/rke2-agent.service.j2",
        "templates/rke2-agent.sysconfig.j2",
        "templates/rke2.profile.j2",
        "templates/rke2.config.yaml.j2",
        "templates/coredns-helmchartconfig.yml.j2",
        "templates/cilium-helmchartconfig.yml.j2",
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
        env={**os.environ, "PATH": os.environ.get("PATH", "") + ":/usr/local/bin"},
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def _render_unit(template, **overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template(template)
    ctx = {
        "ctlabs_rke2": {"defaults": {"pkgs": {"rke2": {"path": "/usr/bin/rke2"}}}},
        "ctlabs_rke2_ingress_enabled": False,
        "ctlabs_rke2_ingress_type": "nginx",
        "ctlabs_rke2_servicelb_enabled": False,
        "ctlabs_rke2_cni": "canal",
    }
    ctx.update(overrides)
    return tpl.render(ctx).split("ExecStart=")[1].split("\n")[0].strip()


def _render_config_yaml(**overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template("rke2.config.yaml.j2")
    ctx = {
        "ctlabs_rke2_ingress_enabled": True,
        "ctlabs_rke2_ingress_type": "nginx",
        "ctlabs_rke2_servicelb_enabled": False,
        "ctlabs_rke2_cni": "canal",
        "ctlabs_rke2_cilium_kube_proxy_replacement": True,
    }
    ctx.update(overrides)
    return tpl.render(ctx)


def test_cni_default_is_canal():
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_rke2"]["defaults"]["config"]
    assert defaults["cni"] == "canal"
    assert defaults["cni_supported"] == ["canal", "cilium", "multus", "none"]


def test_cilium_defaults():
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_rke2"]["defaults"]["config"]
    assert defaults["cilium"]["kube_proxy_replacement"] is True
    assert defaults["cilium"]["operator_replicas"] == 1


def test_cni_facts_forward_only_when_set():
    env = _facts_env()
    tpl = env.get_template("facts.json.j2")
    opted_in = json.loads(tpl.render(ctlabs_role_facts={"cni": "cilium"}, CTLABS_HOST="rke21"))
    assert opted_in["cni"] == "cilium"
    silent = json.loads(tpl.render(ctlabs_role_facts={}, CTLABS_HOST="rke21"))
    assert "cni" not in silent, "a default written here would shadow precheck's fallback"
    assert "cilium" not in silent, "a default written here would shadow precheck's fallback"


def test_cilium_facts_forward_when_set():
    env = _facts_env()
    tpl = env.get_template("facts.json.j2")
    opted_in = json.loads(
        tpl.render(
            ctlabs_role_facts={"cni": "cilium", "cilium": {"kube_proxy_replacement": True, "operator_replicas": 1}},
            CTLABS_HOST="rke21",
        )
    )
    assert opted_in["cilium"]["kube_proxy_replacement"] is True
    assert opted_in["cilium"]["operator_replicas"] == 1


def test_cni_precheck_resolves_fact_and_validates():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    resolve = next(t for t in precheck if t.get("name") == "ctlabs_rke2.tasks.precheck.cni")
    expr = resolve["set_fact"]["ctlabs_rke2_cni"]
    assert "ctg_facts.ctlabs_rke2.cni" in expr
    assert "ctlabs_rke2.defaults.config.cni" in expr
    supported = next(t for t in precheck if t.get("name") == "ctlabs_rke2.tasks.precheck.cni.supported")
    assert "ctlabs_rke2_cni in ctlabs_rke2.defaults.config.cni_supported" in supported["assert"]["that"]


def test_cilium_precheck_resolves_facts():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    kpr = next(t for t in precheck if t.get("name") == "ctlabs_rke2.tasks.precheck.cilium.kube_proxy_replacement")
    expr = kpr["set_fact"]["ctlabs_rke2_cilium_kube_proxy_replacement"]
    assert "ctg_facts.ctlabs_rke2.cilium.kube_proxy_replacement" in expr
    assert "ctlabs_rke2.defaults.config.cilium.kube_proxy_replacement" in expr
    replicas = next(t for t in precheck if t.get("name") == "ctlabs_rke2.tasks.precheck.cilium.operator_replicas")
    expr = replicas["set_fact"]["ctlabs_rke2_cilium_operator_replicas"]
    assert "ctg_facts.ctlabs_rke2.cilium.operator_replicas" in expr
    assert "ctlabs_rke2.defaults.config.cilium.operator_replicas" in expr


def test_server_unit_is_flagless():
    """All cluster flags moved to /etc/rancher/rke2/config.yaml — units stay static."""
    for tpl in ("rke2-server.service.j2", "rke2-control.service.j2"):
        assert _render_unit(tpl) == "/usr/bin/rke2 server"
        assert _render_unit(tpl, ctlabs_rke2_cni="cilium") == "/usr/bin/rke2 server"


def test_config_yaml_default_is_empty():
    """canal + nginx ingress + no servicelb → no keys, stock rke2 behaviour."""
    rendered = _render_config_yaml()
    assert "cni" not in rendered
    assert "disable" not in rendered
    assert "enable-servicelb" not in rendered
    assert "disable-kube-proxy" not in rendered


def test_config_yaml_cilium_disables_kube_proxy():
    rendered = _render_config_yaml(ctlabs_rke2_cni="cilium", ctlabs_rke2_ingress_enabled=False)
    assert "cni: cilium" in rendered
    assert "disable-kube-proxy: true" in rendered
    assert "disable:\n  - rke2-ingress-nginx" in rendered


def test_config_yaml_kube_proxy_flag_follows_the_knob():
    rendered = _render_config_yaml(ctlabs_rke2_cni="cilium", ctlabs_rke2_cilium_kube_proxy_replacement=False)
    assert "cni: cilium" in rendered
    assert "disable-kube-proxy" not in rendered


def test_config_yaml_servicelb():
    rendered = _render_config_yaml(ctlabs_rke2_servicelb_enabled=True)
    assert "enable-servicelb: true" in rendered


def test_config_yaml_task_writes_unified_config(role_dir):
    with open(os.path.join(ROLE_TASKS, "config.yml")) as f:
        config = yaml.safe_load(f)
    task = next(t for t in config if t.get("name") == "ctlabs_rke2.tasks.config.rke2.config_yaml")
    assert task["when"] == 'ctlabs_rke2_role in ["server", "control"]'
    assert " ".join(task["template"]["dest"].split()) == "{{ ctlabs_rke2.defaults.config.config_yaml.file }}"
    assert task["notify"] == "ctlabs_rke2.handlers.{{ ctlabs_rke2_role }}.systemd.reload"


def test_cilium_helmchartconfig_render():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template("cilium-helmchartconfig.yml.j2")

    with_kpr = yaml.safe_load(
        tpl.render(
            ctlabs_rke2_cilium_kube_proxy_replacement=True,
            ctlabs_rke2_cilium_operator_replicas=1,
            ctlabs_rke2_gateway_api_enabled=True,
            ctlabs_rke2_gateway_api_provider="cilium",
        )
    )
    assert with_kpr["kind"] == "HelmChartConfig"
    assert with_kpr["metadata"]["name"] == "rke2-cilium"
    values = with_kpr["spec"]["valuesContent"]
    assert "kubeProxyReplacement: true" in values
    assert "replicas: 1" in values
    assert "gatewayAPI:\n  enabled: true" in values

    without_kpr = yaml.safe_load(
        tpl.render(
            ctlabs_rke2_cilium_kube_proxy_replacement=False,
            ctlabs_rke2_cilium_operator_replicas=1,
            ctlabs_rke2_gateway_api_enabled=True,
            ctlabs_rke2_gateway_api_provider="traefik",
        )
    )
    values = without_kpr["spec"]["valuesContent"]
    assert "kubeProxyReplacement" not in values
    assert "gatewayAPI" not in values, "traefik labs must not get cilium's Gateway API"


def test_kube_proxy_stale_manifest_cleanup(role_dir):
    """rke2 never removes an existing kube-proxy static pod manifest when
    disable-kube-proxy flips on — the role must, or the pod stays forever."""
    with open(os.path.join(ROLE_TASKS, "config.yml")) as f:
        config = yaml.safe_load(f)
    task = next(t for t in config if t.get("name") == "ctlabs_rke2.tasks.config.kube_proxy.static_manifest.absent")
    when = task["when"] if isinstance(task["when"], str) else " ".join(task["when"])
    assert "server" in when and "cilium" in when and "kube_proxy_replacement" in when
    assert task["file"]["state"] == "absent"
    with open(os.path.join(ROLE_TASKS, os.pardir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_rke2"]["defaults"]["config"]
    assert defaults["kube_proxy_manifest"].endswith("kube-proxy.yaml")


def test_cilium_helmchartconfig_tasks_are_server_only_and_ordered(role_dir):
    with open(os.path.join(ROLE_TASKS, "config.yml")) as f:
        config = yaml.safe_load(f)
    dir_task = next(t for t in config if t.get("name") == "ctlabs_rke2.tasks.config.cilium.manifests.dir")
    write_task = next(t for t in config if t.get("name") == "ctlabs_rke2.tasks.config.cilium.helmchartconfig")
    for task in (dir_task, write_task):
        when = task["when"] if isinstance(task["when"], str) else " ".join(task["when"])
        assert "server" in when and "cilium" in when
    assert "cilium.helmchartconfig.file" in write_task["template"]["dest"]

    with open(os.path.join(ROLE_TASKS, "main.yml")) as f:
        main = yaml.safe_load(f)
    imports = [t["import_tasks"] for t in main if "import_tasks" in t]
    assert imports.index("config.yml") < imports.index("service.yml"), (
        "HelmChartConfig must land in the manifests dir before the server starts"
    )


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
