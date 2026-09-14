# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_kind/tests/test_ctlabs_kind.py
# Description : pytest tests for ctlabs_kind role
# ------------------------------------------------------------------------------

import json
import os
import subprocess

from jinja2 import Environment, FileSystemLoader

ROLE_TEMPLATES = "/root/ctlabs-ansible/roles/ctlabs_kind/templates"


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
        "tasks/charts.yml",
        "tasks/routing.yml",
        "tasks/proxy.yml",
        "defaults/main.yml",
        "handlers/main.yml",
        "templates/facts.json.j2",
        "templates/kind-cluster.yml.j2",
        "templates/kind.profile.j2",
    ]
    for f in files:
        path = os.path.join(role_dir, f)
        assert os.path.isfile(path), f"Missing required file: {f}"


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_kind.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
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
