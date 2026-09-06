from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from functools import wraps
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stoners-secret-2025')

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///stoners.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    avatar     = db.Column(db.String(4),   default='💪')
    created_at = db.Column(db.DateTime,    default=datetime.now)
    habits     = db.relationship('Habit', backref='owner', lazy=True)
    badges     = db.relationship('Badge', backref='user', lazy=True)

class Habit(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    emoji      = db.Column(db.String(4),   default='🏋️')
    color      = db.Column(db.String(20),  default='olive')
    goal       = db.Column(db.Integer,     default=30)
    created_at = db.Column(db.DateTime,    default=datetime.now)
    user_id    = db.Column(db.Integer,     db.ForeignKey('user.id'), nullable=False)
    logs       = db.relationship('HabitLog', backref='habit', lazy=True, cascade='all, delete')

class HabitLog(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    date     = db.Column(db.Date,    nullable=False, default=date.today)
    done     = db.Column(db.Boolean, default=True)
    __table_args__ = (db.UniqueConstraint('habit_id', 'date'),)

class Badge(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50),  nullable=False)
    description = db.Column(db.String(200), nullable=False)
    icon        = db.Column(db.String(4),   nullable=False)
    milestone   = db.Column(db.Integer,     nullable=False)  # streak days or total reps
    badge_type  = db.Column(db.String(20),  nullable=False)  # 'streak' or 'total'
    earned_at   = db.Column(db.DateTime,    default=datetime.now)
    user_id     = db.Column(db.Integer,     db.ForeignKey('user.id'), nullable=False)

# ── HELPERS ─────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_user():
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None

def calc_streak(habit):
    streak = 0
    d = date.today()
    while True:
        log = HabitLog.query.filter_by(habit_id=habit.id, date=d, done=True).first()
        if log:
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak

def get_month_logs(habit, year, month):
    from calendar import monthrange
    days = monthrange(year, month)[1]
    logs = {}
    for log in HabitLog.query.filter_by(habit_id=habit.id).all():
        if log.date.year == year and log.date.month == month:
            logs[log.date.day] = log.done
    return logs, days

def check_and_award_badges(user):
    """Check if user deserves any new badges"""
    habits = Habit.query.filter_by(user_id=user.id).all()
    
    new_badges = []
    
    # Define all possible badges
    badge_configs = [
        {'name': '7 DAY WARRIOR', 'icon': '🔥', 'milestone': 7, 'type': 'streak', 'desc': 'Achieve a 7-day streak'},
        {'name': '21 DAY SOLDIER', 'icon': '⚡', 'milestone': 21, 'type': 'streak', 'desc': 'Achieve a 21-day streak'},
        {'name': '100 DAY LEGEND', 'icon': '👑', 'milestone': 100, 'type': 'streak', 'desc': 'Achieve a 100-day streak'},
        {'name': '10 HABITS', 'icon': '🎯', 'milestone': 10, 'type': 'count', 'desc': 'Create 10 habits'},
        {'name': '50 REPS', 'icon': '💯', 'milestone': 50, 'type': 'total', 'desc': 'Complete 50 habit logs'},
        {'name': '365 DAYS', 'icon': '🏆', 'milestone': 365, 'type': 'streak', 'desc': 'Achieve a 365-day streak'},
    ]
    
    for config in badge_configs:
        # Check if badge already earned
        existing = Badge.query.filter_by(user_id=user.id, name=config['name']).first()
        if existing:
            continue
        
        earned = False
        
        if config['type'] == 'streak':
            # Check max streak across all habits
            max_streak = max([calc_streak(h) for h in habits], default=0)
            if max_streak >= config['milestone']:
                earned = True
                
        elif config['type'] == 'total':
            # Check total completions
            total = HabitLog.query.join(Habit).filter(
                Habit.user_id == user.id, HabitLog.done == True).count()
            if total >= config['milestone']:
                earned = True
                
        elif config['type'] == 'count':
            # Check habit count
            if len(habits) >= config['milestone']:
                earned = True
        
        if earned:
            badge = Badge(
                name=config['name'],
                icon=config['icon'],
                description=config['desc'],
                milestone=config['milestone'],
                badge_type=config['type'],
                user_id=user.id
            )
            db.session.add(badge)
            new_badges.append(config['name'])
    
    if new_badges:
        db.session.commit()
    
    return new_badges

app.jinja_env.globals['get_user'] = get_user

@app.context_processor
def inject_globals():
    return {'today': date.today(), 'now': datetime.now()}

# ── AUTH ────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']
        avatar   = request.form.get('avatar', '💪')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username taken.', 'error')
            return redirect(url_for('register'))
        user = User(username=username, email=email,
                    password=generate_password_hash(password), avatar=avatar)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── ROUTES ────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    user  = get_user()
    if not user: return redirect(url_for('login'))
    today = date.today()
    now   = datetime.now()
    habits = Habit.query.filter_by(user_id=user.id).order_by(Habit.created_at).all()

    habit_data = []
    for h in habits:
        log_today = HabitLog.query.filter_by(habit_id=h.id, date=today).first()
        streak    = calc_streak(h)
        total     = HabitLog.query.filter_by(habit_id=h.id, done=True).count()
        habit_data.append({
            'habit':      h,
            'done_today': bool(log_today and log_today.done),
            'streak':     streak,
            'total':      total,
            'progress':   min(round(total / h.goal * 100), 100) if h.goal else 0,
        })

    done_count  = sum(1 for h in habit_data if h['done_today'])
    total_count = len(habit_data)
    hour        = now.hour

    if total_count == 0:
        alert_msg  = "NO MISSIONS ASSIGNED YET. PRESS [+] TO BEGIN."
        alert_type = "olive"
    elif hour < 6:
        alert_msg  = "PAST MIDNIGHT — REST UP. MISSIONS RESUME AT DAWN."
        alert_type = "info"
    elif hour < 12:
        alert_msg  = f"MORNING BRIEF — {total_count - done_count} MISSIONS AWAITING EXECUTION. MOVE OUT."
        alert_type = "warning"
    elif hour < 17:
        alert_msg  = f"AFTERNOON SITREP — {done_count}/{total_count} MISSIONS COMPLETE. MAINTAIN TEMPO."
        alert_type = "olive"
    elif hour < 21:
        alert_msg  = f"EVENING DEBRIEF — {total_count - done_count} MISSIONS OUTSTANDING. FINISH STRONG."
        alert_type = "warning"
    else:
        if done_count == total_count:
            alert_msg  = "END OF DAY — ALL MISSIONS COMPLETE. OUTSTANDING. STAND DOWN."
            alert_type = "green"
        else:
            alert_msg  = f"END OF DAY — {total_count - done_count} MISSIONS INCOMPLETE. DEBRIEF REQUIRED."
            alert_type = "red"

    return render_template('index.html', user=user, habit_data=habit_data,
                           today=today, now=now,
                           done_count=done_count, total_count=total_count,
                           alert_msg=alert_msg, alert_type=alert_type)

@app.route('/add_habit', methods=['POST'])
@login_required
def add_habit():
    name  = request.form['name'].strip()
    emoji = request.form.get('emoji', '🏋️')
    color = request.form.get('color', 'olive')
    goal  = int(request.form.get('goal', 30))
    if name:
        habit = Habit(name=name, emoji=emoji, color=color, goal=goal,
                      user_id=session['user_id'])
        db.session.add(habit)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_habit/<int:habit_id>', methods=['POST'])
@login_required
def delete_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id == session['user_id']:
        db.session.delete(habit)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/toggle/<int:habit_id>', methods=['POST'])
@login_required
def toggle(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    today = date.today()
    log = HabitLog.query.filter_by(habit_id=habit_id, date=today).first()
    if log:
        db.session.delete(log)
        done = False
    else:
        log = HabitLog(habit_id=habit_id, date=today, done=True)
        db.session.add(log)
        done = True
    db.session.commit()
    streak = calc_streak(habit)
    
    # Check for new badges
    user = get_user()
    new_badges = check_and_award_badges(user)
    
    return jsonify({'done': done, 'streak': streak, 'new_badges': new_badges})

@app.route('/habit/<int:habit_id>')
@login_required
def habit_detail(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != session['user_id']:
        return redirect(url_for('index'))
    today = date.today()
    year  = int(request.args.get('year',  today.year))
    month = int(request.args.get('month', today.month))
    logs, days_in_month = get_month_logs(habit, year, month)
    streak   = calc_streak(habit)
    total    = HabitLog.query.filter_by(habit_id=habit.id, done=True).count()
    progress = min(round(total / habit.goal * 100), 100) if habit.goal else 0
    prev_month    = month - 1 if month > 1 else 12
    prev_year     = year if month > 1 else year - 1
    next_month    = month + 1 if month < 12 else 1
    next_year     = year if month < 12 else year + 1
    first_weekday = date(year, month, 1).weekday()
    month_name    = date(year, month, 1).strftime('%B %Y')
    return render_template('habit_detail.html', habit=habit,
                           logs=logs, days=days_in_month,
                           streak=streak, total=total, progress=progress,
                           year=year, month=month, month_name=month_name,
                           prev_month=prev_month, prev_year=prev_year,
                           next_month=next_month, next_year=next_year,
                           first_weekday=first_weekday, today=today)

@app.route('/stats')
@login_required
def stats():
    user = get_user()
    if not user: return redirect(url_for('login'))
    habits = Habit.query.filter_by(user_id=user.id).all()
    today  = date.today()

    data = []
    for h in habits:
        streak   = calc_streak(h)
        total    = HabitLog.query.filter_by(habit_id=h.id, done=True).count()
        progress = min(round(total / h.goal * 100), 100) if h.goal else 0
        data.append({'habit': h, 'streak': streak, 'total': total, 'progress': progress})

    best              = max(data, key=lambda x: x['streak']) if data else None
    total_completions = sum(d['total'] for d in data)
    longest_streak    = max((d['streak'] for d in data), default=0)
    avg_rate          = round(sum(d['progress'] for d in data) / len(data)) if data else 0

    chart_labels  = json.dumps([d['habit'].name for d in data])
    chart_totals  = json.dumps([d['total']      for d in data])
    chart_streaks = json.dumps([d['streak']     for d in data])

    week_labels = []
    week_counts = []
    for i in range(6, -1, -1):
        day   = today - timedelta(days=i)
        count = 0
        for h in habits:
            if HabitLog.query.filter_by(habit_id=h.id, date=day, done=True).first():
                count += 1
        week_labels.append(day.strftime('%a').upper())
        week_counts.append(count)

    return render_template('stats.html', user=user, data=data,
                           best=best,
                           total_completions=total_completions,
                           longest_streak=longest_streak,
                           avg_rate=avg_rate,
                           chart_labels=chart_labels,
                           chart_totals=chart_totals,
                           chart_streaks=chart_streaks,
                           week_labels=json.dumps(week_labels),
                           week_counts=json.dumps(week_counts))

@app.route('/profile')
@login_required
def profile():
    user = get_user()
    if not user: return redirect(url_for('login'))
    habits = Habit.query.filter_by(user_id=user.id).all()
    total  = HabitLog.query.join(Habit).filter(
                Habit.user_id == user.id, HabitLog.done == True).count()
    rates  = []
    for h in habits:
        t = HabitLog.query.filter_by(habit_id=h.id, done=True).count()
        rates.append(min(round(t / h.goal * 100), 100) if h.goal else 0)
    rate   = round(sum(rates) / len(rates)) if rates else 0
    cats   = db.session.query(Habit.name, db.func.count(HabitLog.id))\
                       .join(HabitLog, HabitLog.habit_id == Habit.id)\
                       .filter(Habit.user_id == user.id, HabitLog.done == True)\
                       .group_by(Habit.name).all()
    
    return render_template('profile.html', user=user,
                           total=total, done=total, rate=rate,
                           habits=habits, cats=cats)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
