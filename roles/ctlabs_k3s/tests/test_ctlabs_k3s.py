# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_k3s/tests/test_ctlabs_k3s.py
# Description : pytest tests for ctlabs_k3s role
# ------------------------------------------------------------------------------

import os
import subprocess

from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = "/root/ctlabs-ansible/roles/ctlabs_k3s/templates"

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
