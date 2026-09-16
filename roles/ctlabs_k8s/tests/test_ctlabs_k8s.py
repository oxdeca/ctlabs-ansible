# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_k8s/tests/test_ctlabs_k8s.py
# Description : pytest tests for ctlabs_k8s role
# ------------------------------------------------------------------------------

import os
import subprocess

import yaml
import json
from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = "/root/ctlabs-ansible/roles/ctlabs_k8s/templates"
ROLE_TASKS = "/root/ctlabs-ansible/roles/ctlabs_k8s/tasks"


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


def _render_kubeadm_init(**overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template("kubeadm-init.yml.j2")
    ctx = {
        "ctlabs_k8s_join_token": "abcdef.0123456789abcdef",
        "ctlabs_k8s_cert_key": "0" * 64,
        "ctlabs_k8s_master_ip": "192.168.99.10",
        "ctlabs_k8s_pod_cidr": "10.8.0.0/16",
        "ctlabs_k8s": {
            "defaults": {
                "cluster": {
                    "k8s": {"version": "1.36.4"},
                }
            }
        },
    }
    ctx.update(overrides)
    return tpl.render(ctx)


def _render_kubeadm_join(role, **overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template("kubeadm-join.yml.j2")
    ctx = {
        "ansible_default_ipv4": {"address": "192.168.99.20"},
        "ctlabs_k8s_role": role,
        "ctlabs_k8s_join_apiserver": "192.168.99.10:6443",
        "ctlabs_k8s_join_token": "abcdef.0123456789abcdef",
        "ctlabs_k8s_join_ca_hash": "0" * 64,
        "ctlabs_k8s_join_cert_key": "1" * 64,
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
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/99-k8s.conf.j2",
        "templates/calico-custom-resources.yml.j2",
        "templates/containerd-config.toml.j2",
        "templates/crictl.yaml.j2",
        "templates/ctlabs_k8s.sh.j2",
        "templates/flannel.yml.j2",
        "templates/join-data.yml.j2",
        "templates/facts.json.j2",
        "templates/k8sall.sh.j2",
        "templates/kubeadm-init.yml.j2",
        "templates/kubeadm-join.yml.j2",
        "templates/kube-vip.yml.j2",
        "templates/versions.sh.j2",
        "templates/weave.yml.j2",
        "templates/local-path-provisioner.yml.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_k8s.yml")
    env = dict(os.environ, ANSIBLE_ROLES_PATH=os.path.join(role_dir, os.pardir))
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_kubeadm_init_valid_yaml():
    rendered = _render_kubeadm_init()
    docs = list(yaml.safe_load_all(rendered))
    kinds = [d["kind"] for d in docs if d]
    assert kinds == ["InitConfiguration", "ClusterConfiguration", "KubeletConfiguration"]


def test_kubeadm_init_values():
    rendered = _render_kubeadm_init()
    docs = list(yaml.safe_load_all(rendered))
    init, cluster, _ = docs
    assert init["bootstrapTokens"][0]["token"] == "abcdef.0123456789abcdef"
    assert init["localAPIEndpoint"]["advertiseAddress"] == "192.168.99.10"
    assert cluster["kubernetesVersion"] == "1.36.4"
    assert cluster["controlPlaneEndpoint"] == "192.168.99.10:6443"
    assert cluster["networking"]["podSubnet"] == "10.8.0.0/16"


def test_kubeadm_join_worker():
    rendered = _render_kubeadm_join("worker")
    join = list(yaml.safe_load_all(rendered))[0]
    assert join["kind"] == "JoinConfiguration"
    assert "controlPlane" not in join
    assert join["discovery"]["bootstrapToken"]["apiServerEndpoint"] == "192.168.99.10:6443"
    assert join["discovery"]["bootstrapToken"]["token"] == "abcdef.0123456789abcdef"
    assert join["discovery"]["bootstrapToken"]["caCertHashes"] == ["sha256:" + "0" * 64]
    assert join["nodeRegistration"]["kubeletExtraArgs"][0]["value"] == "192.168.99.20"


def test_kubeadm_join_control():
    rendered = _render_kubeadm_join("control")
    join = list(yaml.safe_load_all(rendered))[0]
    assert "controlPlane" in join
    assert join["controlPlane"]["certificateKey"] == "1" * 64
    assert join["localAPIEndpoint"]["advertiseAddress"] == "192.168.99.20"
    assert join["discovery"]["bootstrapToken"]["apiServerEndpoint"] == "192.168.99.10:6443"


def test_join_data_valid_yaml():
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    rendered = env.get_template("join-data.yml.j2").render(
        ctlabs_k8s_master_ip="192.168.99.10",
        ctlabs_k8s_join_token="abcdef.0123456789abcdef",
        ctlabs_k8s_cert_key="0" * 64,
        ctlabs_k8s_join_ca_hash="1" * 64,
    )
    data = list(yaml.safe_load_all(rendered))[0]
    assert data == {
        "api_server": "192.168.99.10:6443",
        "token": "abcdef.0123456789abcdef",
        "certificate_key": "0" * 64,
        "ca_cert_hash": "1" * 64,
    }


def test_facts_role_valid_json():
    facts = json.loads(
        _facts_env()
        .get_template("facts.json.j2")
        .render(ctlabs_role_facts={"role": "control", "master_node": "k8s1", "master_ip": "192.168.99.10", "storage": "none"})
    )
    assert facts == {"role": "control", "master_node": "k8s1", "master_ip": "192.168.99.10", "storage": "none"}


def test_facts_role_default_master():
    facts = json.loads(_facts_env().get_template("facts.json.j2").render(ctlabs_role_facts={}))
    assert facts == {"role": "master"}


def test_facts_storage_explicit():
    facts = json.loads(
        _facts_env().get_template("facts.json.j2").render(ctlabs_role_facts={"storage": "longhorn"})
    )
    assert facts["storage"] == "longhorn"


def test_facts_storage_absent_when_undeclared():
    facts = json.loads(
        _facts_env().get_template("facts.json.j2").render(ctlabs_role_facts={"role": "worker"})
    )
    assert "storage" not in facts


def _render_local_path(**overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    ctx = {
        "ctlabs_k8s": {
            "defaults": {
                "config": {
                    "storage": {
                        "local": {
                            "namespace": "kube-system",
                            "version": "v0.0.31",
                            "data_dir": "/media/vols",
                            "helper_image": "busybox:latest",
                        }
                    }
                }
            }
        },
    }
    ctx.update(overrides)
    return env.get_template("local-path-provisioner.yml.j2").render(ctx)


def test_local_path_valid_yaml():
    docs = [d for d in yaml.safe_load_all(_render_local_path()) if d]
    kinds = [d["kind"] for d in docs]
    assert kinds == [
        "Namespace",
        "ServiceAccount",
        "ClusterRole",
        "ClusterRoleBinding",
        "Role",
        "RoleBinding",
        "ConfigMap",
        "Deployment",
        "StorageClass",
    ]


def test_local_path_data_dir():
    docs = [d for d in yaml.safe_load_all(_render_local_path()) if d]
    cm = next(d for d in docs if d["kind"] == "ConfigMap")
    assert "/media/vols" in cm["data"]["config.json"]
    sc = next(d for d in docs if d["kind"] == "StorageClass")
    assert sc["metadata"]["annotations"]["storageclass.kubernetes.io/is-default-class"] == "true"
    assert sc["provisioner"] == "rancher.io/local-path"


def test_local_path_image_tag():
    docs = [d for d in yaml.safe_load_all(_render_local_path()) if d]
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    image = deploy["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image == "docker.io/rancher/local-path-provisioner:v0.0.31"


def test_local_path_helper_pod_mounted():
    docs = [d for d in yaml.safe_load_all(_render_local_path()) if d]
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    cm = next(d for d in docs if d["kind"] == "ConfigMap")
    vol = deploy["spec"]["template"]["spec"]["volumes"][0]["configMap"]
    assert vol["name"] == "local-path-config"
    assert "items" not in vol
    assert "setup" in cm["data"] and "teardown" in cm["data"]
    helper = yaml.safe_load(cm["data"]["helperPod.yaml"])
    assert helper["spec"]["containers"][0]["name"] == "helper-pod"


def test_local_path_provisioner_flags():
    docs = [d for d in yaml.safe_load_all(_render_local_path()) if d]
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    cont = deploy["spec"]["template"]["spec"]["containers"][0]
    assert "--helper-image" in cont["command"]
    assert "--configmap-name" in cont["command"]
    assert "local-path-config" in cont["command"]
    envs = {e["name"]: e.get("value") for e in cont["env"]}
    assert envs["CONFIG_MOUNT_PATH"] == "/etc/config/"


def test_precheck_storage_master_only():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    names = [t.get("name") for t in precheck]
    assert "ctlabs_k8s.tasks.precheck.storage.fact" in names
    assert "ctlabs_k8s.tasks.precheck.storage.master_only" in names
    fact = next(t for t in precheck if t.get("name") == "ctlabs_k8s.tasks.precheck.storage.fact")
    assert "ctlabs_k8s_storage_raw" in fact["set_fact"]
    assert "ctlabs_k8s_storage" in fact["set_fact"]
    assert "ctg_facts.ctlabs_k8s.storage" in fact["set_fact"]["ctlabs_k8s_storage"]
    assert "default('')" in fact["set_fact"]["ctlabs_k8s_storage"]
    assert "lower" in fact["set_fact"]["ctlabs_k8s_storage"]
    assert "'master'" in fact["set_fact"]["ctlabs_k8s_storage"]
    asrt = next(t for t in precheck if t.get("name") == "ctlabs_k8s.tasks.precheck.storage.master_only")
    that = asrt["assert"]["that"]
    cond = that if isinstance(that, str) else that[0]
    assert "ctlabs_k8s_storage_raw == ''" in cond
    assert "ctlabs_k8s_role == 'master'" in cond


def test_precheck_storage_rule_order():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    names = [t.get("name") for t in precheck]
    assert names.index("ctlabs_k8s.tasks.precheck.role.supported") < names.index(
        "ctlabs_k8s.tasks.precheck.storage.fact"
    )
    assert names.index("ctlabs_k8s.tasks.precheck.storage.fact") < names.index(
        "ctlabs_k8s.tasks.precheck.storage.master_only"
    )


def test_config_storage_exists_master_only():
    with open(os.path.join(ROLE_TASKS, "config.yml")) as f:
        config = yaml.safe_load(f)
    storage = next(t for t in config if t.get("name") == "ctlabs_k8s.tasks.config.storage")
    assert storage["when"] == "ctlabs_k8s_role == 'master'"
    blocknames = [t.get("name") for t in storage["block"]]
    assert "ctlabs_k8s.tasks.config.storage.engine" not in blocknames
    assert "ctlabs_k8s.tasks.config.storage.local.manifest" in blocknames


def test_precheck_gateway_api_facts():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    names = [t.get("name") for t in precheck]
    assert "ctlabs_k8s.tasks.precheck.gateway_api.enabled" in names
    assert "ctlabs_k8s.tasks.precheck.gateway_api.provider" in names
    enabled = next(t for t in precheck if t.get("name") == "ctlabs_k8s.tasks.precheck.gateway_api.enabled")
    provider = next(t for t in precheck if t.get("name") == "ctlabs_k8s.tasks.precheck.gateway_api.provider")
    assert "ctg_facts.ctlabs_k8s.gateway_api.enabled" in enabled["set_fact"]["ctlabs_k8s_gateway_api_enabled"]
    assert "default" in enabled["set_fact"]["ctlabs_k8s_gateway_api_enabled"]
    assert "ctg_facts.ctlabs_k8s.gateway_api.provider" in provider["set_fact"]["ctlabs_k8s_gateway_api_provider"]


def test_config_gateway_api_master_only():
    with open(os.path.join(ROLE_TASKS, "config.yml")) as f:
        config = yaml.safe_load(f)
    gw = next(t for t in config if t.get("name") == "ctlabs_k8s.tasks.config.gateway_api")
    assert "ctlabs_k8s_role == 'master'" in (gw["when"] if isinstance(gw["when"], str) else " ".join(gw["when"]))
    assert "ctlabs_k8s_gateway_api_enabled" in " ".join(gw["when"])
    blocknames = [t.get("name") for t in gw["block"]]
    for expected in [
        "ctlabs_k8s.tasks.config.gateway_api.crds.download",
        "ctlabs_k8s.tasks.config.gateway_api.crds.apply",
        "ctlabs_k8s.tasks.config.gateway_api.namespace",
        "ctlabs_k8s.tasks.config.gateway_api.gateway_class",
        "ctlabs_k8s.tasks.config.gateway_api.gateway",
    ]:
        assert expected in blocknames
    declarative = ["kubernetes.core.k8s" in t for t in gw["block"]]
    assert any(declarative)


def test_config_gateway_api_no_command():
    with open(os.path.join(ROLE_TASKS, "config.yml")) as f:
        config = yaml.safe_load(f)
    gw = next(t for t in config if t.get("name") == "ctlabs_k8s.tasks.config.gateway_api")
    allow_kubectl_server_side = {"ctlabs_k8s.tasks.config.gateway_api.crds.apply"}
    for t in gw["block"]:
        if t.get("name") in allow_kubectl_server_side:
            continue
        assert "command" not in t, f"gateway_api task '{t.get('name')}' must not use command"
        assert "shell" not in t, f"gateway_api task '{t.get('name')}' must not use shell"


def test_gateway_template_listeners():
    with open(os.path.join(ROLE_TEMPLATES, "gateway.yml.j2")) as f:
        tpl = f.read()
    assert "kind: Gateway" in tpl
    assert "gatewayClassName:" in tpl
    assert "protocol: HTTP" in tpl
    assert "protocol: HTTPS" in tpl
    assert "mode: Terminate" in tpl
    assert "certificateRefs" in tpl
    assert "allowedRoutes" in tpl

    with open(os.path.join(ROLE_TASKS, "../defaults/main.yml")) as f:
        defaults = yaml.safe_load(f)
    gw = defaults["ctlabs_k8s"]["defaults"]["config"]["gateway_api"]
    assert gw["provider"] == "traefik"
    assert gw["gateway"]["name"] == "traefik-gateway"
    assert gw["gateway"]["tls_secret"] == "argocd-tls"
    assert gw["gateway"]["listeners"]["web"]["port"] == 8000
    assert gw["gateway"]["listeners"]["websecure"]["port"] == 8443
    assert "standard-install.yaml" in gw["crds"]["url"]
    assert gw["gateway"]["class_controller"] == "traefik.io/gateway-controller"

    with open(os.path.join(ROLE_TEMPLATES, "gatewayclass.yml.j2")) as f:
        gwc = f.read()
    assert "kind: GatewayClass" in gwc
    assert "controllerName:" in gwc
    assert gwc.count("controllerName:") == 1


def test_calico_encapsulation_default():
    with open(os.path.join(ROLE_TEMPLATES, "calico-custom-resources.yml.j2")) as f:
        tpl = f.read()
    assert "ctlabs_k8s_pod_cidr_encapsulation" in tpl
    assert "VXLANCrossSubnet" not in tpl

    with open(os.path.join(ROLE_TASKS, "../defaults/main.yml")) as f:
        defaults = yaml.safe_load(f)
    assert defaults["ctlabs_k8s_pod_cidr_encapsulation"] == "IPIP"


def test_precheck_lb_fact():
    with open(os.path.join(ROLE_TASKS, "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    names = [t.get("name") for t in precheck]
    assert "ctlabs_k8s.tasks.precheck.lb.fact" in names
    assert "ctlabs_k8s.tasks.precheck.lb.supported" in names
    fact = next(t for t in precheck if t.get("name") == "ctlabs_k8s.tasks.precheck.lb.fact")
    assert "ctg_facts.ctlabs_k8s.lb" in fact["set_fact"]["ctlabs_k8s_lb"]
    assert "default" in fact["set_fact"]["ctlabs_k8s_lb"]
    sup = next(t for t in precheck if t.get("name") == "ctlabs_k8s.tasks.precheck.lb.supported")
    assert "ctlabs_k8s.defaults.config.lb_supported" in sup["assert"]["that"]


def test_lb_defaults():
    with open(os.path.join(ROLE_TASKS, "../defaults/main.yml")) as f:
        defaults = yaml.safe_load(f)
    cfg = defaults["ctlabs_k8s"]["defaults"]["config"]
    assert cfg["lb"] == "kube-vip"
    assert cfg["lb_supported"] == ["kube-vip", "metallb", "none"]


def test_kube_vip_svc_enable_gated_by_lb():
    tpl = _facts_env().get_template("kube-vip.yml.j2")
    ctx = {"ansible_default_ipv4": {"address": "192.168.30.31"}}
    on = tpl.render(ctlabs_k8s_lb="kube-vip", **ctx)
    off = tpl.render(ctlabs_k8s_lb="metallb", **ctx)
    assert 'name: svc_enable\n      value: "true"' in on
    assert 'name: svc_enable\n      value: "false"' in off


def test_config_csrs_approver_master_only():
    with open(os.path.join(ROLE_TASKS, "config.yml")) as f:
        config = yaml.safe_load(f)
    block = next(t for t in config if t.get("name") == "ctlabs_k8s.tasks.config.certs.approver")
    assert block["when"] == "ctlabs_k8s_role == 'master'"
    names = [t.get("name") for t in block["block"]]
    for expected in [
        "ctlabs_k8s.tasks.config.certs.approver.script",
        "ctlabs_k8s.tasks.config.certs.approver.service",
        "ctlabs_k8s.tasks.config.certs.approver.timer",
        "ctlabs_k8s.tasks.config.certs.approver.enable",
    ]:
        assert expected in names
    enable = next(t for t in block["block"] if t.get("name") == "ctlabs_k8s.tasks.config.certs.approver.enable")
    assert enable["systemd"]["name"] == "k8s-csr-approver.timer"
    assert enable["systemd"]["enabled"] is True
    for t in block["block"]:
        assert "command" not in t
        assert "shell" not in t


def test_csr_approver_templates():
    with open(os.path.join(ROLE_TEMPLATES, "approve-serving-csrs.sh.j2")) as f:
        script = f.read()
    assert "kubelet-serving" in script
    assert "certificate approve" in script
    assert 'awk \'$NF == "Pending"' in script
    with open(os.path.join(ROLE_TEMPLATES, "k8s-csr-approver.timer.j2")) as f:
        timer = f.read()
    assert "OnUnitActiveSec=60s" in timer
    with open(os.path.join(ROLE_TEMPLATES, "k8s-csr-approver.service.j2")) as f:
        service = f.read()
    assert "Type=oneshot" in service
