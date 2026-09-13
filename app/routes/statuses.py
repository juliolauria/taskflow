from fastapi import APIRouter, Form, Request
from fastapi.templating import Jinja2Templates

from ..database import SessionLocal
from ..models import StatusOption, Task

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _render_manage(request: Request, error: str = ""):
    with SessionLocal() as db:
        options = (
            db.query(StatusOption).order_by(StatusOption.sort_order, StatusOption.id).all()
        )
        rows = []
        for opt in options:
            in_use = db.query(Task).filter(Task.status == opt.name).count()
            rows.append(
                {
                    "id": opt.id,
                    "name": opt.name,
                    "color": opt.color,
                    "is_builtin": opt.is_builtin,
                    "in_use": in_use,
                }
            )

    return templates.TemplateResponse(
        request,
        "partials/manage_options_modal.html",
        {
            "modal_title": "Manage statuses",
            "label_singular": "status",
            "options": rows,
            "show_color": True,
            "add_url": "/statuses",
            "delete_url_prefix": "/statuses",
            "error": error,
        },
    )


@router.get("/statuses/manage")
def manage_statuses(request: Request):
    return _render_manage(request)


@router.post("/statuses")
def create_status(request: Request, name: str = Form(...), color: str = Form("#4f8cff")):
    name = name.strip()
    if name:
        with SessionLocal() as db:
            existing = db.query(StatusOption).filter(StatusOption.name == name).first()
            if existing is None:
                next_order = db.query(StatusOption).count()
                db.add(
                    StatusOption(
                        name=name, color=color, is_builtin=False, sort_order=next_order
                    )
                )
                db.commit()

    return _render_manage(request)


@router.delete("/statuses/{status_id}")
def delete_status(request: Request, status_id: int):
    with SessionLocal() as db:
        option = db.get(StatusOption, status_id)
        if option is None:
            return _render_manage(request)

        if option.is_builtin:
            return _render_manage(
                request, error=f"“{option.name}” is a built-in status and can't be removed."
            )

        in_use = db.query(Task).filter(Task.status == option.name).count()
        if in_use:
            return _render_manage(
                request,
                error=f"“{option.name}” is used by {in_use} task(s) — reassign them first.",
            )

        db.delete(option)
        db.commit()

    return _render_manage(request)
