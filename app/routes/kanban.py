from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.templating import Jinja2Templates

from ..database import SessionLocal
from ..models import PRIORITY_RANK, Priority, Project, StatusOption, Task

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _sort_key(task: Task):
    return (
        PRIORITY_RANK[task.priority],
        task.deadline is None,
        task.deadline or date.max,
    )


def _filter_label(
    value_to_label: dict[str, str], selected: list[str], all_label: str
) -> str:
    if not selected or len(selected) >= len(value_to_label):
        return all_label
    if len(selected) == 1:
        return value_to_label.get(selected[0], selected[0])
    return f"{len(selected)} selected"


@router.get("/kanban")
def kanban_view(
    request: Request,
    projects: list[str] = Query(default=[]),
    priorities: list[str] = Query(default=[]),
):
    with SessionLocal() as db:
        all_projects = (
            db.query(Project).filter(Project.archived.is_(False)).order_by(Project.sort_order, Project.name).all()
        )
        status_options = (
            db.query(StatusOption).order_by(StatusOption.sort_order, StatusOption.id).all()
        )

        query = db.query(Task)
        if projects:
            query = query.filter(Task.project_id.in_([int(p) for p in projects]))
        if priorities:
            query = query.filter(Task.priority.in_([Priority(p) for p in priorities]))

        tasks = query.all()

        columns = []
        for status in status_options:
            column_tasks = sorted(
                (t for t in tasks if t.status == status.name), key=_sort_key
            )
            columns.append({"status": status, "tasks": column_tasks})

        context = {
            "columns": columns,
            "projects": all_projects,
            "project_names": {p.id: p.name for p in all_projects},
            "project_colors": {p.id: (p.color or "#888888") for p in all_projects},
            "project_filter_options": [(str(p.id), p.name) for p in all_projects],
            "priority_filter_options": [(p.value, p.value) for p in Priority],
            "selected_projects": projects,
            "selected_priorities": priorities,
            "project_filter_label": _filter_label(
                {str(p.id): p.name for p in all_projects}, projects, "All Projects"
            ),
            "priority_filter_label": _filter_label(
                {p.value: p.value for p in Priority}, priorities, "All Priorities"
            ),
            "current_filter": "kanban",
        }
        return templates.TemplateResponse(request, "kanban.html", context)
