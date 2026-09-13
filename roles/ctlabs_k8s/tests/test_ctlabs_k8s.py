# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_k8s/tests/test_ctlabs_k8s.py
# Description : pytest tests for ctlabs_k8s role
# ------------------------------------------------------------------------------

import os
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = "/root/ctlabs-ansible/roles/ctlabs_k8s/templates"


def _render_kubeadm_init(**overrides):
    env = Environment(loader=FileSystemLoader(ROLE_TEMPLATES))
    tpl = env.get_template("kubeadm-init.yml.j2")
    ctx = {
        "ctlabs_k8s_join_token": "abcdef.0123456789abcdef",
        "ctlabs_k8s_cert_key": "0" * 64,
        "ctlabs_k8s_master_ip": "192.168.99.10",
        "ctlabs_k8s_pod_cidr": "10.8.15.0/24",
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
        "templates/k8sall.sh.j2",
        "templates/kubeadm-init.yml.j2",
        "templates/kubeadm-join.yml.j2",
        "templates/kube-vip.yml.j2",
        "templates/versions.sh.j2",
        "templates/weave.yml.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_k8s.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
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
    assert cluster["networking"]["podSubnet"] == "10.8.15.0/24"
