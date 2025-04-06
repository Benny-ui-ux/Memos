from flask import Flask, render_template, request, redirect, url_for, session, flash 
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
import requests
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
import pymysql.cursors
from slugify import slugify
import logging

app = Flask(__name__)
load_dotenv()  # Ensure environment variables are loaded
app.secret_key = os.getenv('FLASK_SECRET_KEY')
app.config['SESSION_COOKIE_PATH'] = '/'

USERNAME = os.getenv('FLASK_LOGIN_USER')
PASSWORD = os.getenv('FLASK_LOGIN_PASSWORD')
PUSHOVER_USER = os.getenv('PUSHOVER_USER_KEY')
PUSHOVER_TOKEN = os.getenv('PUSHOVER_APP_TOKEN')


DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

MAX_REMINDERS = 7


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/www/memos/memos.log", mode='a'),  # Adjust path as needed
    ]
)
logger = logging.getLogger(__name__)


class Memo(db.Model):
    __tablename__ = "memos"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    memo = db.Column(db.Text, nullable=False)
    reminder_time = db.Column(db.DateTime, nullable=True)
    reminder_sent_count = db.Column(db.Integer, default=0)
    last_reminded_at = db.Column(db.DateTime, nullable=True)

class CompletedMemo(db.Model):
    __tablename__ = "completed_memos"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    memo = db.Column(db.Text, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, unique=True)  # Note title
    slug = db.Column(db.String(255), nullable=False, unique=True)  # URL-friendly identifier
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_unique_slug(name):
        base_slug = slugify(name)
        slug = base_slug
        count = 1

        while Note.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1

        return slug

class Journal(db.Model):
    __tablename__ = "journal"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, unique=True)  # Note title
    slug = db.Column(db.String(255), nullable=False, unique=True)  # URL-friendly identifier
    entry = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_unique_slug(name):
        base_slug = slugify(name)
        slug = base_slug
        count = 1

        while Journal.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1

        return slug

def init_db():
    with app.app_context():
        db.create_all() 


def send_pushover_notification_threaded(memo_text, reminder_count):
    """Send a notification via Pushover in a separate thread."""
    message = f"Reminder ({reminder_count + 1}/{MAX_REMINDERS}): {memo_text}"
    data = {"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": message}
    requests.post("https://api.pushover.net/1/messages.json", data=data)


def check_and_send_reminders():
    """Send reminders at precise intervals for each memo independently."""
    with app.app_context():
        now = datetime.utcnow()
        logger.info(f"Checking reminders at {now}")
        time_threshold = now - timedelta(hours=24)

        # Use two separate queries for clarity
        # For initial reminders - strict time comparison
        initial_reminders = Memo.query.filter(
            db.and_(
                Memo.reminder_time <= now,  # Time has passed or is now
                Memo.reminder_sent_count == 0  # Never sent
            )
        ).all()

        # For follow-up reminders - check 24-hour threshold
        followup_reminders = Memo.query.filter(
            db.and_(
                Memo.reminder_sent_count > 0,  # At least one reminder sent
                Memo.reminder_sent_count < MAX_REMINDERS,  # Not reached max
                Memo.last_reminded_at <= time_threshold  # 24 hours passed
            )
        ).all()

        # Log information about eligible reminders
        for memo in initial_reminders:
            logger.info(f"Initial reminder eligible: ID={memo.id}, time={memo.reminder_time}, current_time={now}")

        reminders = initial_reminders + followup_reminders
        logger.info(f"Found {len(initial_reminders)} initial and {len(followup_reminders)} followup reminders")

        if not reminders:
            logger.info("No reminders to send")
            return

        # Process the reminders
        tasks = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            for memo in reminders:
                logger.info(f"Processing reminder #{memo.reminder_sent_count + 1} for memo ID {memo.id}")

                future = executor.submit(
                    send_pushover_notification_threaded,
                    memo.memo,
                    memo.reminder_sent_count
                )
                tasks.append((future, memo))

            for future, memo in tasks:
                try:
                    future.result()
                    memo.reminder_sent_count += 1
                    memo.last_reminded_at = now
                    logger.info(f"Sent reminder for memo ID {memo.id}")
                except Exception as e:
                    logger.error(f"Failed to send reminder for memo ID {memo.id}: {str(e)}")

        try:
            db.session.commit()
            logger.info(f"Updated {len(reminders)} reminder records")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating reminder records: {str(e)}")

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

    memos = Memo.query.order_by(Memo.reminder_time.asc()).all()
    return render_template('index.html', memos=memos)


@app.route('/submit', methods=['POST'])
def submit():
    try:
        memo = request.form.get('memo')
        reminder_time_str = request.form.get('reminder_time')

        if reminder_time_str:
            # Convert string to datetime and explicitly make it UTC
            local_time = datetime.strptime(reminder_time_str, "%Y-%m-%dT%H:%M")
            # Convert to UTC if the input is in local time
            # This assumes your form input is in your local timezone
            # You'll need to adjust the offset based on your timezone
            utc_offset = timedelta(hours=5)  # Adjust this based on your timezone difference from UTC
            reminder_time = local_time + utc_offset
            
            logger.info(f"Setting reminder for local time: {local_time}, UTC time: {reminder_time}")
        else:
            reminder_time = None

        new_memo = Memo(memo=memo, reminder_time=reminder_time)
        db.session.add(new_memo)
        db.session.commit()
        
        logger.info(f"Saved memo ID {new_memo.id} with reminder time (UTC): {new_memo.reminder_time}")

        flash('Your memo was submitted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error submitting memo: {str(e)}")
        flash(f'Something went wrong: {str(e)}', 'danger')

    return redirect(url_for('index'))


@app.route('/delete_memo/<int:memo_id>', methods=['POST'])
def delete_memo(memo_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        memo = Memo.query.get(memo_id)
        if memo:
            db.session.delete(memo)
            db.session.commit()
            flash('Memo deleted successfully!', 'success')
        else:
            flash('Memo not found.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting memo: {str(e)}', 'danger')

    return redirect(url_for('index'))


@app.route('/mark_complete/<int:memo_id>', methods=['POST'])
def mark_complete(memo_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        memo = Memo.query.get(memo_id)
        if memo:
            completed_memo = CompletedMemo(memo=memo.memo)
            db.session.add(completed_memo)
            db.session.delete(memo)
            db.session.commit()
            flash('Memo marked as complete.', 'success')
        else:
            flash('Memo not found.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking memo as complete: {str(e)}', 'danger')

    return redirect(url_for('index'))


@app.route('/completed_memos')
def completed_jobs():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    completed_memos = CompletedMemo.query.all()
    return render_template('completed_memos.html', completed_memos=completed_memos)


@app.route('/delete_completed_memo/<int:memo_id>', methods=['POST'])
def delete_completed_memo(memo_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        memo = CompletedMemo.query.get(memo_id)
        if memo:
            db.session.delete(memo)
            db.session.commit()
            flash('Memo deleted successfully!', 'success')
        else:
            flash('Memo not found.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting memo: {str(e)}', 'danger')

    return redirect(url_for('completed_jobs'))

@app.route('/notes')
def notes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template('notes.html', notes=notes)


@app.route('/note/<string:slug>')
def view_note(slug):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    note = Note.query.filter_by(slug=slug).first_or_404()
    return render_template('view_note.html', note=note)


@app.route('/submit_note', methods=['POST'])
def submit_note():
    try:
        name = request.form.get('name')
        note_text = request.form.get('note')

        if not name:
            flash('Note name is required!', 'danger')
            return redirect(url_for('notes'))

        slug = Note.generate_unique_slug(name)

        new_note = Note(name=name, slug=slug, note=note_text)
        db.session.add(new_note)
        db.session.commit()

        flash('Your note was submitted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Something went wrong: {str(e)}', 'danger')

    return redirect(url_for('notes'))


@app.route('/delete_note/<string:slug>', methods=['POST'])
def delete_note(slug):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        note = Note.query.filter_by(slug=slug).first()
        if note:
            db.session.delete(note)
            db.session.commit()
            flash('Note deleted successfully!', 'success')
        else:
            flash('Note not found.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting note: {str(e)}', 'danger')

    return redirect(url_for('notes'))


@app.route('/edit_note/<string:slug>', methods=['GET', 'POST'])
def edit_note(slug):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    note = Note.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_text = request.form.get('note')

        if new_name and new_name != note.name:
            note.name = new_name
            note.slug = Note.generate_unique_slug(new_name)

        note.note = new_text

        try:
            db.session.commit()
            flash('Note updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating note: {str(e)}', 'danger')

        return redirect(url_for('notes'))

    return render_template('edit_note.html', note=note)


# Updated edit_journal route
@app.route('/edit_journal/<string:slug>', methods=['GET', 'POST'])
def edit_journal(slug):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    entry = Journal.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_entry_text = request.form['entry']

        if new_name and new_name != entry.name:
            entry.name = new_name
            entry.slug = Journal.generate_unique_slug(new_name)

        entry.entry = new_entry_text
        try:
            db.session.commit()
            flash('Journal updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating journal: {str(e)}', 'danger')

        return redirect(url_for('journal'))

    return render_template('edit_journal.html', entry=entry)



@app.route('/journal')
def journal():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    entries = Journal.query.order_by(Journal.created_at.desc()).all()
    return render_template('journal.html', journal=entries)


@app.route('/submit_journal', methods=['POST'])
def submit_journal():
    try:
        name = request.form.get('name')
        journal_text = request.form.get('journal')

        if not name:
            flash('Entry name is required!', 'danger')
            return redirect(url_for('journal'))

        slug = Journal.generate_unique_slug(name)

        new_entry = Journal(name=name, slug=slug, entry=journal_text)
        db.session.add(new_entry)
        db.session.commit()

        flash('Your journal was submitted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Something went wrong: {str(e)}', 'danger')

    return redirect(url_for('journal'))


@app.route('/delete_journal/<string:slug>', methods=['POST'])
def delete_journal(slug):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        entry = Journal.query.filter_by(slug=slug).first()
        if entry:
            db.session.delete(entry)
            db.session.commit()
            flash('Entry deleted successfully!', 'success')
        else:
            flash('Entry not found.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting entry: {str(e)}', 'danger')

    return redirect(url_for('journal'))


@app.route('/journal/<string:slug>')
def view_journal(slug):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    entry = Journal.query.filter_by(slug=slug).first_or_404()
    return render_template('view_journal.html', entry=entry)

@app.template_filter('nl2br')
def nl2br(value):
    return value.replace('\n', '<br>')


if __name__ == '__main__':
    init_db()
    app.run(debug=False)