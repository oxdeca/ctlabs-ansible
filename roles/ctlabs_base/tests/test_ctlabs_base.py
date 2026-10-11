# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_base/tests/test_ctlabs_base.py
# Description : pytest tests for ctlabs_base
# ------------------------------------------------------------------------------

import os
import subprocess

import yaml


def _load(role_dir, *parts):
    with open(os.path.join(role_dir, *parts)) as fh:
        return yaml.safe_load(fh)


def test_playbook_syntax_check(role_dir):
    playbook = os.path.join(role_dir, "tests", "test_base.yml")
    result = subprocess.run(
        ["ansible-playbook", "--syntax-check", playbook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax check failed:\n{result.stderr}"


def test_main_imports_facts_after_precheck(role_dir):
    main = _load(role_dir, "tasks", "main.yml")
    imports = [task["import_tasks"] for task in main if "import_tasks" in task]

    # facts are needed inline (config.yml mounts disks from ctlabs_base_disks),
    # but must come after precheck; keep the `setup` tag so -t setup triggers them
    assert imports.index("facts.yml") > imports.index("precheck.yml")
    assert imports.index("facts.yml") < imports.index("package.yml")

    facts_import = next(t for t in main if t.get("import_tasks") == "facts.yml")
    assert "setup" in facts_import["tags"]
    assert "ctlabs_base.facts" in facts_import["tags"]


def test_precheck_only_asserts(role_dir):
    precheck = _load(role_dir, "tasks", "precheck.yml")
    text = "\n".join(str(task) for task in precheck)
    assert "assert" in text
    for module in ("template:", "win_template:", "setup:"):
        assert module not in text, f"precheck.yml must not write facts ({module})"


def test_facts_linux_writes_role_fact(role_dir):
    facts = _load(role_dir, "tasks", "facts.yml")
    linux = next(task for task in facts if "redhat" in str(task.get("when")))
    block = linux["block"]

    write = next(task for task in block if "template" in task)
    assert write["template"]["src"] == "facts.json.j2"
    assert write["template"]["dest"].endswith("ctlabs_base.fact")

    # disks are resolved from the declarative role fact, not metadata
    disks = next(task for task in block if "disks" in task["name"])
    assert "ctlabs_base_disks" in str(disks["set_fact"])


def test_facts_windows_writes_role_fact(role_dir):
    facts = _load(role_dir, "tasks", "facts.yml")
    windows = next(
        task for task in facts if str(task.get("when")) == "ctg_os_family == 'windows'"
    )
    block = windows["block"]

    assert any("facts_dir" in task["name"] and "win_file" in task for task in block)

    write = next(task for task in block if "win_template" in task)
    assert write["win_template"]["src"] == "facts.ps1.j2"
    assert write["win_template"]["dest"].endswith("ctlabs_base.ps1")

    assert any("setup" in task and task["setup"].get("fact_path") for task in block)


def test_facts_json_template_has_disks(role_dir):
    path = os.path.join(role_dir, "templates", "facts.json.j2")
    with open(path) as fh:
        content = fh.read()
    assert "disks" in content
    assert "to_json" in content


def test_windows_fact_emits_json(role_dir):
    path = os.path.join(role_dir, "templates", "facts.ps1.j2")
    with open(path) as fh:
        content = fh.read()
    assert "ConvertTo-Json" in content


def test_no_metadata_or_legacy_refs(role_dir):
    # facts for all: no GCP metadata lookups and no legacy global-fact/dest names
    offenders = []
    for root, _dirs, files in os.walk(role_dir):
        if "__pycache__" in root or os.sep + "tests" in root:
            continue
        for name in files:
            if not name.endswith((".yml", ".j2")):
                continue
            path = os.path.join(root, name)
            with open(path) as fh:
                for lineno, line in enumerate(fh, 1):
                    if any(
                        token in line
                        for token in (
                            "metadata.google",
                            "ctlabs.fact.ps1",
                            "ctlabs_base_disks.fact",
                            "gce_disk_prefix",
                            "bashrc.kali.sh",
                        )
                    ):
                        offenders.append(f"{path}:{lineno}")
    assert not offenders, f"legacy/metadata refs found: {offenders}"


def test_ctg_facts_maps_ctlabs_base(ansible_repo_root):
    path = os.path.join(
        ansible_repo_root, "inventories", "group_vars", "all", "ctlabs.yml"
    )
    with open(path) as fh:
        content = fh.read()
    assert "'ctlabs_base':" in content
    assert "ansible_ctlabs_base" in content
