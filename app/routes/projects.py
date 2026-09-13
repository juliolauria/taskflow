from fastapi import APIRouter, Form, Request
from fastapi.templating import Jinja2Templates

from ..database import SessionLocal
from ..models import Project

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

PALETTE = ["#4f8cff", "#22c55e", "#f97316", "#a855f7", "#ec4899", "#14b8a6", "#eab308"]


def _render_sidebar(request: Request, current_filter: str):
    with SessionLocal() as db:
        projects = (
            db.query(Project)
            .filter(Project.archived.is_(False))
            .order_by(Project.sort_order, Project.name)
            .all()
        )
        return templates.TemplateResponse(
            request,
            "partials/sidebar.html",
            {"projects": projects, "current_filter": current_filter},
        )


@router.post("/projects")
def create_project(
    request: Request,
    name: str = Form(...),
    color: str = Form(""),
    current_filter: str = Form("all"),
):
    name = name.strip()

    if name:
        with SessionLocal() as db:
            existing = db.query(Project).filter(Project.name == name).first()
            if existing is None:
                count = db.query(Project).count()
                db.add(
                    Project(name=name, color=color or PALETTE[count % len(PALETTE)])
                )
                db.commit()

    return _render_sidebar(request, current_filter)


@router.post("/projects/{project_id}/rename")
def rename_project(
    request: Request,
    project_id: int,
    name: str = Form(...),
    current_filter: str = Form("all"),
):
    name = name.strip()

    with SessionLocal() as db:
        project = db.get(Project, project_id)

        if project is not None and name:
            clash = (
                db.query(Project)
                .filter(Project.name == name, Project.id != project_id)
                .first()
            )
            if clash is None:
                project.name = name
                db.commit()

        projects = (
            db.query(Project)
            .filter(Project.archived.is_(False))
            .order_by(Project.sort_order, Project.name)
            .all()
        )

        return templates.TemplateResponse(
            request,
            "partials/page_title_rename_result.html",
            {
                "project": project,
                "current_filter": current_filter,
                "projects": projects,
            },
        )


@router.post("/projects/reorder")
def reorder_projects(
    request: Request,
    order: str = Form(...),
    current_filter: str = Form("all"),
):
    ids = [int(i) for i in order.split(",") if i]

    with SessionLocal() as db:
        projects = db.query(Project).filter(Project.id.in_(ids)).all()
        projects_by_id = {p.id: p for p in projects}
        for index, project_id in enumerate(ids):
            project = projects_by_id.get(project_id)
            if project is not None:
                project.sort_order = index * 10
        db.commit()

    return _render_sidebar(request, current_filter)


@router.post("/projects/{project_id}/color")
def update_project_color(
    request: Request,
    project_id: int,
    color: str = Form(...),
    current_filter: str = Form("all"),
):
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is not None:
            project.color = color
            db.commit()

    return _render_sidebar(request, current_filter)
