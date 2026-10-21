# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_openvpn/tests/test_ctlabs_openvpn.py
# Description : pytest tests for ctlabs_openvpn role
# ------------------------------------------------------------------------------

import json
import os
import subprocess
import yaml
from jinja2 import Environment, FileSystemLoader


def test_files_exist(role_dir):
    expected_files = [
        "defaults/main.yml",
        "handlers/main.yml",
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/package.yml",
        "tasks/config.yml",
        "tasks/service.yml",
        "tasks/facts.yml",
        "templates/server.conf.j2",
        "templates/client.conf.j2",
        "templates/facts.json.j2",
    ]
    for rel_path in expected_files:
        path = os.path.join(role_dir, rel_path)
        assert os.path.isfile(path), f"Missing expected file: {rel_path}"


def test_defaults_structure(role_dir):
    defaults_file = os.path.join(role_dir, "defaults", "main.yml")
    with open(defaults_file) as f:
        data = yaml.safe_load(f)

    assert "ctlabs_openvpn" in data
    cfg = data["ctlabs_openvpn"]
    assert "defaults" in cfg
    assert "os" in cfg
    assert "debian12" in cfg["os"]
    assert "centos9" in cfg["os"]
    assert "redhat9" in cfg["os"]

    defaults = cfg["defaults"]
    assert "service" in defaults
    assert "config" in defaults
    assert defaults["config"]["server"]["file"] == "/etc/openvpn/server/server.conf"
    assert defaults["config"]["client"]["file"] == "/etc/openvpn/client/client.conf"
    assert defaults["config"]["controller_key_dir"] == "/etc/openvpn"


def test_server_template_rendering(role_dir):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    tmpl = env.get_template("server.conf.j2")
    ctx = {
        "ctg_facts": {
            "ctlabs_openvpn": {
                "type": "server",
                "server_ip": "10.8.15.1",
                "client_ip": "10.8.15.2",
                "dev": "tun0",
                "port": 1194,
                "proto": "udp",
                "cipher": "AES-256-CBC",
                "auth": "SHA512",
            }
        }
    }
    rendered = tmpl.render(ctx)
    assert "dev          tun0" in rendered
    assert "ifconfig     10.8.15.1 10.8.15.2" in rendered
    assert "secret       ovpn.key" in rendered
    assert "port         1194" in rendered
    assert "cipher       AES-256-CBC" in rendered


def test_client_template_rendering(role_dir):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    tmpl = env.get_template("client.conf.j2")
    ctx = {
        "ctg_facts": {
            "ctlabs_openvpn": {
                "type": "client",
                "server_ip": "10.8.15.1",
                "client_ip": "10.8.15.2",
                "remote": "35.200.10.7",
                "dev": "tun0",
                "port": 1194,
                "proto": "udp",
                "cipher": "AES-256-CBC",
                "auth": "SHA512",
            }
        }
    }
    rendered = tmpl.render(ctx)
    assert "dev          tun0" in rendered
    assert "ifconfig     10.8.15.2 10.8.15.1" in rendered
    assert "remote       35.200.10.7 1194" in rendered
    assert "secret       ovpn.key" in rendered


def test_facts_template_rendering_server(role_dir):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    tmpl = env.get_template("facts.json.j2")
    ctx = {
        "ctlabs_role_facts": {
            "type": "server",
            "server_ip": "10.8.15.1",
            "client_ip": "10.8.15.2",
            "dev": "tun0",
            "forward": True,
        }
    }
    rendered = tmpl.render(ctx)
    data = json.loads(rendered)
    assert data["type"] == "server"
    assert data["server_ip"] == "10.8.15.1"
    assert data["client_ip"] == "10.8.15.2"
    assert data["dev"] == "tun0"
    assert data["forward"] is True
    assert "remote" not in data


def test_facts_template_rendering_client(role_dir):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    tmpl = env.get_template("facts.json.j2")
    ctx = {
        "ctlabs_role_facts": {
            "type": "client",
            "server_ip": "10.8.15.1",
            "client_ip": "10.8.15.2",
            "remote": "35.200.10.7",
            "dev": "tun0",
            "port": 1194,
            "key_name": "gcp_tunnel",
        }
    }
    rendered = tmpl.render(ctx)
    data = json.loads(rendered)
    assert data["type"] == "client"
    assert data["remote"] == "35.200.10.7"
    assert data["port"] == 1194
    assert data["key_name"] == "gcp_tunnel"


def test_ansible_syntax_check(role_dir):
    test_playbook = os.path.join(role_dir, "tests", "test_openvpn.yml")
    repo_root = os.path.abspath(os.path.join(role_dir, "..", ".."))
    env = os.environ.copy()
    env["PATH"] = f"/usr/local/bin:{env.get('PATH', '')}"
    env["ANSIBLE_ROLES_PATH"] = os.path.join(repo_root, "roles")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", test_playbook],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed: {result.stderr}\n{result.stdout}"
