from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .routes import checklist, kanban, projects, reports, responsibles, statuses, tasks, views
from .seed import (
    ensure_backlog_status,
    ensure_comments_column,
    ensure_position_column,
    ensure_project_sort_order_column,
    migrate_orphan_tasks,
    migrate_status_values,
    remove_me_responsible_option,
    seed_demo_projects,
    seed_responsible_options,
    seed_status_options,
)

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    ensure_comments_column(db)
    ensure_position_column(db)
    ensure_project_sort_order_column(db)
    seed_demo_projects(db)
    migrate_orphan_tasks(db)
    migrate_status_values(db)
    seed_status_options(db)
    ensure_backlog_status(db)
    seed_responsible_options(db)
    remove_me_responsible_option(db)

app = FastAPI(title="TaskFlow")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(views.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(statuses.router)
app.include_router(responsibles.router)
app.include_router(reports.router)
app.include_router(kanban.router)
app.include_router(checklist.router)
