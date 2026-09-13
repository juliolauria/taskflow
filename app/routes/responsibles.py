from fastapi import APIRouter, Form, Request
from fastapi.templating import Jinja2Templates

from ..database import SessionLocal
from ..models import ResponsibleOption, Task

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _render_manage(request: Request, error: str = ""):
    with SessionLocal() as db:
        options = db.query(ResponsibleOption).order_by(ResponsibleOption.name).all()
        rows = []
        for opt in options:
            in_use = db.query(Task).filter(Task.responsible == opt.name).count()
            rows.append(
                {
                    "id": opt.id,
                    "name": opt.name,
                    "color": None,
                    "is_builtin": False,
                    "in_use": in_use,
                }
            )

    return templates.TemplateResponse(
        request,
        "partials/manage_options_modal.html",
        {
            "modal_title": "Manage responsible",
            "label_singular": "name",
            "options": rows,
            "show_color": False,
            "add_url": "/responsibles",
            "delete_url_prefix": "/responsibles",
            "error": error,
        },
    )


@router.get("/responsibles/manage")
def manage_responsibles(request: Request):
    return _render_manage(request)


@router.post("/responsibles")
def create_responsible(request: Request, name: str = Form(...)):
    name = name.strip()
    if name:
        with SessionLocal() as db:
            existing = db.query(ResponsibleOption).filter(ResponsibleOption.name == name).first()
            if existing is None:
                db.add(ResponsibleOption(name=name))
                db.commit()

    return _render_manage(request)


@router.delete("/responsibles/{option_id}")
def delete_responsible(request: Request, option_id: int):
    with SessionLocal() as db:
        option = db.get(ResponsibleOption, option_id)
        if option is None:
            return _render_manage(request)

        in_use = db.query(Task).filter(Task.responsible == option.name).count()
        if in_use:
            return _render_manage(
                request,
                error=f"“{option.name}” is used by {in_use} task(s) — reassign them first.",
            )

        db.delete(option)
        db.commit()

    return _render_manage(request)
