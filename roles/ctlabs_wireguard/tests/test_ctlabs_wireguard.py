# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_wireguard/tests/test_ctlabs_wireguard.py
# Description : pytest tests for ctlabs_wireguard role
# ------------------------------------------------------------------------------

import json
import os
import subprocess
import tempfile
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
        "files/create_wireguard_keys.py",
        "templates/wireguard.conf.j2",
        "templates/facts.json.j2",
    ]
    for rel_path in expected_files:
        path = os.path.join(role_dir, rel_path)
        assert os.path.isfile(path), f"Missing expected file: {rel_path}"


def test_defaults_structure(role_dir):
    defaults_file = os.path.join(role_dir, "defaults", "main.yml")
    with open(defaults_file) as f:
        data = yaml.safe_load(f)

    assert "ctlabs_wireguard" in data
    cfg = data["ctlabs_wireguard"]
    assert "defaults" in cfg
    assert "os" in cfg
    assert "debian12" in cfg["os"]
    assert "centos9" in cfg["os"]
    assert "redhat9" in cfg["os"]

    defaults = cfg["defaults"]
    assert "config" in defaults
    assert defaults["config"]["dev"] == "wg0"
    assert defaults["config"]["port"] == 51820
    assert defaults["config"]["table"] == "off"
    assert defaults["config"]["allowed_ips"] == "0.0.0.0/0"
    assert defaults["config"]["persistent_keepalive"] == 25


def test_key_generator_script(role_dir):
    script_path = os.path.join(role_dir, "files", "create_wireguard_keys.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        res = subprocess.run(
            ["python3", script_path, tmpdir],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Script failed: {res.stderr}"
        for name in ["server.key", "server.pub", "client.key", "client.pub"]:
            p = os.path.join(tmpdir, name)
            assert os.path.isfile(p), f"Missing generated key: {name}"
            with open(p) as f:
                content = f.read().strip()
            assert len(content) == 44, f"Invalid base64 key length: {len(content)}"

        # Idempotence test: re-running should not alter keys
        with open(os.path.join(tmpdir, "server.key")) as f:
            original_key = f.read()
        res2 = subprocess.run(["python3", script_path, tmpdir], capture_output=True, text=True)
        assert res2.returncode == 0
        with open(os.path.join(tmpdir, "server.key")) as f:
            assert f.read() == original_key


def test_server_template_rendering(role_dir):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    tmpl = env.get_template("wireguard.conf.j2")
    ctx = {
        "ctlabs_wireguard_dev": "wg0",
        "ctlabs_wireguard_address": "10.8.15.1/30",
        "ctlabs_wireguard_private_key": "SERVER_PRIV_KEY",
        "ctlabs_wireguard_peer_public_key": "CLIENT_PUB_KEY",
        "ctg_facts": {
            "ctlabs_wireguard": {
                "type": "server",
                "server_ip": "10.8.15.1",
                "client_ip": "10.8.15.2",
                "port": 51820,
            }
        },
        "ctlabs_wireguard": {
            "defaults": {
                "config": {
                    "port": 51820,
                    "table": "off",
                    "allowed_ips": "0.0.0.0/0",
                    "persistent_keepalive": 25,
                }
            }
        },
    }
    rendered = tmpl.render(ctx)
    assert "[Interface]" in rendered
    assert "Address = 10.8.15.1/30" in rendered
    assert "ListenPort = 51820" in rendered
    assert "PrivateKey = SERVER_PRIV_KEY" in rendered
    assert "Table = off" in rendered
    assert "[Peer]" in rendered
    assert "PublicKey = CLIENT_PUB_KEY" in rendered
    assert "AllowedIPs = 0.0.0.0/0" in rendered
    assert "Endpoint" not in rendered


def test_client_template_rendering(role_dir):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    tmpl = env.get_template("wireguard.conf.j2")
    ctx = {
        "ctlabs_wireguard_dev": "wg0",
        "ctlabs_wireguard_address": "10.8.15.2/30",
        "ctlabs_wireguard_private_key": "CLIENT_PRIV_KEY",
        "ctlabs_wireguard_peer_public_key": "SERVER_PUB_KEY",
        "ctg_facts": {
            "ctlabs_wireguard": {
                "type": "client",
                "server_ip": "10.8.15.1",
                "client_ip": "10.8.15.2",
                "remote": "35.200.10.7",
                "port": 51820,
            }
        },
        "ctlabs_wireguard": {
            "defaults": {
                "config": {
                    "port": 51820,
                    "table": "off",
                    "allowed_ips": "0.0.0.0/0",
                    "persistent_keepalive": 25,
                }
            }
        },
    }
    rendered = tmpl.render(ctx)
    assert "[Interface]" in rendered
    assert "Address = 10.8.15.2/30" in rendered
    assert "PrivateKey = CLIENT_PRIV_KEY" in rendered
    assert "ListenPort" not in rendered
    assert "Table = off" in rendered
    assert "[Peer]" in rendered
    assert "PublicKey = SERVER_PUB_KEY" in rendered
    assert "Endpoint = 35.200.10.7:51820" in rendered
    assert "PersistentKeepalive = 25" in rendered
    assert "AllowedIPs = 0.0.0.0/0" in rendered


def test_facts_template_rendering_server(role_dir):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    tmpl = env.get_template("facts.json.j2")
    ctx = {
        "ctlabs_role_facts": {
            "type": "server",
            "server_ip": "10.8.15.1",
            "client_ip": "10.8.15.2",
            "dev": "wg0",
            "forward": True,
        }
    }
    rendered = tmpl.render(ctx)
    data = json.loads(rendered)
    assert data["type"] == "server"
    assert data["server_ip"] == "10.8.15.1"
    assert data["client_ip"] == "10.8.15.2"
    assert data["dev"] == "wg0"
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
            "port": 51820,
            "dev": "wg0",
            "key_name": "gcp_wg",
        }
    }
    rendered = tmpl.render(ctx)
    data = json.loads(rendered)
    assert data["type"] == "client"
    assert data["remote"] == "35.200.10.7"
    assert data["port"] == 51820
    assert data["key_name"] == "gcp_wg"


def test_ansible_syntax_check(role_dir):
    test_playbook = os.path.join(role_dir, "tests", "test_wireguard.yml")
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
