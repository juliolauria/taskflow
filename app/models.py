import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Priority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


# Status used to be a fixed enum; it's now a user-manageable list backed by
# StatusOption, so these are just the names/colors seeded on first run and
# used internally wherever code needs to refer to a specific built-in status.
STATUS_BACKLOG = "Backlog"
STATUS_TODO = "To Do"
STATUS_DOING = "Doing"
STATUS_FOLLOW_UP = "Follow-Up"
STATUS_ON_HOLD = "On Hold"
STATUS_DONE = "Done"

BUILTIN_STATUSES = [
    (STATUS_BACKLOG, "#64748b"),
    (STATUS_TODO, "#a1a1aa"),
    (STATUS_DOING, "#eab308"),
    (STATUS_FOLLOW_UP, "#f97316"),
    (STATUS_ON_HOLD, "#71717a"),
    (STATUS_DONE, "#22c55e"),
]


# Lower number = higher importance. Used only as the initial backfill order
# for Task.position — actual ordering is now user-controlled via drag/drop.
PRIORITY_RANK = {
    Priority.URGENT: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}

# Each priority keeps its own fixed color everywhere it's rendered (badges,
# and every individual <option> in a priority <select> so the open dropdown
# doesn't repaint every option to match whichever one is selected).
PRIORITY_COLORS = {
    Priority.LOW: "#94a3b8",
    Priority.MEDIUM: "#60a5fa",
    Priority.HIGH: "#fb923c",
    Priority.URGENT: "#f87171",
}


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    color = Column(String, nullable=True)
    archived = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)

    tasks = relationship("Task", back_populates="project")
    tags = relationship("Tag", back_populates="project", cascade="all, delete-orphan")


class StatusOption(Base):
    __tablename__ = "status_options"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    color = Column(String, nullable=False, default="#9aa0a6")
    is_builtin = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)


class ResponsibleOption(Base):
    __tablename__ = "responsible_options"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    done = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    title = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    comments = Column(Text, nullable=False, default="")
    priority = Column(SAEnum(Priority), nullable=False, default=Priority.MEDIUM)
    status = Column(String, nullable=False, default=STATUS_TODO)
    responsible = Column(String, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deadline = Column(Date, nullable=True)
    last_pinged_at = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    position = Column(Integer, nullable=False, default=0)

    project = relationship("Project", back_populates="tasks")
    tags = relationship("Tag", secondary="task_tags", back_populates="tasks")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_tag_project_name"),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)

    project = relationship("Project", back_populates="tags")
    tasks = relationship("Task", secondary="task_tags", back_populates="tags")


class TaskTag(Base):
    __tablename__ = "task_tags"

    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)
