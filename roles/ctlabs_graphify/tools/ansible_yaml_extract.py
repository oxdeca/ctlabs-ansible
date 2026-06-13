#!/usr/bin/env python3
"""Extract Ansible YAML structure into graphify graph.json."""

import json
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path("/root/ctlabs-ansible")
GRAPH_FILE = REPO_ROOT / "graphify-out" / "graph.json"


def norm_id(name):
    return re.sub(r'[^a-zA-Z0-9_]', '_', name).strip('_')[:200]


def make_id(prefix, name):
    return f"{prefix}_{norm_id(name)}"


def make_label(path, name):
    return f"{path}:{name}"[:200]


def extract_tasks(filepath, rel_path):
    """Extract task names, import_tasks edges from a task file."""
    nodes = []
    links = []
    parts = rel_path.split(os.sep)
    if len(parts) >= 4 and parts[0] == 'roles' and parts[2] == 'tasks':
        role_name = parts[1]
    elif len(parts) >= 4 and parts[0] == 'roles' and parts[2] == 'handlers':
        role_name = parts[1]
    else:
        role_name = None

    file_id = make_id("file", rel_path.replace('/', '_').replace('.', '_'))
    file_label = str(rel_path)

    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"  [skip] {rel_path}: {e}")
        return nodes, links

    if not isinstance(data, list):
        return nodes, links

    nodes.append({
        "label": file_label,
        "file_type": "ansible_tasks",
        "source_file": str(rel_path),
        "source_location": "L1",
        "_origin": "yaml_extract",
        "id": file_id,
        "community": 0,
        "norm_label": file_label,
    })

    seen_imports = set()

    for task in data:
        if not isinstance(task, dict):
            continue

        task_id = None
        task_name = task.get('name')

        # import_tasks
        imp = task.get('import_tasks') or task.get('include_tasks')
        if imp and imp not in seen_imports:
            seen_imports.add(imp)
            imported_file = str(Path(rel_path).parent / imp)
            imported_id = make_id("file", imported_file.replace('/', '_').replace('.', '_'))
            links.append({
                "relation": "imports",
                "confidence": "EXTRACTED",
                "source_file": str(rel_path),
                "source_location": "",
                "weight": 1.0,
                "source": file_id,
                "target": imported_id,
                "confidence_score": 1.0,
            })

        # task names
        if task_name:
            task_id = make_id("task", task_name)
            nodes.append({
                "label": task_name,
                "file_type": "ansible_task",
                "source_file": str(rel_path),
                "source_location": "",
                "_origin": "yaml_extract",
                "id": task_id,
                "community": 0,
                "norm_label": make_label(rel_path, task_name),
            })
            links.append({
                "relation": "contains_task",
                "confidence": "EXTRACTED",
                "source_file": str(rel_path),
                "source_location": "",
                "weight": 1.0,
                "source": file_id,
                "target": task_id,
                "confidence_score": 1.0,
            })

            if role_name:
                role_id = make_id("role", role_name)
                links.append({
                    "relation": "role_task",
                    "confidence": "EXTRACTED",
                    "source_file": str(rel_path),
                    "source_location": "",
                    "weight": 1.0,
                    "source": role_id,
                    "target": task_id,
                    "confidence_score": 1.0,
                })

        # tags on task
        if task_id:
            tags = task.get('tags', [])
            if isinstance(tags, str):
                tags = [tags]
            if isinstance(tags, list):
                for tag in tags:
                    tag_id = make_id("tag", tag)
                    nodes.append({
                        "label": tag,
                        "file_type": "ansible_tag",
                        "source_file": str(rel_path),
                        "source_location": "",
                        "_origin": "yaml_extract",
                        "id": tag_id,
                        "community": 0,
                        "norm_label": tag,
                    })
                    links.append({
                        "relation": "has_tag",
                        "confidence": "EXTRACTED",
                        "source_file": str(rel_path),
                        "source_location": "",
                        "weight": 1.0,
                        "source": task_id,
                        "target": tag_id,
                        "confidence_score": 1.0,
                    })

        # blocks → recurse into nested tasks
        block = task.get('block')
        if isinstance(block, list):
            sub_nodes, sub_links = extract_block_tasks(block, rel_path, file_id, role_name)
            nodes.extend(sub_nodes)
            links.extend(sub_links)

        # notify handlers
        if task_id:
            notify = task.get('notify')
            if notify:
                if isinstance(notify, str):
                    notifies = [notify]
                elif isinstance(notify, list):
                    notifies = notify
                else:
                    notifies = []
                for n in notifies:
                    handler_id = make_id("handler", n)
                    nodes.append({
                        "label": n,
                        "file_type": "ansible_handler",
                        "source_file": str(rel_path),
                        "source_location": "",
                        "_origin": "yaml_extract",
                        "id": handler_id,
                        "community": 0,
                        "norm_label": n,
                    })
                    links.append({
                        "relation": "notifies",
                        "confidence": "EXTRACTED",
                        "source_file": str(rel_path),
                        "source_location": "",
                        "weight": 1.0,
                        "source": task_id,
                        "target": handler_id,
                        "confidence_score": 1.0,
                    })

    return nodes, links


def extract_block_tasks(block, rel_path, parent_file_id, role_name):
    """Extract tasks inside a block."""
    nodes = []
    links = []
    for task in block:
        if not isinstance(task, dict):
            continue
        task_name = task.get('name')
        if not task_name:
            continue
        task_id = make_id("task", task_name)
        nodes.append({
            "label": task_name,
            "file_type": "ansible_task",
            "source_file": str(rel_path),
            "source_location": "",
            "_origin": "yaml_extract",
            "id": task_id,
            "community": 0,
            "norm_label": make_label(rel_path, task_name),
        })
        links.append({
            "relation": "contains_task",
            "confidence": "EXTRACTED",
            "source_file": str(rel_path),
            "source_location": "",
            "weight": 1.0,
            "source": parent_file_id,
            "target": task_id,
            "confidence_score": 1.0,
        })
        if role_name:
            role_id = make_id("role", role_name)
            links.append({
                "relation": "role_task",
                "confidence": "EXTRACTED",
                "source_file": str(rel_path),
                "source_location": "",
                "weight": 1.0,
                "source": role_id,
                "target": task_id,
                "confidence_score": 1.0,
            })

        # nested blocks
        sub_block = task.get('block')
        if isinstance(sub_block, list):
            sub_nodes, sub_links = extract_block_tasks(sub_block, rel_path, parent_file_id, role_name)
            nodes.extend(sub_nodes)
            links.extend(sub_links)
    return nodes, links


def extract_playbook(filepath, rel_path):
    """Extract plays, roles, tags from a playbook."""
    nodes = []
    links = []

    pb_id = make_id("playbook", rel_path.replace('/', '_').replace('.', '_'))
    pb_label = str(rel_path)

    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"  [skip] {rel_path}: {e}")
        return nodes, links

    if not isinstance(data, list):
        return nodes, links

    nodes.append({
        "label": pb_label,
        "file_type": "ansible_playbook",
        "source_file": str(rel_path),
        "source_location": "L1",
        "_origin": "yaml_extract",
        "id": pb_id,
        "community": 0,
        "norm_label": pb_label,
    })

    for play in data:
        if not isinstance(play, dict):
            continue

        play_name = play.get('name') or 'unnamed'
        play_id = make_id("play", play_name)

        nodes.append({
            "label": play_name,
            "file_type": "ansible_play",
            "source_file": str(rel_path),
            "source_location": "",
            "_origin": "yaml_extract",
            "id": play_id,
            "community": 0,
            "norm_label": f"{rel_path}:{play_name}",
        })
        links.append({
            "relation": "contains_play",
            "confidence": "EXTRACTED",
            "source_file": str(rel_path),
            "source_location": "",
            "weight": 1.0,
            "source": pb_id,
            "target": play_id,
            "confidence_score": 1.0,
        })

        # hosts
        hosts = play.get('hosts', '')
        if hosts:
            hosts_id = make_id("hosts", str(hosts))
            nodes.append({
                "label": str(hosts),
                "file_type": "ansible_hosts",
                "source_file": str(rel_path),
                "source_location": "",
                "_origin": "yaml_extract",
                "id": hosts_id,
                "community": 0,
                "norm_label": str(hosts),
            })
            links.append({
                "relation": "targets",
                "confidence": "EXTRACTED",
                "source_file": str(rel_path),
                "source_location": "",
                "weight": 1.0,
                "source": play_id,
                "target": hosts_id,
                "confidence_score": 1.0,
            })

        # tags
        tags = play.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
        if isinstance(tags, list):
            for tag in tags:
                tag_id = make_id("tag", tag)
                nodes.append({
                    "label": tag,
                    "file_type": "ansible_tag",
                    "source_file": str(rel_path),
                    "source_location": "",
                    "_origin": "yaml_extract",
                    "id": tag_id,
                    "community": 0,
                    "norm_label": tag,
                })
                links.append({
                    "relation": "has_tag",
                    "confidence": "EXTRACTED",
                    "source_file": str(rel_path),
                    "source_location": "",
                    "weight": 1.0,
                    "source": play_id,
                    "target": tag_id,
                    "confidence_score": 1.0,
                })

        # roles
        roles = play.get('roles', [])
        if isinstance(roles, list):
            for role_ref in roles:
                if isinstance(role_ref, str):
                    role_name = role_ref.replace('roles/', '')
                elif isinstance(role_ref, dict):
                    role_name = role_ref.get('role', '')
                else:
                    continue
                if not role_name:
                    continue
                role_id = make_id("role", role_name)
                nodes.append({
                    "label": role_name,
                    "file_type": "ansible_role",
                    "source_file": str(rel_path),
                    "source_location": "",
                    "_origin": "yaml_extract",
                    "id": role_id,
                    "community": 0,
                    "norm_label": role_name,
                })
                links.append({
                    "relation": "uses_role",
                    "confidence": "EXTRACTED",
                    "source_file": str(rel_path),
                    "source_location": "",
                    "weight": 1.0,
                    "source": play_id,
                    "target": role_id,
                    "confidence_score": 1.0,
                })

    return nodes, links


def extract_defaults(filepath, rel_path):
    """Extract top-level variable names from defaults/main.yml."""
    nodes = []
    links = []

    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"  [skip] {rel_path}: {e}")
        return nodes, links

    if not isinstance(data, dict):
        return nodes, links

    file_id = make_id("defaults", rel_path.replace('/', '_').replace('.', '_'))
    nodes.append({
        "label": f"{rel_path}",
        "file_type": "ansible_defaults",
        "source_file": str(rel_path),
        "source_location": "L1",
        "_origin": "yaml_extract",
        "id": file_id,
        "community": 0,
        "norm_label": f"defaults:{rel_path}",
    })

    for key in data:
        var_id = make_id("var", key)
        nodes.append({
            "label": key,
            "file_type": "ansible_var",
            "source_file": str(rel_path),
            "source_location": "",
            "_origin": "yaml_extract",
            "id": var_id,
            "community": 0,
            "norm_label": key,
        })
        links.append({
            "relation": "defines_var",
            "confidence": "EXTRACTED",
            "source_file": str(rel_path),
            "source_location": "",
            "weight": 1.0,
            "source": file_id,
            "target": var_id,
            "confidence_score": 1.0,
        })

    return nodes, links


def main():
    all_nodes = []
    all_links = []
    seen_ids = set()
    added_nodes = {}
    added_links = set()

    def add_nodes(nodes):
        for n in nodes:
            nid = n['id']
            if nid not in seen_ids:
                added_nodes[nid] = n
                seen_ids.add(nid)

    def add_links(links):
        for l in links:
            key = (l['source'], l['target'], l['relation'])
            if key not in added_links:
                all_links.append(l)
                added_links.add(key)

    # Walk roles
    roles_dir = REPO_ROOT / "roles"
    if roles_dir.exists():
        for role_dir in sorted(roles_dir.iterdir()):
            if not role_dir.is_dir() or role_dir.name.startswith('.'):
                continue

            # Create role node
            role_id = make_id("role", role_dir.name)
            add_nodes([{
                "label": role_dir.name,
                "file_type": "ansible_role",
                "source_file": f"roles/{role_dir.name}",
                "source_location": "L1",
                "_origin": "yaml_extract",
                "id": role_id,
                "community": 0,
                "norm_label": role_dir.name,
            }])

            # Task files
            tasks_dir = role_dir / "tasks"
            if tasks_dir.exists():
                for task_file in sorted(tasks_dir.glob("*.yml")):
                    rel = str(task_file.relative_to(REPO_ROOT))
                    print(f"  tasks: {rel}")
                    n, l = extract_tasks(task_file, rel)
                    add_nodes(n)
                    add_links(l)

            # Handlers
            handlers_dir = role_dir / "handlers"
            if handlers_dir.exists():
                for hf in sorted(handlers_dir.glob("*.yml")):
                    rel = str(hf.relative_to(REPO_ROOT))
                    print(f"  handlers: {rel}")
                    n, l = extract_tasks(hf, rel)
                    add_nodes(n)
                    add_links(l)

            # Defaults
            defaults_file = role_dir / "defaults" / "main.yml"
            if defaults_file.exists():
                rel = str(defaults_file.relative_to(REPO_ROOT))
                print(f"  defaults: {rel}")
                n, l = extract_defaults(defaults_file, rel)
                add_nodes(n)
                add_links(l)

    # Walk playbooks
    playbooks_dir = REPO_ROOT / "playbooks"
    if playbooks_dir.exists():
        for pb in sorted(playbooks_dir.glob("*.yml")):
            rel = str(pb.relative_to(REPO_ROOT))
            print(f"  playbook: {rel}")
            n, l = extract_playbook(str(pb), rel)
            add_nodes(n)
            add_links(l)

    # Read existing graph
    if GRAPH_FILE.exists():
        with open(GRAPH_FILE) as f:
            graph = json.load(f)
    else:
        print(f"ERROR: {GRAPH_FILE} not found")
        sys.exit(1)

    old_node_count = len(graph['nodes'])
    old_link_count = len(graph['links'])

    # Merge: deduplicate by id
    existing_ids = {n['id'] for n in graph['nodes']}
    for n in added_nodes.values():
        if n['id'] not in existing_ids:
            graph['nodes'].append(n)

    # Merge links
    existing_links = {(l['source'], l['target'], l['relation']) for l in graph['links']}
    for l in all_links:
        key = (l['source'], l['target'], l['relation'])
        if key not in existing_links:
            graph['links'].append(l)
            existing_links.add(key)

    graph['built_at_commit'] = "yaml_extracted"

    with open(GRAPH_FILE, 'w') as f:
        json.dump(graph, f, indent=2)

    added_nodes_count = len(added_nodes) - len(existing_ids & seen_ids)
    print(f"\nSummary:")
    print(f"  Nodes: {old_node_count} → {len(graph['nodes'])} (+{len(graph['nodes']) - old_node_count})")
    print(f"  Links: {old_link_count} → {len(graph['links'])} (+{len(graph['links']) - old_link_count})")


if __name__ == '__main__':
    print("Extracting Ansible YAML into graphify graph...")
    main()
