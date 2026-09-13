from fastapi import APIRouter, Form, Query, Request
from fastapi.templating import Jinja2Templates

from ..database import SessionLocal
from ..models import ChecklistItem, Task

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _render_checklist(request: Request, task_id: int, project: str):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None:
            return templates.TemplateResponse(request, "partials/empty.html", {})

        items = (
            db.query(ChecklistItem)
            .filter(ChecklistItem.task_id == task_id)
            .order_by(ChecklistItem.sort_order, ChecklistItem.id)
            .all()
        )
        done_count = sum(1 for item in items if item.done)

        return templates.TemplateResponse(
            request,
            "partials/checklist_modal.html",
            {
                "task": task,
                "items": items,
                "done_count": done_count,
                "total_count": len(items),
                "current_filter": project,
            },
        )


@router.get("/tasks/{task_id}/checklist")
def get_checklist(request: Request, task_id: int, project: str = Query("all")):
    return _render_checklist(request, task_id, project)


@router.post("/tasks/{task_id}/checklist")
def add_checklist_item(
    request: Request,
    task_id: int,
    title: str = Form(...),
    project: str = Query("all"),
):
    title = title.strip()
    if title:
        with SessionLocal() as db:
            if db.get(Task, task_id) is not None:
                count = db.query(ChecklistItem).filter(ChecklistItem.task_id == task_id).count()
                db.add(ChecklistItem(task_id=task_id, title=title, sort_order=count))
                db.commit()

    return _render_checklist(request, task_id, project)


@router.post("/tasks/{task_id}/checklist/reorder")
def reorder_checklist(
    request: Request,
    task_id: int,
    order: str = Form(...),
    project: str = Query("all"),
):
    ids = [int(i) for i in order.split(",") if i]

    with SessionLocal() as db:
        items = (
            db.query(ChecklistItem)
            .filter(ChecklistItem.id.in_(ids), ChecklistItem.task_id == task_id)
            .all()
        )
        items_by_id = {item.id: item for item in items}
        for index, item_id in enumerate(ids):
            item = items_by_id.get(item_id)
            if item is not None:
                item.sort_order = index
        db.commit()

    return _render_checklist(request, task_id, project)


@router.post("/checklist/{item_id}/toggle")
def toggle_checklist_item(request: Request, item_id: int, project: str = Query("all")):
    task_id = None
    with SessionLocal() as db:
        item = db.get(ChecklistItem, item_id)
        if item is not None:
            item.done = not item.done
            task_id = item.task_id
            db.commit()

    if task_id is None:
        return templates.TemplateResponse(request, "partials/empty.html", {})
    return _render_checklist(request, task_id, project)


@router.delete("/checklist/{item_id}")
def delete_checklist_item(request: Request, item_id: int, project: str = Query("all")):
    task_id = None
    with SessionLocal() as db:
        item = db.get(ChecklistItem, item_id)
        if item is not None:
            task_id = item.task_id
            db.delete(item)
            db.commit()

    if task_id is None:
        return templates.TemplateResponse(request, "partials/empty.html", {})
    return _render_checklist(request, task_id, project)
