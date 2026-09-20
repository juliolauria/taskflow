from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

from ..database import SessionLocal
from ..models import (
    PRIORITY_COLORS,
    STATUS_DONE,
    ChecklistItem,
    Priority,
    Project,
    ResponsibleOption,
    StatusOption,
    Task,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _sort_key(task: Task):
    return task.position


def _filter_label(
    value_to_label: dict[str, str], selected: list[str], all_label: str
) -> str:
    if not selected or len(selected) >= len(value_to_label):
        return all_label
    if len(selected) == 1:
        return value_to_label.get(selected[0], selected[0])
    return f"{len(selected)} selected"


@router.get("/filters")
def views_page(
    request: Request,
    group_by: str = Query(""),
    projects: list[str] = Query(default=[]),
    priorities: list[str] = Query(default=[]),
    statuses: list[str] = Query(default=[]),
    responsibles: list[str] = Query(default=[]),
):
    with SessionLocal() as db:
        all_projects = (
            db.query(Project).filter(Project.archived.is_(False)).order_by(Project.sort_order, Project.name).all()
        )
        status_options = (
            db.query(StatusOption).order_by(StatusOption.sort_order, StatusOption.id).all()
        )
        responsible_options = db.query(ResponsibleOption).order_by(ResponsibleOption.name).all()

        query = db.query(Task).filter(Task.status != STATUS_DONE)
        if projects:
            query = query.filter(Task.project_id.in_([int(p) for p in projects]))
        if priorities:
            query = query.filter(Task.priority.in_([Priority(p) for p in priorities]))
        if statuses:
            query = query.filter(Task.status.in_(statuses))
        if responsibles:
            query = query.filter(Task.responsible.in_(responsibles))

        tasks = sorted(query.all(), key=_sort_key)

        completed_query = db.query(Task).filter(Task.status == STATUS_DONE)
        if projects:
            completed_query = completed_query.filter(Task.project_id.in_([int(p) for p in projects]))
        if priorities:
            completed_query = completed_query.filter(Task.priority.in_([Priority(p) for p in priorities]))
        if responsibles:
            completed_query = completed_query.filter(Task.responsible.in_(responsibles))

        completed_tasks = sorted(
            completed_query.all(),
            key=lambda t: t.completed_at or datetime.min,
            reverse=True,
        )

        project_names = {p.id: p.name for p in all_projects}
        project_colors = {p.id: (p.color or "#888888") for p in all_projects}
        status_colors = {s.name: s.color for s in status_options}

        checklist_totals = dict(
            db.query(ChecklistItem.task_id, func.count(ChecklistItem.id))
            .group_by(ChecklistItem.task_id)
            .all()
        )
        checklist_done = dict(
            db.query(ChecklistItem.task_id, func.count(ChecklistItem.id))
            .filter(ChecklistItem.done.is_(True))
            .group_by(ChecklistItem.task_id)
            .all()
        )

        groups: list[dict] = []
        if group_by == "project":
            buckets: dict[int | None, list[Task]] = {}
            for t in tasks:
                buckets.setdefault(t.project_id, []).append(t)
            for pid in sorted(buckets, key=lambda pid: project_names.get(pid, "")):
                groups.append({"label": project_names.get(pid, "Unknown"), "tasks": buckets[pid]})
        elif group_by == "priority":
            buckets = {}
            for t in tasks:
                buckets.setdefault(t.priority.value, []).append(t)
            for p in Priority:
                if p.value in buckets:
                    groups.append({"label": p.value, "tasks": buckets[p.value]})
        elif group_by == "status":
            buckets = {}
            for t in tasks:
                buckets.setdefault(t.status, []).append(t)
            for s in status_options:
                if s.name in buckets:
                    groups.append({"label": s.name, "tasks": buckets[s.name]})
        elif group_by == "responsible":
            buckets = {}
            for t in tasks:
                key = t.responsible or "Unassigned"
                buckets.setdefault(key, []).append(t)
            for key in sorted(buckets):
                groups.append({"label": key, "tasks": buckets[key]})
        else:
            groups.append({"label": None, "tasks": tasks})

        context = {
            "groups": groups,
            "completed_tasks": completed_tasks,
            "all_projects": all_projects,
            "projects": all_projects,
            "priorities": list(Priority),
            "priority_colors": {p.value: PRIORITY_COLORS[p] for p in Priority},
            "statuses": status_options,
            "responsible_options": responsible_options,
            "project_names": project_names,
            "project_colors": project_colors,
            "status_colors": status_colors,
            "checklist_totals": checklist_totals,
            "checklist_done": checklist_done,
            "group_by": group_by,
            "selected_projects": projects,
            "selected_priorities": priorities,
            "selected_statuses": statuses,
            "selected_responsibles": responsibles,
            "project_filter_options": [(str(p.id), p.name) for p in all_projects],
            "priority_filter_options": [(p.value, p.value) for p in Priority],
            "status_filter_options": [(s.name, s.name) for s in status_options],
            "responsible_filter_options": [(r.name, r.name) for r in responsible_options],
            "project_filter_label": _filter_label(
                {str(p.id): p.name for p in all_projects}, projects, "All Projects"
            ),
            "priority_filter_label": _filter_label(
                {p.value: p.value for p in Priority}, priorities, "All Priorities"
            ),
            "status_filter_label": _filter_label(
                {s.name: s.name for s in status_options}, statuses, "All Statuses"
            ),
            "responsible_filter_label": _filter_label(
                {r.name: r.name for r in responsible_options}, responsibles, "All Responsible"
            ),
            "current_filter": "filters",
            "request_query": request.url.query,
        }
        return templates.TemplateResponse(request, "filters_page.html", context)
