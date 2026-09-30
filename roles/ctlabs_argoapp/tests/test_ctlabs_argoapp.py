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
        "tasks/repositories.yml",
        "templates/application.yml.j2",
        "templates/facts.json.j2",
        "templates/repository.yml.j2",
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


def test_repositories_are_noop_and_created_before_applications(role_dir):
    # Two invariants. (1) repositories=[] must be a complete no-op, same as
    # applications=[]. (2) The credential Secrets must be applied BEFORE the
    # applications that name those repositories: ArgoCD reads credentials from
    # Secrets, not from the Application, so an app created first fails its first
    # sync with 'repository not found' - and with automated+selfHeal sync that
    # failure retries forever instead of surfacing.
    with open(os.path.join(role_dir, "tasks", "repositories.yml")) as f:
        tasks = yaml.safe_load(f)
    assert len(tasks) == 1, "repositories.yml should be a single guarded block"
    assert tasks[0]["when"] == "ctlabs_argoapp_repositories | length > 0"
    block = tasks[0]["block"]

    # the credential state has to be captured BEFORE it is overwritten, or there
    # is nothing to roll back to
    names = [t["name"] for t in block]
    assert "ctlabs_argoapp.tasks.repositories.capture" in names
    assert names.index("ctlabs_argoapp.tasks.repositories.capture") < names.index(
        "ctlabs_argoapp.tasks.repositories.apply"
    ), "capture must precede apply"
    capture = block[names.index("ctlabs_argoapp.tasks.repositories.capture")]
    # a snapshot must never be the thing that fails the run
    assert capture["failed_when"] is False
    assert capture["no_log"] is True
    assert "repository.yml.j2" in block[
        names.index("ctlabs_argoapp.tasks.repositories.apply")
    ]["kubernetes.core.k8s"]["definition"]

    with open(os.path.join(role_dir, "tasks", "main.yml")) as f:
        main = yaml.safe_load(f)
    imports = [t["import_tasks"] for t in main if "import_tasks" in t]
    assert imports.index("repositories.yml") < imports.index("applications.yml"), (
        f"repositories must be imported before applications, got {imports}"
    )


def test_repositories_tag_also_covers_applications_run(role_dir):
    # -t ctlabs_argoapp.applications is how this role is normally limited. If
    # the repositories file were not also tagged, that run would skip the
    # credentials and every git-backed app would fail to sync.
    with open(os.path.join(role_dir, "tasks", "main.yml")) as f:
        main = yaml.safe_load(f)
    repos = next(
        t for t in main
        if t.get("import_tasks") == "repositories.yml"
    )
    assert "ctlabs_argoapp.applications" in repos["tags"]


def test_failed_run_rolls_back_credentials_it_changed(role_dir):
    # A bad credential does not harm running workloads (verified on rke21 with
    # automated.prune on: the pod stayed Running and health stayed Healthy,
    # because with no target state there is nothing to diff against and so
    # nothing is pruned). It DOES block reconciliation of every app on that
    # repository while looking healthy - so the role must undo its own credential
    # change when the reconcile that followed it fails.
    with open(os.path.join(role_dir, "tasks", "rollback.yml")) as f:
        tasks = yaml.safe_load(f)
    assert len(tasks) == 1, f"revert is a single guarded block, got {len(tasks)}"
    block = tasks[0]["block"]

    # only act on a run that actually changed credentials, and only when the
    # role manages any
    assert "ctlabs_argoapp_repositories | length > 0" in tasks[0]["when"]
    assert "res_repo is changed" in tasks[0]["when"]

    plan = _find_task(block, ".rollback.plan")
    # a failed run reverts every credential it touched; Secrets the role did not
    # touch are left strictly alone
    plan_fact = plan.get("set_fact", plan.get("ansible.builtin.set_fact"))
    assert plan_fact["_rollback_restore"] == "{{ _names | intersect(_prior) }}"
    assert plan_fact["_rollback_delete"] == "{{ _names | difference(_prior) }}"

    restore = _find_task(block, ".rollback.restore")
    delete = _find_task(block, ".rollback.delete")
    assert restore["kubernetes.core.k8s"]["state"] == "present"
    assert delete["kubernetes.core.k8s"]["state"] == "absent"
    # prior bytes go back verbatim: .data arrives base64-encoded from the API and
    # is re-applied as-is, so a PEM key cannot be mangled
    assert "_had.data" in restore["kubernetes.core.k8s"]["definition"]
    assert "_had.metadata.labels" in restore["kubernetes.core.k8s"]["definition"]
    # both touch live credentials
    assert restore["no_log"] is True
    assert delete["no_log"] is True
    assert _find_task(block, ".rollback.report") is not None

    # It must NOT hang off a block/rescue. Measured on rke21: with the whole role
    # wrapped, the recap came back `ok=23 failed=0 rescued=1` - a bad credential
    # reported as a green run. rollback is instead imported from the fail-fast
    # path, which fails the task straight after, so the recap stays `failed=1`.
    with open(os.path.join(role_dir, "tasks", "main.yml")) as f:
        assert "rescue" not in open(os.path.join(role_dir, "tasks", "main.yml")).read()
    with open(os.path.join(role_dir, "tasks", "applications.yml")) as f:
        apps = f.read()
    assert "import_tasks: rollback.yml" in apps
    assert apps.index("import_tasks: rollback.yml") < apps.index("ansible.builtin.fail")


def test_repository_secret_carries_the_discovery_label(role_dir):
    # The label IS the discovery mechanism. A Secret without it is created
    # successfully and then never read by ArgoCD - a silent failure that looks
    # exactly like wrong credentials.
    with open(os.path.join(role_dir, "templates", "repository.yml.j2")) as f:
        template = f.read()
    assert "argocd.argoproj.io/secret-type" in template
    assert "stringData" in template
    # booleans must be stringified: stringData rejects real YAML booleans
    assert "ctlabs_argoapp_namespace" in template


def test_repository_keys_are_allowlisted_not_splatted(role_dir):
    # ArgoCD silently ignores stringData keys it does not recognise, so an
    # unfiltered splat turns a typo into a mystery TLS failure at sync time.
    with open(os.path.join(role_dir, "templates", "repository.yml.j2")) as f:
        template = f.read()
    assert "password" in template and "sshPrivateKey" in template
    for forbidden in ("_repo | to_nice_json", "_repo | combine(_repo"):
        assert forbidden not in template, f"repository keys must be allowlisted, found: {forbidden}"


def test_repositories_resolved_and_validated_in_precheck(role_dir):
    with open(os.path.join(role_dir, "tasks", "precheck.yml")) as f:
        precheck = yaml.safe_load(f)
    names = [t.get("name") for t in precheck]

    resolve = next(t for t in precheck if t.get("name") == "ctlabs_argoapp.tasks.precheck.resolve")
    assert "ctlabs_argoapp_repositories" in resolve["set_fact"]

    for expected in (
        "ctlabs_argoapp.tasks.precheck.repositories.spec",
        "ctlabs_argoapp.tasks.precheck.repositories.names",
    ):
        assert expected in names, f"precheck must validate {expected}"
    spec = next(
        t for t in precheck
        if t.get("name") == "ctlabs_argoapp.tasks.precheck.repositories.spec"
    )
    assert spec["loop"] == "{{ ctlabs_argoapp_repositories }}"
    # these run no cluster calls, so they must NOT be guarded on applications
    for task in precheck:
        if ".repositories." in task.get("name", ""):
            assert "kubernetes.core" not in task, f"{task['name']} must not contact the cluster"


def test_defaults_document_repositories_as_optional(role_dir):
    with open(os.path.join(role_dir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)
    assert defaults["ctlabs_argoapp"]["defaults"]["repositories"] == []


def _find_task(tasks, suffix):
    # recursive: the reconcile wait is nested inside a block/rescue, and walking
    # only the top level breaks silently every time the task nesting changes
    for t in tasks:
        if t.get("name", "").endswith(suffix):
            return t
        for key in ("block", "rescue"):
            found = _find_task(t.get(key, []) or [], suffix)
            if found is not None:
                return found
    return None


def test_numeric_wait_knobs_are_cast_at_point_of_use(role_dir):
    # Found by live-testing against rke21: with jinja2_native off this repo's
    # ansible hands set_fact numbers back as strings, so `timeout // delay`
    # died with "unsupported operand type(s) for //: 'str' and 'str'" - after the
    # Applications had already been applied. Cast every numeric knob where it is
    # consumed; a bare arithmetic between two set_fact vars must not reappear.
    with open(os.path.join(role_dir, "tasks", "applications.yml")) as f:
        block = yaml.safe_load(f)[0]["block"]
    wait = _find_task(block, ".wait")
    assert wait["retries"] == (
        "{{ ctlabs_argoapp_wait_timeout | int // ctlabs_argoapp_wait_delay | int }}"
    )
    assert wait["delay"] == "{{ ctlabs_argoapp_wait_delay | int }}"
    # the wait is now set-level (one read of all Applications), so there is no
    # per-app `when` on it - the settle phase is what honours per-app opt-out
    assert "when" not in wait
    crd = _find_task(block, ".crd.available")
    assert crd["kubernetes.core.k8s_info"]["wait_timeout"] == "{{ ctlabs_argoapp_crd_wait | int }}"

    for path in glob.glob(os.path.join(role_dir, "tasks", "*.yml")):
        with open(path) as f2:
            text = f2.read()
        for line in text.splitlines():
            code = line.split("#")[0]
            if "//" in code:
                assert "| int //" in code, f"{os.path.basename(path)}: uncasted floor division: {code.strip()}"


def test_wait_fails_fast_on_argocd_error_conditions(role_dir):
    # Live-testing against rke21: a wrong repository credential leaves the app
    # at sync.status=Unknown with a ComparisonError condition while health stays
    # Healthy. `until: Synced and Healthy` therefore never becomes true, so a bad
    # credential burned the whole wait_timeout - 600s per application - and the
    # real cause was visible only in the ArgoCD UI.
    #
    # Two mechanisms were tried and are both wrong; keep them from creeping back:
    #   * failed_when does NOT fire between `until` retries (measured: 82s with a
    #     60s budget - it only applies after the retries are exhausted).
    #   * a per-app k8s_info inside a loop registers an aggregate whose per-item
    #     results live in .results[], so 'res.resources' is absent and every app
    #     reads as failed - including healthy ones.
    # The fix is to put "errored" INSIDE the until condition (evaluated per
    # attempt) and decide explicitly in a follow-up task.
    with open(os.path.join(role_dir, "tasks", "applications.yml")) as f:
        block = yaml.safe_load(f)[0]["block"]

    settle = _find_task(block, ".settle")
    # until exits on EITHER outcome; that is what makes it fast
    assert settle["until"] == "_pending | length == 0"
    # sync.status == 'Unknown' is the comparison-failure signal, and it must be
    # one of the two ways out of 'pending'
    assert "'Unknown'" in settle["vars"]["_errored"]
    assert "difference(_converged)" in settle["vars"]["_pending"]
    # exhausting the settle budget is not a failure - a rollout may be slow
    assert settle["failed_when"] is False
    # must be ONE read of all Applications, never a loop (aggregate register)
    assert "loop" not in settle

    errors = _find_task(block, ".settle.errors")
    assert errors is not None
    assert "error_conditions" in str(errors["when"])
    # a loop is safe here only because set_fact accumulates per iteration
    assert "loop" in errors
    # The diagnosis string is formatted HERE, while the resource is in hand.
    # Building it later through intermediate vars (_errs/_first/_msgs) re-resolved
    # them against the wrong object and raised "'dict object' has no attribute
    # 'status'" on a dict that plainly had one.
    fact = errors["set_fact"]["_argo_problems"]
    assert "_e.metadata.name" in fact
    assert "_argo_problems | default([]) + [" in fact
    assert "_msgs" not in str(errors)
    assert "_first" not in str(errors)

    # the report is a block: it rolls credentials back, then fails
    report = _find_task(block, ".settle.report")
    assert report is not None, "an errored Application must fail the run explicitly"
    assert report["when"] == "_argo_problems | default([]) | length > 0"
    assert any(t.get("import_tasks") == "rollback.yml" for t in report["block"])
    inner = _find_task(report["block"], ".settle.report")
    msg = inner["ansible.builtin.fail"]["msg"]
    assert "ArgoCD cannot reconcile" in msg
    assert "kubectl get applications" in msg
    # must not claim the workloads were harmed - they are not
    assert "nothing is pruned" in msg
    # and must point at the actual usual cause rather than telling the operator
    # to terminate a sync operation that is not stuck
    assert "repositories" in msg
    assert "terminate" not in msg.lower()

    wait = _find_task(block, ".wait")
    assert "loop" not in wait, "the long wait must also read all Applications once"
    # the long wait still gets the full budget, and also must not hard-fail so
    # the dedicated report below can produce the message
    assert wait["failed_when"] is False
    assert _find_task(block, ".wait.report") is not None

    # The per-application `wait: false` opt-out must survive the rewrite. The
    # settle/wait phases read ALL Applications in one pass and so cannot
    # re-evaluate a per-item `when` - so the opt-in list is precomputed in
    # precheck and both phases select against it. Losing this means an app that
    # asked not to be waited on gets waited on, and can fail the run.
    with open(os.path.join(role_dir, "tasks", "precheck.yml")) as f:
        pre = yaml.safe_load(f)
    waiting = next(t for t in pre if t.get("name", "").endswith(".precheck.waiting"))
    assert waiting["when"] == "_a['wait'] | default(_c) | bool"
    assert "ctlabs_argoapp_waiting" in waiting["set_fact"]

    apps_text = open(os.path.join(role_dir, "tasks", "applications.yml")).read()
    assert "ctlabs_argoapp_waiting" in apps_text
    # both the settle and the long wait must select against it
    assert apps_text.count("ctlabs_argoapp_waiting") >= 4

    with open(os.path.join(role_dir, "defaults", "main.yml")) as f:
        defaults = yaml.safe_load(f)["ctlabs_argoapp"]["defaults"]
    assert defaults["error_conditions"] == [
        "ComparisonError",
        "SyncError",
        "InvalidSpecError",
        "DeletionError",
    ]
    assert defaults["settle_retries"] == 6


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
