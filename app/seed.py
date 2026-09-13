from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models


def seed_demo_projects(db: Session) -> None:
    """Add a couple of sample projects on first run so the Active view has
    something to group by before project management (step 4) exists."""
    if db.query(models.Project).count() > 0:
        return

    demo_projects = [
        models.Project(name="Digital Tomato", color="#3b82f6"),
        models.Project(name="FACTS/PMH", color="#22c55e"),
    ]
    db.add_all(demo_projects)
    db.commit()


def migrate_orphan_tasks(db: Session) -> None:
    """Every task must belong to a project now (Inbox was removed). Any
    pre-existing task with no project gets moved into a fallback "Unsorted"
    project instead of being silently dropped or blocked from loading."""
    orphans = db.query(models.Task).filter(models.Task.project_id.is_(None)).all()
    if not orphans:
        return

    fallback = (
        db.query(models.Project).filter(models.Project.name == "Unsorted").first()
    )
    if fallback is None:
        fallback = models.Project(name="Unsorted", color="#9aa0a6")
        db.add(fallback)
        db.flush()

    for task in orphans:
        task.project_id = fallback.id

    db.commit()
    print(f"[migrate_orphan_tasks] moved {len(orphans)} task(s) into 'Unsorted' project")


# Task.status used to be a SQLAlchemy Enum(Status) column, which stores the
# enum MEMBER NAME in the database (e.g. "TODO", "FOLLOW_UP"), not its
# display value ("To Do", "Follow-Up"). Status is now a plain string column
# so it can hold arbitrary user-added values, so any row still holding one
# of the old enum-name strings needs to be normalized to its display form —
# otherwise those tasks would silently stop matching any StatusOption.
STATUS_NAME_MIGRATION = {
    "TODO": models.STATUS_TODO,
    "DOING": models.STATUS_DOING,
    "FOLLOW_UP": models.STATUS_FOLLOW_UP,
    "ON_HOLD": models.STATUS_ON_HOLD,
    "DONE": models.STATUS_DONE,
}


def migrate_status_values(db: Session) -> None:
    changed = 0
    for old_name, new_name in STATUS_NAME_MIGRATION.items():
        tasks = db.query(models.Task).filter(models.Task.status == old_name).all()
        for task in tasks:
            task.status = new_name
            changed += 1
    if changed:
        db.commit()
        print(f"[migrate_status_values] normalized {changed} task(s) status value(s)")


def seed_status_options(db: Session) -> None:
    if db.query(models.StatusOption).count() > 0:
        return
    for order, (name, color) in enumerate(models.BUILTIN_STATUSES):
        db.add(
            models.StatusOption(
                name=name, color=color, is_builtin=True, sort_order=order
            )
        )
    db.commit()


def ensure_backlog_status(db: Session) -> None:
    """"Backlog" was added to the built-in status set after status_options
    had already been seeded on existing installs, so seed_status_options'
    "only seed if empty" guard would never add it retroactively. Add it
    directly (ordered before To Do) if it isn't already there."""
    existing = (
        db.query(models.StatusOption)
        .filter(models.StatusOption.name == models.STATUS_BACKLOG)
        .first()
    )
    if existing is not None:
        return

    lowest = (
        db.query(models.StatusOption).order_by(models.StatusOption.sort_order).first()
    )
    order = (lowest.sort_order - 1) if lowest else 0
    db.add(
        models.StatusOption(
            name=models.STATUS_BACKLOG, color="#64748b", is_builtin=True, sort_order=order
        )
    )
    db.commit()


def ensure_comments_column(db: Session) -> None:
    """`comments` is a new Task column. Base.metadata.create_all() only
    creates missing TABLES, not missing COLUMNS on an existing table, so an
    already-initialized tasks table needs an explicit, additive
    ALTER TABLE. SQLite fills the DEFAULT into every existing row —
    no existing data is touched or lost."""
    columns = {row[1] for row in db.execute(text("PRAGMA table_info(tasks)")).fetchall()}
    if "comments" in columns:
        return
    db.execute(text("ALTER TABLE tasks ADD COLUMN comments TEXT NOT NULL DEFAULT ''"))
    db.commit()
    print("[ensure_comments_column] added 'comments' column to tasks table")


def ensure_project_sort_order_column(db: Session) -> None:
    """`sort_order` is a new Project column driving manual drag-to-reorder
    in the sidebar. Additive ALTER TABLE, same reasoning as the Task columns
    above. Backfills using the current alphabetical order so the sidebar
    doesn't visually reshuffle the first time this runs."""
    columns = {row[1] for row in db.execute(text("PRAGMA table_info(projects)")).fetchall()}
    if "sort_order" in columns:
        return
    db.execute(text("ALTER TABLE projects ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"))
    db.commit()

    projects = db.query(models.Project).order_by(models.Project.name).all()
    for index, project in enumerate(projects):
        project.sort_order = index * 10
    db.commit()
    print(f"[ensure_project_sort_order_column] added 'sort_order' and backfilled {len(projects)} project(s)")


def seed_responsible_options(db: Session) -> None:
    """Keep the reusable Responsible list in sync with whatever names are
    actually in use on tasks (covers pre-existing data, e.g. "Me")."""
    existing_names = {r.name for r in db.query(models.ResponsibleOption).all()}
    used_names = {
        r
        for (r,) in db.query(models.Task.responsible)
        .filter(models.Task.responsible != "")
        .distinct()
        .all()
    }
    new_names = used_names - existing_names
    for name in new_names:
        db.add(models.ResponsibleOption(name=name))
    if new_names:
        db.commit()


def remove_me_responsible_option(db: Session) -> None:
    """The user asked for "Me" gone from the reusable Responsible list.
    Existing tasks that still have responsible="Me" keep that value
    untouched (their data isn't altered) — this only removes it from the
    add/select list. Must run AFTER seed_responsible_options, since that
    function would otherwise re-add "Me" every startup (it's still in use
    on old tasks)."""
    option = (
        db.query(models.ResponsibleOption).filter(models.ResponsibleOption.name == "Me").first()
    )
    if option is not None:
        db.delete(option)
        db.commit()


def ensure_position_column(db: Session) -> None:
    """`position` is a new Task column driving manual drag-to-reorder.
    Additive ALTER TABLE, same reasoning as ensure_comments_column — no
    existing data touched. Backfills using the prior implicit sort order
    (priority, then deadline) so nothing visually jumps around the first
    time this runs."""
    columns = {row[1] for row in db.execute(text("PRAGMA table_info(tasks)")).fetchall()}
    if "position" in columns:
        return
    db.execute(text("ALTER TABLE tasks ADD COLUMN position INTEGER NOT NULL DEFAULT 0"))
    db.commit()

    from datetime import date

    tasks = db.query(models.Task).all()

    def _sort_key(task):
        return (
            models.PRIORITY_RANK[task.priority],
            task.deadline is None,
            task.deadline or date.max,
        )

    for index, task in enumerate(sorted(tasks, key=_sort_key)):
        task.position = index * 10
    db.commit()
    print(f"[ensure_position_column] added 'position' column and backfilled {len(tasks)} task(s)")
