# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_chartmuseum/tests/test_ctlabs_chartmuseum.py
# Description : pytest tests for ctlabs_chartmuseum role
# ------------------------------------------------------------------------------

import os
import re
import subprocess


def _run_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_chartmuseum.yml")
    repo_root = os.path.abspath(os.path.join(role_dir, "..", ".."))
    env = os.environ.copy()
    env["ANSIBLE_ROLES_PATH"] = os.path.join(repo_root, "roles")
    return subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )


def test_templates_exist(role_dir):
    for name in ["config.yml.j2", "chartmuseum.service.j2", "facts.json.j2"]:
        path = os.path.join(role_dir, "templates", name)
        assert os.path.isfile(path), f"missing template: {name}"


def test_precheck_does_not_append_contextpath_to_charturl(role_dir):
    # Regression test: chartmuseum builds
    # '<charturl>/<contextpath>/charts/<name>-<version>.tgz' itself. Appending
    # contextpath in the derived charturl doubles the path and every chart URL
    # in index.yaml 404s.
    path = os.path.join(role_dir, "tasks", "precheck.yml")
    with open(path) as f:
        content = f.read()
    content = re.sub(r"^\s*#.*$", "", content, flags=re.MULTILINE)
    block = content.split("precheck.charturl")[1].split("- name:")[0]
    assert "contextpath" not in block, (
        "charturl derivation must not include contextpath - chartmuseum "
        "appends it itself"
    )


def test_ansible_syntax_check(role_dir):
    result = _run_syntax_check(role_dir)
    assert result.returncode == 0, f"Syntax check failed: {result.stderr}"


def _rendered_lines(role_dir, template):
    """Return the template with jinja + yaml comments stripped.

    The config template documents each trap in a comment right next to the
    correct key, so a naive substring scan sees the *wrong* spellings too.
    """
    path = os.path.join(role_dir, "templates", template)
    with open(path) as f:
        content = f.read()
    content = re.sub(r"{#.*?#}", "", content, flags=re.DOTALL)
    return re.sub(r"^\s*#.*$", "", content, flags=re.MULTILINE)


def test_config_template_uses_viper_keys_not_cli_flags(role_dir):
    # Regression test: the config file is read by viper, whose keys differ from
    # the CLI flag names. 'enable-metrics' and a nested 'auth: {anonymousget:}'
    # are both accepted silently by viper and then do nothing, which leaves the
    # endpoint unprotected / /metrics 404ing. Pin the viper spellings.
    content = _rendered_lines(role_dir, "config.yml.j2")
    for key in [
        "enablemetrics",
        "authanonymousget",
        "basicauth",
        "json-index",
        "disabledelete",
        "maxuploadsize",
        "contextpath",
        "charturl",
    ]:
        assert key in content, f"config template missing viper key: {key}"
    # anchor on start-of-key so 'authanonymousget' is not mistaken for a
    # nested 'anonymousget', and 'basicauth' not for an 'auth:' block
    assert not re.search(r"^\s*enable-metrics\s*:", content, re.MULTILINE)
    assert not re.search(r"^\s*anonymousget\s*:", content, re.MULTILINE)
    assert not re.search(r"^\s*auth\s*:", content, re.MULTILINE)


def test_config_template_never_emits_tls_cacert(role_dir):
    # Regression test: chartmuseum switches the listener to
    # RequireAndVerifyClientCert as soon as tls.cacert is present, so every
    # client without a client cert gets
    # 'tls: client didn't provide a certificate' - including the role's own
    # health check. CACERT is offered as a knob but must not be rendered unless
    # a user opts in by uncommenting.
    content = _rendered_lines(role_dir, "config.yml.j2")
    assert not re.search(r"^\s*cacert\s*:", content, re.MULTILINE)


def test_facts_template_does_not_forward_auth_password(role_dir):
    # The fact file lands in a world-readable /etc/ansible/facts.d; forwarding
    # auth.pass would leak the basic-auth credential to every host that reads
    # this fact. Jinja comments are stripped first - the comment block explains
    # why auth is omitted and would otherwise trip the assertion.
    path = os.path.join(role_dir, "templates", "facts.json.j2")
    with open(path) as f:
        content = f.read()
    content = re.sub(r"{#.*?#}", "", content, flags=re.DOTALL)
    for forbidden in ["auth", "pass", "user"]:
        assert (
            forbidden not in content
        ), f"facts template must not forward the auth block (found {forbidden})"


def test_facts_are_flat_config_overlay(role_dir):
    # Regression test: the fact file is named ctlabs_chartmuseum.fact, so its
    # TOP-LEVEL keys become ctg_facts.ctlabs_chartmuseum.<key>. Wrapping the
    # knobs in a "config" key would make them land on
    # ctg_facts.ctlabs_chartmuseum.config.<key> and precheck would silently
    # fall back to role defaults for every one of them.
    content = _rendered_lines(role_dir, "facts.json.j2")
    assert "config" not in content, "facts must be a flat config overlay, not nested"

    precheck = os.path.join(role_dir, "tasks", "precheck.yml")
    with open(precheck) as f:
        content = f.read()
    assert (
        "ctlabs_chartmuseum_fact" in content
    ), "precheck must merge the flat fact dict, not a .config sub-dict"
