from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from datetime import datetime, date
import calendar
import jpholiday
from models import db, User, Shift
from calendar import monthrange
from sqlalchemy import cast, Date
from collections import defaultdict
from datetime import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shift.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



@app.route('/')
@login_required
def calendar_view():
    today = datetime.today()
    return redirect(url_for('calendar_view_detail', year=today.year, month=today.month))  # ←修正済

@app.route('/calendar/<int:year>/<int:month>')
@login_required
def calendar_view_detail(year, month):
    cal = calendar.Calendar()
    month_days = cal.itermonthdates(year, month)

    # 正しい月末日を取得
    last_day = monthrange(year, month)[1]

    # シフトの取得
    shifts = Shift.query.filter(
        Shift.date >= date(year, month, 1),
        Shift.date <= date(year, month, last_day)
    ).all()

    # 日付ごとにシフトをまとめる
    shifts_by_date = defaultdict(list)
    for shift in shifts:
        key = shift.date.strftime('%Y-%m-%d')
        shifts_by_date[key].append(shift)

    # 祝日取得
    holidays = [d[0].strftime('%Y-%m-%d') for d in jpholiday.month_holidays(year, month)]

    # 週ごとに分けた日付とシフト情報
    weeks = []
    week = []
    for day in month_days:
        if day.month != month:
            week.append(None)  # 前後月の日は None に
        else:
            key = day.strftime('%Y-%m-%d')
            week.append({
                'date': key,
                'day': day.day,
                'shifts': shifts_by_date[key]
            })

        if len(week) == 7:
            weeks.append(week)
            week = []

    # 月移動用
    prev_month = month - 1 if month > 1 else 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year

    return render_template(
        'calendar.html',
        calendar=weeks,
        year=year,
        month=month,
        holidays=holidays,
        user=current_user,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('calendar_view'))
        else:
            flash('ユーザー名またはパスワードが間違っています')  # ← これが必要！
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        is_admin = 'is_admin' in request.form
        
        # 同じユーザー名が既に存在していないか確認
        if User.query.filter_by(username=username).first():
            flash('そのユーザー名は既に使われています')
            return redirect(url_for('register'))

        user = User(username=username)
        user.set_password(password)  # ここでハッシュ化
        user.is_admin = is_admin
        db.session.add(user)
        db.session.commit()
        flash('登録が完了しました。ログインしてください。')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add_shift/<date>', methods=['GET', 'POST'])
@login_required
def add_shift(date):
    if request.method == 'POST':
        from_hour = request.form['from_hour']
        from_minute = request.form['from_minute']
        to_hour = request.form['to_hour']
        to_minute = request.form['to_minute']

        from_time = f"{int(from_hour):02d}:{int(from_minute):02d}"
        to_time = f"{int(to_hour):02d}:{int(to_minute):02d}"

        # 文字列の日付 → datetime.date に変換
        shift_date = datetime.strptime(date, '%Y-%m-%d').date()

        new_shift = Shift(
            user_id=current_user.id,
            date=shift_date,
            from_time=from_time,
            to_time=to_time
        )
        db.session.add(new_shift)
        db.session.commit()
        return redirect(url_for('calendar_view_detail', year=shift_date.year, month=shift_date.month))

    return render_template('add_shift.html', date=date)

@app.route('/edit_shift/<int:shift_id>', methods=['GET', 'POST'])
@login_required
def edit_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.user_id != current_user.id and not current_user.is_admin:
        flash('このシフトを編集する権限がありません。')
        return redirect(url_for('calendar_view'))

    if request.method == 'POST':
        if request.method == 'POST':
            from_hour = request.form['from_hour']
            from_minute = request.form['from_minute']
            to_hour = request.form['to_hour']
            to_minute = request.form['to_minute']

            shift.from_time = f"{int(from_hour):02d}:{int(from_minute):02d}"
            shift.to_time = f"{int(to_hour):02d}:{int(to_minute):02d}"
            db.session.commit()
            flash("シフトを更新しました")
            return redirect(url_for('calendar_view', year=shift.date.year, month=shift.date.month))
    
    return render_template('edit_shift.html', shift=shift)

@app.route('/delete_shift/<int:shift_id>', methods=['POST'])
@login_required
def delete_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.user_id != current_user.id:
        flash("他人のシフトは削除できません")
        return redirect(url_for('calendar_view'))

    db.session.delete(shift)
    db.session.commit()
    flash("シフトを削除しました")
    return redirect(url_for('calendar_view', year=shift.date.year, month=shift.date.month))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)