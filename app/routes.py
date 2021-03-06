from app import app, db
import os, secrets
from flask import request, redirect, url_for, render_template, send_from_directory, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Todo, TodoReaction, Notification
from datetime import datetime


@app.route('/')
@app.route('/index')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('todo'))
    return render_template('index.html')


@app.route('/avatars/<path:filename>')
def get_avatar(filename):
    return send_from_directory(app.config['AVATARS_SAVE_PATH'], filename)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form['username']
    password = request.form['password']

    if username == '' or password == '':
        return render_template('login.html', error='Please enter both a username and a password')

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return render_template('login.html', error='Invalid username or password')

    login_user(user)
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/sign-up', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'GET':
        return render_template('signUp.html')

    username = request.form['username']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    password = request.form['password']

    if username == '' or first_name == '' or last_name == '' or email == '' or password == '':
        return render_template('signUp.html', error='Missing required fields')

    existing_user = User.query.filter_by(username=username).first()
    if existing_user is not None:
        return render_template('signUp.html', error="Username is already in use")

    existing_user = User.query.filter_by(email=email).first()
    if existing_user is not None:
        return render_template('signUp.html', error="Email is already in use")

    user = User(username=username, first_name=first_name, last_name=last_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return redirect(url_for('index'))


@app.route('/todo', methods=['GET', 'POST'])
@login_required
def todo():
    if request.method == 'GET':
        return render_template('todo.html', todos=Todo.query.filter_by(completed=False).all(),
                               users=User.query.all())
    title = request.form['title']
    description = request.form['description']
    if title == '':
        return redirect(url_for('todo'))
    user = User.query.get(current_user.id)
    newTodo = Todo(title=title, description=description, user=user)
    db.session.add(newTodo)
    user.add_timeline(f"Created a new task <strong>{title}</strong>")
    db.session.commit()
    return redirect(url_for('todo'))


@app.route('/todo/<id>/complete')
@login_required
def complete_todo(id):
    todo = Todo.query.get(int(id))
    if todo is None:
        return redirect(url_for('todo'))
    todo.completed = True
    todo.completed_at = datetime.utcnow()
    current_user.add_timeline(f"Completed task <strong>{todo.title}</strong>")
    db.session.commit()
    return redirect(url_for('todo'))


@app.route('/todo/<id>/edit', methods=['POST'])
@login_required
def edit_todo(id):
    todo = Todo.query.get(int(id))
    if todo is None:
        return jsonify(result="error", message="todo not found")
    if "title" in request.form:
        title = request.form['title']
        todo.title = title
    if "description" in request.form:
        description = request.form['description']
        todo.description = description
    db.session.commit()
    return jsonify(result="success")


@app.route('/todo/<id>/like', methods=['GET'])
@login_required
def like_todo(id):
    todo = Todo.query.get(int(id))
    if todo is None:
        return redirect(url_for('todo'))
    if todo.has_liked(current_user):
        return redirect(url_for('todo'))
    db.session.add(TodoReaction(user_id=current_user.id, todo_id=todo.id))
    creator = User.query.get(todo.user_id)
    if creator != current_user:
        creator.add_notification(actor=current_user,
                                 body="{actor_username} liked your completed task <strong>" + todo.title + "</strong>")
    db.session.commit()
    return redirect(url_for('todo'))


@app.route('/todo/<id>/unlike', methods=['GET'])
@login_required
def unlike_todo(id):
    todo = Todo.query.get(int(id))
    if todo is None:
        return redirect(url_for('todo'))
    reaction = TodoReaction.query.filter_by(user_id=current_user.id, todo_id=todo.id).first()
    if reaction is None:
        return redirect(url_for('todo'))
    db.session.delete(reaction)
    db.session.commit()
    return redirect(url_for('todo'))


@app.route('/todo/<id>/delete', methods=['GET'])
@login_required
def delete_todo(id):
    todo = Todo.query.get(int(id))
    if todo.user_id != current_user.id:
        return redirect(url_for('todo'))
    current_user.add_timeline(f"Deleted task <strong>{todo.title}</strong>")
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for('todo'))


@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user, users=User.query.all())


@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'GET':
        return render_template('editProfile.html', users=User.query.all())
    bio = request.form['bio']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    username = request.form['username']

    existing_user = User.query.filter_by(username=username).first()
    if existing_user is not None and existing_user != current_user:
        return render_template('editProfile.html', error='That username is already in use', users=User.query.all())

    existing_user = User.query.filter_by(email=email).first()
    if existing_user is not None and existing_user != current_user:
        return render_template('editProfile.html', error='That email is already in use', users=User.query.all())

    avatar = request.files.get('avatar', None)
    if avatar:
        if not save_avatar(avatar):
            return render_template('editProfile.html', error='Please upload a valid image', users=User.query.all())

    current_user.bio = bio
    current_user.first_name = first_name
    current_user.last_name = last_name
    current_user.email = email
    current_user.username = username
    db.session.commit()

    return redirect(url_for('profile', username=current_user.username))


def save_avatar(file):
    random_hex = secrets.token_hex(10)
    _, file_ext = os.path.splitext(file.filename)
    if file_ext not in ['.jpeg', '.png', '.jpg']:
        return False
    picture_fn = random_hex + file_ext
    path = app.config['AVATARS_SAVE_PATH']
    file.save(os.path.join(path, picture_fn))
    current_user.avatar = url_for('get_avatar', filename=picture_fn)
    return True


@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user == current_user:
        return redirect(url_for('profile', username=username))
    current_user.follow(user)
    db.session.commit()
    return redirect(url_for('profile', username=username))


@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user == current_user:
        return redirect(url_for('profile', username=username))
    current_user.unfollow(user)
    db.session.commit()
    return redirect(url_for('profile', username=username))


@app.route('/read-notifications', methods=['POST'])
@login_required
def read_notifications():
    current_user.last_notification_read_time = datetime.utcnow()
    db.session.commit()
    return jsonify(result="success")


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
