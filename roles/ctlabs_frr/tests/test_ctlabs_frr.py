# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_frr/tests/test_ctlabs_frr.py
# Description : pytest tests for ctlabs_frr role (frr.conf.j2 rendering)
# ------------------------------------------------------------------------------

import os
from jinja2 import Environment, FileSystemLoader


def render(role_dir, router):
    env = Environment(loader=FileSystemLoader(os.path.join(role_dir, "templates")))
    return env.get_template("frr.conf.j2").render(
        ctlabs_frr_daemons_profile="datacenter",
        ansible_nodename="ro1",
        ctg_facts={"ctlabs_frr": {"router": router}},
    )


def bgp(**kw):
    return {"bgp": {"local_asn": 65001, "local_ip": "10.0.0.1",
                    "remote_ip": "10.0.0.2", "remote_asn": 65045, **kw}}


def test_bgp_nets_address_family_balanced(role_dir):
    out = render(role_dir, bgp(nets=["192.168.10.0/24", "192.168.20.0/24"]))
    assert "  address-family ipv4 unicast" in out
    assert "  network 192.168.10.0/24" in out
    assert "  network 192.168.20.0/24" in out
    assert out.count("address-family ipv4 unicast") == out.count("exit-address-family") == 1


def test_bgp_without_nets_has_no_stray_exit_address_family(role_dir):
    # regression: neighbour-only BGP rendered a bare exit-address-family,
    # which vtysh rejects ("Unknown command: exit-address-family")
    for kw in ({}, {"nets": []}):
        out = render(role_dir, bgp(**kw))
        assert "neighbor 10.0.0.2 remote-as 65045" in out
        assert "address-family" not in out


def test_ospf_only_has_no_bgp(role_dir):
    out = render(role_dir, {"ospf": {"nets": ["192.168.10.0/24"]}})
    assert "router bgp" not in out
    assert "address-family" not in out
    assert "  network 192.168.10.0/24 area 0" in out
