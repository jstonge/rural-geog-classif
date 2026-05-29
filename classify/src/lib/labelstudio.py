"""Label Studio scaffolding — client + pull + push + summarize.

Generic helpers that don't know about rural-geog specifically. Keep this
file portable: any project that talks to LS over the SDK should be able
to copy it into its own `annotate/src/lib/` and run.

Project-specific glue (which task data field is the key, which control
names exist, which schema goes with which project id) stays in callers
— this module only parameterizes those choices, never hardcodes them.

Functions
---------
- make_client                — factory from .env or explicit credentials
- load_gt                    — most-recent-wins ground truth pull
- summarize_project          — per-control + per-annotator stats
- backup_project             — dump project + tasks to JSON
- push_annotations           — push one annotation per key, attributed to a user
- remove_annotations_by_user — backout for push_annotations
- push_task_data             — merge updates into task.data fields by key
- create_project_from_df     — bulk-create a project from a dataframe
- annotator_label            — display name for an LS user object

Environment
-----------
Expects LABEL_STUDIO_URL and LABEL_STUDIO_API_KEY in the environment
(or a .env file discoverable by python-dotenv).
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pandas as pd
from dotenv import load_dotenv

if TYPE_CHECKING:
    from label_studio_sdk import LabelStudio


# ----- client ------------------------------------------------------------

def make_client(*, base_url: str | None = None, api_key: str | None = None,
                verify_ssl: bool = False) -> "LabelStudio":
    """Create a LabelStudio SDK client.

    Credentials default to env vars (LABEL_STUDIO_URL / LABEL_STUDIO_API_KEY),
    loaded via python-dotenv. verify_ssl=False matches the project's
    historical setup (self-signed cert); pass True for production use.
    """
    load_dotenv()
    from label_studio_sdk import LabelStudio
    return LabelStudio(
        base_url=base_url or os.getenv("LABEL_STUDIO_URL"),
        api_key=api_key or os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=verify_ssl),
    )


# ----- pull --------------------------------------------------------------

def load_gt(client: "LabelStudio", project_id: int, control: str, *,
            key_field: str = "id") -> pd.DataFrame:
    """Fetch ground truth for a control from a live LS project.

    `control` matches the LS <Choices name="..."> from_name in the labeling
    config. When a task has multiple annotations, the most-recently-updated
    one wins. `key_field` is the task.data field used as the row key
    (e.g. "DOI" or "post_id"); falls back to t.id if not present.

    Returns DataFrame with columns [{key_field}, {control}_gt] where
    {control}_gt is list[str]. Tasks with no choices for this control are
    dropped.
    """
    records: list[dict] = []
    for t in client.tasks.list(project=project_id, fields="all"):
        key = (t.data or {}).get(key_field, t.id)
        if key is None:
            continue
        # most-recently-updated annotation wins
        anns = sorted(
            t.annotations or [],
            key=lambda a: a.get("updated_at") or a.get("created_at") or "",
            reverse=True,
        )
        for ann in anns:
            found = False
            for r in ann.get("result", []):
                if r.get("from_name") == control and r.get("type") == "choices":
                    choices = r.get("value", {}).get("choices", [])
                    if choices:
                        records.append({key_field: key, f"{control}_gt": list(choices)})
                        found = True
                        break
            if found:
                break
    if not records:
        return pd.DataFrame(columns=[key_field, f"{control}_gt"])
    return pd.DataFrame(records)


def annotator_label(u: Any) -> str:
    """Display name for an LS user: full name -> email -> user_<id> fallback."""
    name = " ".join(
        s for s in [getattr(u, "first_name", None), getattr(u, "last_name", None)] if s
    ).strip()
    return name or getattr(u, "email", None) or f"user_{u.id}"


def summarize_project(client: "LabelStudio", project_id: int,
                       users_by_id: dict[int, dict] | None = None) -> dict:
    """Per-control + per-annotator + throughput stats for one project.

    `users_by_id` maps user id -> {"id", "name", "email"}; pass None to
    fetch via client.users.list() (extra API round trip).

    Returns a dict suitable for serializing to a dashboard JSON.
    """
    if users_by_id is None:
        users_by_id = {
            u.id: {"id": u.id, "email": getattr(u, "email", None),
                   "name": annotator_label(u)}
            for u in client.users.list()
        }

    tasks = list(client.tasks.list(project=project_id))

    label_totals: dict[str, Counter] = defaultdict(Counter)
    by_annotator: dict[str, dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    annotator_stats: dict[int, dict] = defaultdict(
        lambda: {"n_annotations": 0, "tasks": set(), "controls": set()}
    )
    annotations_per_task: Counter = Counter()
    n_annotated = 0

    for t in tasks:
        if not t.annotations:
            annotations_per_task[0] += 1
            continue
        n_annotated += 1
        annotations_per_task[len(t.annotations)] += 1
        for ann in t.annotations:
            uid = ann.get("completed_by")
            stats = annotator_stats[uid]
            stats["n_annotations"] += 1
            stats["tasks"].add(t.id)
            for r in ann.get("result", []):
                if r.get("type") != "choices":
                    continue
                control = r["from_name"]
                stats["controls"].add(control)
                for choice in r["value"]["choices"]:
                    label_totals[control][choice] += 1
                    by_annotator[control][uid][choice] += 1

    controls = sorted(label_totals.keys())
    annotators = []
    for uid, stats in annotator_stats.items():
        u = users_by_id.get(uid, {"id": uid, "email": None, "name": f"user_{uid}"})
        annotators.append({
            "id": uid,
            "name": u["name"],
            "email": u["email"],
            "n_annotations": stats["n_annotations"],
            "n_tasks": len(stats["tasks"]),
            "controls": sorted(stats["controls"]),
        })
    annotators.sort(key=lambda a: a["n_annotations"], reverse=True)

    return {
        "project_id": project_id,
        "n_tasks_total": len(tasks),
        "n_tasks_annotated": n_annotated,
        "controls": controls,
        "annotators": annotators,
        "label_distribution": {
            c: dict(sorted(label_totals[c].items(), key=lambda kv: -kv[1]))
            for c in controls
        },
        "by_annotator": {
            c: {str(uid): dict(sorted(by_annotator[c][uid].items(),
                                       key=lambda kv: -kv[1]))
                for uid in by_annotator[c]}
            for c in controls
        },
        "annotations_per_task": dict(sorted(annotations_per_task.items())),
    }


# ----- backup ------------------------------------------------------------

def _to_jsonable(obj: Any) -> Any:
    """Best-effort conversion of LS SDK pydantic-ish objects to plain dicts."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return obj.dict()
        except TypeError:
            pass
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def backup_project(client: "LabelStudio", project_id: int, out_dir: Path) -> int:
    """Dump one project to {out_dir}/project.json + tasks.json. Returns task count.

    Run before any mutation (push_annotations, push_task_data,
    create_project_from_df with an existing label config, etc.).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    project = client.projects.get(id=project_id)
    project_meta = {
        "id":           project.id,
        "title":        getattr(project, "title", None),
        "description":  getattr(project, "description", None),
        "label_config": project.label_config,
        "created_at":   str(getattr(project, "created_at", "")),
    }
    (out_dir / "project.json").write_text(
        json.dumps(project_meta, indent=2, ensure_ascii=False))

    tasks_out = []
    for t in client.tasks.list(project=project_id, fields="all"):
        tasks_out.append({
            "id":          t.id,
            "data":        t.data,
            "annotations": _to_jsonable(getattr(t, "annotations", []) or []),
            "predictions": _to_jsonable(getattr(t, "predictions", []) or []),
        })
    (out_dir / "tasks.json").write_text(
        json.dumps(tasks_out, indent=2, ensure_ascii=False, default=str))
    return len(tasks_out)


# ----- push annotations --------------------------------------------------

def push_annotations(client: "LabelStudio", project_id: int,
                      key_to_labels: dict[Any, list[str]], control: str, *,
                      user_id: int, to_name: str = "text",
                      key_field: str = "id", ground_truth: bool = False,
                      apply: bool = False, backdate_iso: str | None = None,
                      ) -> list[int]:
    """Push one annotation per key, completed_by user_id.

    `key_to_labels` maps task key (DOI / post_id / etc.) to list[str] of
    choice labels. Single-label tasks: pass a 1-element list.

    `control` matches the LS <Choices name="..."> from_name. `to_name`
    matches its toName attribute (defaults to "text").

    `apply=False` does dry-run (prints a sample, returns []). Returns
    list of created annotation ids.

    `backdate_iso` (e.g. "2024-01-01T00:00:00Z") PATCHes created_at on
    each pushed annotation so they sort behind human annotators.
    """
    from label_studio_sdk.core.api_error import ApiError

    tasks = list(client.tasks.list(project=project_id))
    key_to_task = {(t.data or {}).get(key_field, t.id): t.id for t in tasks}
    matched = [(k, key_to_task[k], lbls) for k, lbls in key_to_labels.items()
               if k in key_to_task and lbls]
    print(f"  matched {len(matched)}/{len(key_to_labels)} keys to existing tasks")

    if not apply:
        if matched:
            k, tid, lbls = matched[0]
            print(f"  dry-run sample: task_id={tid} key={k} choices={lbls} "
                  f"completed_by={user_id} ground_truth={ground_truth}")
        print("  DRY RUN — pass apply=True to push.")
        return []

    pushed_ids: list[int] = []
    for _, tid, lbls in matched:
        try:
            ann = client.annotations.create(
                id=tid,
                result=[{
                    "from_name": control,
                    "to_name": to_name,
                    "type": "choices",
                    "value": {"choices": list(lbls)},
                }],
                completed_by=user_id,
                ground_truth=ground_truth,
            )
            pushed_ids.append(ann.id)
        except ApiError as e:
            print(f"!! push failed for task {tid}: status={e.status_code} body={e.body}")
            break

    if backdate_iso and pushed_ids:
        base = (os.getenv("LABEL_STUDIO_URL") or "").rstrip("/")
        key = os.getenv("LABEL_STUDIO_API_KEY")
        headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
        n_ok = 0
        with httpx.Client(verify=False) as h:
            for aid in pushed_ids:
                r = h.patch(f"{base}/api/annotations/{aid}/", headers=headers,
                            json={"created_at": backdate_iso})
                if r.status_code in (200, 204):
                    n_ok += 1
                else:
                    print(f"!! backdate failed for ann {aid}: {r.status_code} {r.text[:200]}")
                    break
        print(f"  backdated {n_ok}/{len(pushed_ids)} to {backdate_iso}")

    print(f"  pushed {len(pushed_ids)} annotations (completed_by={user_id})")
    return pushed_ids


def remove_annotations_by_user(client: "LabelStudio", project_id: int,
                                 user_id: int, *, apply: bool = False) -> int:
    """Delete every annotation in `project_id` completed_by `user_id`.

    Backout for push_annotations() with the same user_id. apply=False does
    dry-run. Returns count of (would-be / were) deleted.
    """
    tasks = list(client.tasks.list(project=project_id, fields="all"))
    to_delete = [
        ann["id"]
        for t in tasks
        for ann in (t.annotations or [])
        if ann.get("completed_by") == user_id
    ]
    print(f"  annotations completed_by={user_id} in project {project_id}: {len(to_delete)}")
    if not apply:
        print("  DRY RUN — pass apply=True to delete.")
        return len(to_delete)
    for aid in to_delete:
        client.annotations.delete(id=aid)
    print(f"  deleted {len(to_delete)} annotations.")
    return len(to_delete)


# ----- push task data ----------------------------------------------------

def push_task_data(client: "LabelStudio", project_id: int,
                    key_to_updates: dict[Any, dict[str, Any]], *,
                    key_field: str = "id", apply: bool = False) -> int:
    """Merge updates into task.data fields by key.

    `key_to_updates` maps task key -> {field_name: new_value, ...}. The
    update is *merged* into the existing data dict (keys not mentioned
    are preserved). An empty update dict for a key is a no-op.

    Common uses: pushing auxiliary HTML context (intro_section_html,
    method_section_html) for annotator-facing display. apply=False does
    dry-run. Returns count of tasks (would be / were) updated.
    """
    tasks = list(client.tasks.list(project=project_id))
    key_to_task = {(t.data or {}).get(key_field, t.id): t for t in tasks}
    patches: list[tuple[int, dict]] = []
    for k, updates in key_to_updates.items():
        t = key_to_task.get(k)
        if t is None or not updates:
            continue
        patches.append((t.id, {**(t.data or {}), **updates}))
    print(f"  patches: {len(patches)}/{len(key_to_updates)}")
    if not apply:
        print("  DRY RUN — pass apply=True to push.")
        return len(patches)
    for tid, new_data in patches:
        client.tasks.update(id=tid, data=new_data)
    print(f"  updated {len(patches)} tasks.")
    return len(patches)


# ----- create project ----------------------------------------------------

def create_project_from_df(client: "LabelStudio", df: pd.DataFrame, *,
                            title: str, label_config: str,
                            predictions: list[dict] | None = None,
                            wait_for_commit: bool = True,
                            wait_max_attempts: int = 20,
                            wait_seconds: float = 2.0) -> Any:
    """Create a new project from a flat dataframe (one row per task).

    Phase 1: bulk-import tasks via `projects.import_tasks` (df rows
    become task.data dicts directly — no nested "data" wrapper).

    Phase 2 (optional): bulk-import predictions via
    `projects.import_predictions`. Each prediction is
    {"task": task_id, "result": [...], "model_version": "..."} — the
    caller resolves task_id from whatever key field they're using.

    Returns the created project object.
    """
    from label_studio_sdk.core.api_error import ApiError
    records = json.loads(df.to_json(orient="records"))

    project = client.projects.create(title=title, label_config=label_config)
    print(f"  created project {project.id}: {title!r}")
    try:
        client.projects.import_tasks(id=project.id, request=records,
                                      commit_to_project=True)
    except ApiError as e:
        print(f"!!! import_tasks ApiError status={e.status_code} body={e.body}")
        raise

    if wait_for_commit:
        expected = len(records)
        n = 0
        for _ in range(wait_max_attempts):
            n = len(list(client.tasks.list(project=project.id)))
            if n >= expected:
                break
            print(f"  waiting for tasks to commit... {n}/{expected}")
            time.sleep(wait_seconds)
        print(f"  tasks visible: {n}/{expected}")

    if predictions:
        pred_response = client.projects.import_predictions(id=project.id,
                                                            request=predictions)
        print(f"  predictions response: {pred_response}")
        print(f"  attached {len(predictions)} predictions")
    return project
