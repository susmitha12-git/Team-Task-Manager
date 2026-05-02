from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)
    role       = db.Column(db.Enum('admin', 'member'), default='member', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    owned_projects = db.relationship('Project', backref='owner', lazy=True,
                                     cascade='all, delete-orphan')
    memberships    = db.relationship('ProjectMember', backref='user', lazy=True,
                                     cascade='all, delete-orphan')
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to',
                                     backref='assignee', lazy=True)
    created_tasks  = db.relationship('Task', foreign_keys='Task.created_by',
                                     backref='creator', lazy=True)

    def __repr__(self):
        return f'<User {self.email} [{self.role}]>'


class Project(db.Model):
    __tablename__ = 'projects'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    owner_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tasks   = db.relationship('Task', backref='project', lazy=True,
                              cascade='all, delete-orphan')
    members = db.relationship('ProjectMember', backref='project', lazy=True,
                              cascade='all, delete-orphan')

    @property
    def task_count(self):
        return len(self.tasks)

    @property
    def done_count(self):
        return sum(1 for t in self.tasks if t.status == 'done')

    @property
    def progress(self):
        if not self.tasks:
            return 0
        return int((self.done_count / len(self.tasks)) * 100)

    def __repr__(self):
        return f'<Project {self.name}>'


class ProjectMember(db.Model):
    __tablename__ = 'project_members'

    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('project_id', 'user_id', name='uq_project_member'),)

    def __repr__(self):
        return f'<ProjectMember project={self.project_id} user={self.user_id}>'


class Task(db.Model):
    __tablename__ = 'tasks'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_id  = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status      = db.Column(db.Enum('todo', 'in_progress', 'done'), default='todo', nullable=False)
    priority    = db.Column(db.Enum('low', 'medium', 'high'), default='medium', nullable=False)
    due_date    = db.Column(db.Date, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_overdue(self):
        from datetime import date
        return self.due_date and self.due_date < date.today() and self.status != 'done'

    @property
    def priority_class(self):
        return {'low': 'success', 'medium': 'warning', 'high': 'danger'}.get(self.priority, 'secondary')

    @property
    def status_label(self):
        return {'todo': 'To Do', 'in_progress': 'In Progress', 'done': 'Done'}.get(self.status, self.status)

    def __repr__(self):
        return f'<Task {self.title} [{self.status}]>'
