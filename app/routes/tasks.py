from datetime import date, datetime

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

from ..database import SessionLocal
from ..models import (
    PRIORITY_COLORS,
    STATUS_DONE,
    STATUS_TODO,
    ChecklistItem,
    Priority,
    Project,
    ResponsibleOption,
    StatusOption,
    Task,
)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

EDITABLE_FIELDS = {
    "title",
    "priority",
    "status",
    "responsible",
    "deadline",
    "project_id",
    "comments",
}


def _filter_to_project_id(filter_value: str) -> int | None:
    if filter_value == "all" or not filter_value:
        return None
    try:
        return int(filter_value)
    except ValueError:
        return None


def _redirect_home(redirect_to: str) -> RedirectResponse:
    return RedirectResponse(redirect_to or "/", status_code=303)


def _remember_responsible(db, name: str) -> None:
    """Typing a new name into a Responsible field also registers it as a
    reusable option, so it shows up in autocomplete/manage everywhere else."""
    name = name.strip()
    if not name:
        return
    exists = db.query(ResponsibleOption).filter(ResponsibleOption.name == name).first()
    if exists is None:
        db.add(ResponsibleOption(name=name))


@router.post("/tasks")
def create_task(
    request: Request,
    title: str = Form(...),
    project: str = Query("all"),
    project_id: str = Form(""),
    redirect_to: str = Form(""),
):
    title = title.strip()
    resolved_project_id = int(project_id) if project_id else _filter_to_project_id(project)

    if title and resolved_project_id is not None:
        with SessionLocal() as db:
            next_position = (db.query(func.max(Task.position)).scalar() or 0) + 10
            task = Task(
                title=title,
                project_id=resolved_project_id,
                priority=Priority.MEDIUM,
                status=STATUS_TODO,
                responsible="",
                position=next_position,
            )
            db.add(task)
            db.commit()

    return _redirect_home(redirect_to)


@router.post("/tasks/reorder")
def reorder_tasks(
    request: Request,
    order: list[str] = Form(...),
    redirect_to: str = Form(""),
):
    ids = [int(i) for i in order if i]

    with SessionLocal() as db:
        tasks = db.query(Task).filter(Task.id.in_(ids)).all()
        tasks_by_id = {t.id: t for t in tasks}
        base = min((t.position for t in tasks), default=0)
        for index, task_id in enumerate(ids):
            task = tasks_by_id.get(task_id)
            if task is not None:
                task.position = base + index * 10
        db.commit()

    return _redirect_home(redirect_to)


@router.post("/tasks/{task_id}/done")
def mark_done(
    request: Request,
    task_id: int,
    project: str = Query("all"),
    redirect_to: str = Form(""),
):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is not None:
            task.status = STATUS_DONE
            task.completed_at = datetime.utcnow()
            db.commit()

    return _redirect_home(redirect_to)


@router.post("/tasks/{task_id}/reopen")
def reopen_task(
    request: Request,
    task_id: int,
    project: str = Query("all"),
    redirect_to: str = Form(""),
):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is not None:
            task.status = STATUS_TODO
            task.completed_at = None
            db.commit()

    return _redirect_home(redirect_to)


@router.post("/tasks/{task_id}/field")
def update_task_field(
    request: Request,
    task_id: int,
    project: str = Query("all"),
    field: str = Form(...),
    value: str = Form(""),
    redirect_to: str = Form(""),
):
    if field in EDITABLE_FIELDS:
        with SessionLocal() as db:
            task = db.get(Task, task_id)
            if task is not None:
                if field == "title":
                    value = value.strip()
                    if value:
                        task.title = value
                elif field == "priority":
                    task.priority = Priority(value)
                elif field == "status":
                    if value == STATUS_DONE and task.status != STATUS_DONE:
                        task.completed_at = datetime.utcnow()
                    elif value != STATUS_DONE:
                        task.completed_at = None
                    task.status = value
                elif field == "responsible":
                    value = value.strip()
                    task.responsible = value
                    _remember_responsible(db, value)
                elif field == "deadline":
                    task.deadline = date.fromisoformat(value) if value else None
                elif field == "project_id":
                    if value:
                        task.project_id = int(value)
                elif field == "comments":
                    task.comments = value.strip()

                db.commit()

    return _redirect_home(redirect_to)


@router.get("/tasks/{task_id}/edit")
def edit_task_form(
    request: Request,
    task_id: int,
    project: str = Query("all"),
    redirect_to: str = Query(""),
):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None:
            return templates.TemplateResponse(
                request, "partials/empty.html", {}
            )

        projects = (
            db.query(Project)
            .filter(Project.archived.is_(False))
            .order_by(Project.sort_order, Project.name)
            .all()
        )
        status_options = (
            db.query(StatusOption)
            .order_by(StatusOption.sort_order, StatusOption.id)
            .all()
        )
        responsible_options = db.query(ResponsibleOption).order_by(ResponsibleOption.name).all()

        checklist_items = (
            db.query(ChecklistItem)
            .filter(ChecklistItem.task_id == task_id)
            .order_by(ChecklistItem.sort_order, ChecklistItem.id)
            .all()
        )
        done_count = sum(1 for item in checklist_items if item.done)

        return templates.TemplateResponse(
            request,
            "partials/task_modal.html",
            {
                "task": task,
                "projects": projects,
                "statuses": status_options,
                "priorities": list(Priority),
                "priority_colors": {p.value: PRIORITY_COLORS[p] for p in Priority},
                "status_colors": {s.name: s.color for s in status_options},
                "responsible_options": responsible_options,
                "current_filter": project,
                "redirect_to": redirect_to,
                "items": checklist_items,
                "done_count": done_count,
                "total_count": len(checklist_items),
                "target_id": f"task-checklist-{task.id}",
                "embedded": True,
            },
        )


@router.post("/tasks/{task_id}")
def update_task(
    request: Request,
    task_id: int,
    project: str = Query("all"),
    title: str = Form(...),
    comments: str = Form(""),
    project_id: str = Form(""),
    priority: str = Form(...),
    status: str = Form(...),
    responsible: str = Form(""),
    deadline: str = Form(""),
    redirect_to: str = Form(""),
):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is not None:
            task.title = title.strip() or task.title
            task.comments = comments.strip()
            if project_id:
                task.project_id = int(project_id)
            task.priority = Priority(priority)
            responsible = responsible.strip()
            task.responsible = responsible
            _remember_responsible(db, responsible)
            task.deadline = date.fromisoformat(deadline) if deadline else None

            if status == STATUS_DONE and task.status != STATUS_DONE:
                task.completed_at = datetime.utcnow()
            elif status != STATUS_DONE:
                task.completed_at = None
            task.status = status

            db.commit()

    return _redirect_home(redirect_to)


@router.delete("/tasks/{task_id}")
def delete_task(
    request: Request,
    task_id: int,
    project: str = Query("all"),
    redirect_to: str = Form(""),
):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is not None:
            db.delete(task)
            db.commit()

    return _redirect_home(redirect_to)
