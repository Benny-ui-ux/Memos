from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from dotenv import load_dotenv
import sqlite3
from datetime import timedelta
import os

app = Flask(__name__)
load_dotenv() 
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
app.permanent_session_lifetime = timedelta(minutes=30)
app.config['SESSION_COOKIE_PATH'] = '/'

USERNAME = os.getenv('FLASK_LOGIN_USER')
PASSWORD = os.getenv('FLASK_LOGIN_PASSWORD')
DATABASE = 'memos.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute(''' 
        CREATE TABLE IF NOT EXISTS memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memo TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );''')

        db.execute('''CREATE TABLE IF NOT EXISTS completed_memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memo TEXT NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );''')

        db.execute('''CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );''')

        db.execute('''CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );''')

        db.commit()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USERNAME and password == PASSWORD:
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))


@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    

    conn = get_db()
    memos = conn.execute('SELECT * FROM memos').fetchall()

    return render_template('index.html', memos=memos)

@app.route('/submit', methods=['POST'])
def submit():
    try:
        memo = request.form.get('memo')

        conn = get_db()
        conn.execute('INSERT INTO memos (memo) VALUES (?)', (memo,))
        conn.commit()
        flash('Your memo was submitted successfully!', 'success')
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')

    return redirect(url_for('index'))


@app.route('/delete_memo/<int:memo_id>', methods=['POST'])
def delete_memo(memo_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        db = get_db()
        db.execute('DELETE FROM memos WHERE id = ?', (memo_id,))
        db.commit()
        flash('Memo deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting memo: {str(e)}', 'danger')
    return redirect(url_for('index'))


@app.route('/mark_complete/<int:memo_id>', methods=['POST'])
def mark_complete(memo_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        db = get_db()
        memo = db.execute('SELECT memo FROM memos WHERE id = ?', (memo_id,)).fetchone()

        if memo:
            db.execute('INSERT INTO completed_memos (memo) VALUES (?)', (memo[0],))
            db.execute('DELETE FROM memos WHERE id = ?', (memo_id,))
            db.commit()
            flash('Memo marked as complete.', 'success')
        else:
            flash('Memo not found.', 'danger')
    except Exception as e:
        flash(f'Error marking memo as complete: {str(e)}', 'danger')
    return redirect(url_for('index'))


@app.route('/completed_memos')
def completed_jobs():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    completed_memos = db.execute('SELECT * FROM completed_memos').fetchall()
    return render_template('completed_memos.html', completed_memos=completed_memos)

@app.route('/notes')
def notes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    

    conn = get_db()
    notes = conn.execute('SELECT * FROM notes').fetchall()

    return render_template('notes.html', notes=notes)

@app.route('/submit_note', methods=['POST'])
def submit_note():
    try:
        note = request.form.get('note')

        conn = get_db()
        conn.execute('INSERT INTO notes (note) VALUES (?)', (note,))
        conn.commit()
        flash('Your memo was submitted successfully!', 'success')
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')

    return redirect(url_for('notes'))

@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        db = get_db()
        db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        db.commit()
        flash('Note deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting Note: {str(e)}', 'danger')
    return redirect(url_for('notes'))

@app.route('/journal')
def journal():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    

    conn = get_db()
    entry = conn.execute('SELECT * FROM journal').fetchall()

    return render_template('journal.html', journal=entry)

@app.route('/submit_journal', methods=['POST'])
def submit_journal():
    try:
        entry = request.form.get('entry')

        conn = get_db()
        conn.execute('INSERT INTO journal (entry) VALUES (?)', (entry,))
        conn.commit()
        flash('Your journal was submitted successfully!', 'success')
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')

    return redirect(url_for('journal'))

@app.route('/delete_journal/<int:entry_id>', methods=['POST'])
def delete_journal(entry_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        db = get_db()
        db.execute('DELETE FROM journal WHERE id = ?', (entry_id,))
        db.commit()
        flash('Journal deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting Journal: {str(e)}', 'danger')
    return redirect(url_for('journal'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

