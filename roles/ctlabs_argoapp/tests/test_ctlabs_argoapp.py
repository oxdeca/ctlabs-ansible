# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_argoapp/tests/test_ctlabs_argoapp.py
# Description : pytest tests for ctlabs_argoapp role
# ------------------------------------------------------------------------------

import glob
import os
import subprocess

import yaml


def _repo_env():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env = os.environ.copy()
    # plain role name + roles path: a templated role path makes --syntax-check a
    # false green, because ansible never loads the role's task files.
    env["ANSIBLE_ROLES_PATH"] = os.path.join(repo_root, "roles")
    return repo_root, env


def test_role_files_exist(role_dir):
    required = [
        "defaults/main.yml",
        "tasks/main.yml",
        "tasks/precheck.yml",
        "tasks/applications.yml",
        "tasks/facts.yml",
        "templates/application.yml.j2",
        "templates/facts.json.j2",
        "README.md",
    ]
    for name in required:
        path = os.path.join(role_dir, name)
        assert os.path.isfile(path), f"Missing required file: {name}"


def test_playbook_syntax_check(role_dir):
    _, env = _repo_env()
    playbook = os.path.join(role_dir, "tests", "test_argoapp.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_render_all_source_forms(role_dir):
    # Functional check for what --syntax-check cannot see: that the verbatim
    # source passthrough round-trips through to_nice_yaml (booleans stay
    # booleans, valuesObject keeps int/bool types) and that role defaults merge
    # in only where the application stays silent.
    _, env = _repo_env()
    playbook = os.path.join(role_dir, "tests", "test_render.yml")
    result = subprocess.run(
        ["ansible-playbook", playbook],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Render failed:\n{result.stdout}\n{result.stderr}"


def test_facts_template_forwards_only_set_knobs(role_dir):
    # Guards a silent failure: a fact file that renders fine but drops or
    # defaults every per-host knob leaves the role on role defaults while
    # looking healthy. Absent knobs must stay absent so precheck's defaults
    # still apply.
    _, env = _repo_env()
    playbook = os.path.join(role_dir, "tests", "test_facts.yml")
    result = subprocess.run(
        ["ansible-playbook", playbook],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Facts render failed:\n{result.stdout}\n{result.stderr}"


def test_source_is_opaque_passthrough(role_dir):
    # The design contract: spec.source is ArgoCD's own schema, so the role must
    # never enumerate, filter or descend into its keys - otherwise a source
    # form ArgoCD adds later silently loses data here.
    with open(os.path.join(role_dir, "templates", "application.yml.j2")) as f:
        template = f.read()
    assert "'source'     : app['source']," in template
    for forbidden in (
        "in app['source']",
        "app['source'][",
        "app['source'] | selectattr",
        "app['source'] | map(",
        "app['source'] | rejectattr",
    ):
        assert forbidden not in template, f"template must not inspect source: {forbidden}"


def test_tasks_use_no_imperative_module(role_dir):
    # ctlabs convention: declarative modules only (kubernetes.core here), no
    # command/shell. The sync wait must poll the Application CR, not kubectl.
    for path in glob.glob(os.path.join(role_dir, "tasks", "*.yml")):
        with open(path) as f:
            tasks = yaml.safe_load(f)
        for task in tasks or []:
            for key in ("command", "shell"):
                assert key not in task, f"{os.path.basename(path)}: {task.get('name')} uses '{key}'"


def test_helm_conflict_guard_fails_loudly(role_dir):
    # Helm and ArgoCD managing the same release revert each other forever and
    # leave the app permanently OutOfSync with no obvious cause - so the
    # precheck must read the helm charts and assert, not skip.
    with open(os.path.join(role_dir, "tasks", "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    names = [t.get("name") for t in precheck]
    assert "ctlabs_argoapp.tasks.precheck.helm.charts" in names
    guard = next(t for t in precheck if t.get("name") == "ctlabs_argoapp.tasks.precheck.helm.conflict")
    assert "assert" in guard, "the helm conflict guard must fail, not silently skip"
    assert "ctlabs_argoapp_conflicts | length == 0" in guard["assert"]["that"][0]
    charts = next(t for t in precheck if t.get("name") == "ctlabs_argoapp.tasks.precheck.helm.charts")
    assert ".ctlabs_helm" in charts["set_fact"]["ctlabs_argoapp_helm_charts"]


def test_role_is_noop_without_applications(role_dir):
    # Every cluster lab would carry this role; it must do nothing at all when a
    # host declares no applications (no cluster contact whatsoever).
    with open(os.path.join(role_dir, "tasks", "applications.yml")) as f:
        tasks = yaml.safe_load(f)
    assert len(tasks) == 1, "applications.yml should be a single guarded block"
    assert tasks[0]["when"] == "ctlabs_argoapp_applications | length > 0"


def test_numeric_wait_knobs_are_cast_at_point_of_use(role_dir):
    # Found by live-testing against rke21: with jinja2_native off this repo's
    # ansible hands set_fact numbers back as strings, so `timeout // delay`
    # died with "unsupported operand type(s) for //: 'str' and 'str'" - after the
    # Applications had already been applied. Cast every numeric knob where it is
    # consumed; a bare arithmetic between two set_fact vars must not reappear.
    with open(os.path.join(role_dir, "tasks", "applications.yml")) as f:
        block = yaml.safe_load(f)[0]["block"]
    wait = next(t for t in block if t.get("name", "").endswith(".wait"))
    assert wait["retries"] == (
        "{{ ctlabs_argoapp_wait_timeout | int // ctlabs_argoapp_wait_delay | int }}"
    )
    assert wait["delay"] == "{{ ctlabs_argoapp_wait_delay | int }}"
    assert wait["when"] == "app['wait'] | default(ctlabs_argoapp_wait) | bool"
    crd = next(t for t in block if t.get("name", "").endswith(".crd.available"))
    assert crd["kubernetes.core.k8s_info"]["wait_timeout"] == "{{ ctlabs_argoapp_crd_wait | int }}"

    for path in glob.glob(os.path.join(role_dir, "tasks", "*.yml")):
        with open(path) as f2:
            text = f2.read()
        for line in text.splitlines():
            code = line.split("#")[0]
            if "//" in code:
                assert "| int //" in code, f"{os.path.basename(path)}: uncasted floor division: {code.strip()}"


def test_precheck_verifies_argocd_instance_exists(role_dir):
    # The OS check alone was not enough: the role targets an ArgoCD control
    # plane that some OTHER role (ctlabs_helm) installed, so a wrong play order
    # or a wrong namespace was only discovered as a mystery timeout / NoMatches
    # deep in applications.yml. The precheck must therefore verify the CRD is
    # Established AND that an application controller actually has a ready
    # replica - an Established CRD survives a broken controller, in which case
    # the Applications would be created and silently never reconciled.
    with open(os.path.join(role_dir, "tasks", "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    names = [t.get("name") for t in precheck]

    crd = next(t for t in precheck if t.get("name", "").endswith("argocd.crd"))
    assert crd["kubernetes.core.k8s_info"]["name"] == "applications.argoproj.io"
    assert crd["kubernetes.core.k8s_info"]["wait_condition"] == {
        "type": "Established",
        "status": "True",
    }

    # both workload shapes must be probed: the helm chart runs the controller as
    # a Deployment, the operator as a StatefulSet.
    probe = [
        t for t in precheck
        if ".argocd.controller" in t.get("name", "")
        and "kubernetes.core.k8s_info" in t
    ]
    kinds = {t["kubernetes.core.k8s_info"]["kind"] for t in probe}
    assert kinds == {"Deployment", "StatefulSet"}, f"controller probes cover {kinds}"
    for task in probe:
        assert task["kubernetes.core.k8s_info"]["namespace"] == "{{ ctlabs_argoapp_namespace }}"
        assert task["kubernetes.core.k8s_info"]["label_selectors"] == [
            "app.kubernetes.io/component=application-controller"
        ]

    guard = next(
        t for t in precheck if t.get("name", "").endswith("argocd.controller.assert")
    )
    assert "assert" in guard, "a missing controller must fail, not be skipped"
    assert "_argoapp_ctrl_resources | length > 0" in guard["assert"]["that"]
    assert "_argoapp_ctrl_ready | int >= 1" in guard["assert"]["that"]
    # the failure has to name the actual dependency, not just "not ready"
    assert "ctlabs_helm" in guard["assert"]["fail_msg"]


def test_argocd_precheck_is_guarded_and_safe_on_empty(role_dir):
    # Two invariants: (1) applications=[] must stay a complete no-op, so every
    # new cluster-touching precheck task is guarded; (2) the ready-replica count
    # must never be computed with max() over a possibly-empty list, which raises
    # and swallows the human-readable fail_msg.
    with open(os.path.join(role_dir, "tasks", "precheck.yml")) as f:
        precheck = yaml.safe_load(f)

    for task in precheck:
        name = task.get("name", "")
        if ".argocd." not in name:
            continue
        assert task.get("when") == "ctlabs_argoapp_applications | length > 0", (
            f"{name} contacts the cluster and must be guarded by applications>0"
        )

    ready = next(
        t for t in precheck if t.get("name", "").endswith("argocd.controller.ready")
    )
    assert "| sum" in ready["set_fact"]["_argoapp_ctrl_ready"]
    assert "max" not in ready["set_fact"]["_argoapp_ctrl_ready"]
    assert "default=0" in ready["set_fact"]["_argoapp_ctrl_ready"]


def test_default_namespace_is_the_chart_release_namespace(role_dir):
    # ctlabs_helm deploys release 'argocd' into NAMESPACE 'argo' (helm list -A
    # shows NAME=argocd, NAMESPACE=argo). Defaulting to 'argocd' looked right -
    # it is the release name - but targeted a namespace that does not exist, so
    # every Application would land nowhere.
    with open(os.path.join(role_dir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)
    assert defaults["ctlabs_argoapp"]["defaults"]["namespace"] == "argo"
