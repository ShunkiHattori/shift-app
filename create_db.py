from app import db
from  app import app
from models import User, Shift
# appに紐づけたアプリコンテキストで実行する必要がある
with app.app_context():
    db.create_all()
    print("データベースを作成しました。")