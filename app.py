from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Project, Task, ProjectMember
from config import Config
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─── AUTH ROUTES ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role     = request.form.get('role', 'member')  # admin or member

        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('signup.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('signup.html')

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email, password=hashed, role=role)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─── DASHBOARD ──────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        projects = Project.query.filter_by(owner_id=current_user.id).all()
    else:
        memberships = ProjectMember.query.filter_by(user_id=current_user.id).all()
        project_ids = [m.project_id for m in memberships]
        projects = Project.query.filter(Project.id.in_(project_ids)).all()

    my_tasks = Task.query.filter_by(assigned_to=current_user.id).all()
    overdue  = [t for t in my_tasks if t.due_date and t.due_date < datetime.utcnow().date() and t.status != 'done']
    stats = {
        'total_projects': len(projects),
        'total_tasks': len(my_tasks),
        'overdue': len(overdue),
        'completed': len([t for t in my_tasks if t.status == 'done']),
    }
    return render_template('dashboard.html', projects=projects, my_tasks=my_tasks,
                           overdue_tasks=overdue, stats=stats)


# ─── PROJECT ROUTES ─────────────────────────────────────────────────────────

@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if current_user.role != 'admin':
        flash('Only admins can create projects.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip()
        if not name:
            flash('Project name is required.', 'danger')
            return render_template('project_form.html', action='Create', project=None)
        project = Project(name=name, description=desc, owner_id=current_user.id)
        db.session.add(project)
        db.session.commit()
        flash('Project created!', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    return render_template('project_form.html', action='Create', project=None)


@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    _check_project_access(project)
    tasks   = Task.query.filter_by(project_id=project_id).all()
    members = db.session.query(User).join(ProjectMember,
              User.id == ProjectMember.user_id).filter(
              ProjectMember.project_id == project_id).all()
    all_users = User.query.all() if current_user.role == 'admin' else []
    return render_template('project_detail.html', project=project,
                           tasks=tasks, members=members, all_users=all_users)


@app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        project.name        = request.form.get('name', '').strip()
        project.description = request.form.get('description', '').strip()
        db.session.commit()
        flash('Project updated.', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    return render_template('project_form.html', action='Edit', project=project)


@app.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/projects/<int:project_id>/add_member', methods=['POST'])
@login_required
def add_member(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    user_id = request.form.get('user_id')
    if user_id:
        exists = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
        if not exists:
            db.session.add(ProjectMember(project_id=project_id, user_id=user_id))
            db.session.commit()
            flash('Member added.', 'success')
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/projects/<int:project_id>/remove_member/<int:user_id>', methods=['POST'])
@login_required
def remove_member(project_id, user_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('project_detail', project_id=project_id))
    pm = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if pm:
        db.session.delete(pm)
        db.session.commit()
        flash('Member removed.', 'success')
    return redirect(url_for('project_detail', project_id=project_id))


# ─── TASK ROUTES ────────────────────────────────────────────────────────────

@app.route('/projects/<int:project_id>/tasks/new', methods=['GET', 'POST'])
@login_required
def new_task(project_id):
    project = Project.query.get_or_404(project_id)
    _check_project_access(project)
    members = db.session.query(User).join(ProjectMember,
              User.id == ProjectMember.user_id).filter(
              ProjectMember.project_id == project_id).all()
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        assigned_to = request.form.get('assigned_to') or None
        due_date    = request.form.get('due_date') or None
        priority    = request.form.get('priority', 'medium')
        if not title:
            flash('Task title is required.', 'danger')
            return render_template('task_form.html', action='Create', task=None,
                                   project=project, members=members)
        if due_date:
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        task = Task(title=title, description=description, project_id=project_id,
                    assigned_to=assigned_to, due_date=due_date,
                    priority=priority, status='todo', created_by=current_user.id)
        db.session.add(task)
        db.session.commit()
        flash('Task created!', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    return render_template('task_form.html', action='Create', task=None,
                           project=project, members=members)


@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task    = Task.query.get_or_404(task_id)
    project = task.project
    _check_project_access(project)
    members = db.session.query(User).join(ProjectMember,
              User.id == ProjectMember.user_id).filter(
              ProjectMember.project_id == project.id).all()
    if request.method == 'POST':
        task.title       = request.form.get('title', '').strip()
        task.description = request.form.get('description', '').strip()
        task.assigned_to = request.form.get('assigned_to') or None
        task.priority    = request.form.get('priority', 'medium')
        task.status      = request.form.get('status', 'todo')
        due_date         = request.form.get('due_date') or None
        task.due_date    = datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None
        db.session.commit()
        flash('Task updated.', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    return render_template('task_form.html', action='Edit', task=task,
                           project=project, members=members)


@app.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    task   = Task.query.get_or_404(task_id)
    status = request.form.get('status')
    if status in ('todo', 'in_progress', 'done'):
        task.status = status
        db.session.commit()
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    project_id = task.project_id
    _check_project_access(task.project)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('project_detail', project_id=project_id))


# ─── API ENDPOINTS ──────────────────────────────────────────────────────────

@app.route('/api/tasks/<int:task_id>/status', methods=['PATCH'])
@login_required
def api_update_status(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    status = data.get('status')
    if status in ('todo', 'in_progress', 'done'):
        task.status = status
        db.session.commit()
        return jsonify({'success': True, 'status': task.status})
    return jsonify({'error': 'Invalid status'}), 400


# ─── HELPERS ────────────────────────────────────────────────────────────────

def _check_project_access(project):
    if current_user.role == 'admin' and project.owner_id == current_user.id:
        return
    membership = ProjectMember.query.filter_by(
        project_id=project.id, user_id=current_user.id).first()
    if not membership:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
