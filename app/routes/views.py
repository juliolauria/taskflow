from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

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


def _checklist_counts(db: Session) -> tuple[dict[int, int], dict[int, int]]:
    totals = dict(
        db.query(ChecklistItem.task_id, func.count(ChecklistItem.id))
        .group_by(ChecklistItem.task_id)
        .all()
    )
    done = dict(
        db.query(ChecklistItem.task_id, func.count(ChecklistItem.id))
        .filter(ChecklistItem.done.is_(True))
        .group_by(ChecklistItem.task_id)
        .all()
    )
    return totals, done


def build_active_context(db: Session, filter_value: str) -> dict:
    filter_value = filter_value or "all"

    projects = (
        db.query(Project)
        .filter(Project.archived.is_(False))
        .order_by(Project.sort_order, Project.name)
        .all()
    )
    status_options = (
        db.query(StatusOption).order_by(StatusOption.sort_order, StatusOption.id).all()
    )
    responsible_options = db.query(ResponsibleOption).order_by(ResponsibleOption.name).all()

    query = db.query(Task).filter(Task.status != STATUS_DONE)

    matched_project = None
    if filter_value != "all":
        matched_project = next((p for p in projects if str(p.id) == filter_value), None)
        if matched_project is not None:
            query = query.filter(Task.project_id == matched_project.id)
        else:
            filter_value = "all"

    tasks = query.all()

    groups: list[dict] = []

    if filter_value == "all":
        # One flat, spreadsheet-style table across every project — the
        # Project column (not a section boundary) tells you which is which.
        all_tasks = sorted(tasks, key=_sort_key)
        if all_tasks:
            groups.append({"project": None, "tasks": all_tasks})
        view_title = "All Tasks"
    else:
        project_tasks = sorted(tasks, key=_sort_key)
        if project_tasks:
            groups.append({"project": matched_project, "tasks": project_tasks})
        view_title = matched_project.name

    completed_query = db.query(Task).filter(Task.status == STATUS_DONE)
    if filter_value != "all":
        completed_query = completed_query.filter(Task.project_id == matched_project.id)

    completed_tasks = sorted(
        completed_query.all(),
        key=lambda t: t.completed_at or datetime.min,
        reverse=True,
    )

    checklist_totals, checklist_done = _checklist_counts(db)

    return {
        "groups": groups,
        "show_project_column": filter_value == "all",
        "projects": projects,
        "project_names": {p.id: p.name for p in projects},
        "project_colors": {p.id: (p.color or "#888888") for p in projects},
        "completed_tasks": completed_tasks,
        "current_filter": filter_value,
        "current_project_id": matched_project.id if matched_project else None,
        "view_title": view_title,
        "priorities": list(Priority),
        "priority_colors": {p.value: PRIORITY_COLORS[p] for p in Priority},
        "statuses": status_options,
        "status_colors": {s.name: s.color for s in status_options},
        "responsible_options": responsible_options,
        "checklist_totals": checklist_totals,
        "checklist_done": checklist_done,
    }


@router.get("/")
def active_view(request: Request, project: str = Query("all")):
    with SessionLocal() as db:
        context = build_active_context(db, project)
        return templates.TemplateResponse(request, "active.html", context)
