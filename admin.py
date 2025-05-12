# create_admin.py

from main import app
from extensions import db
from models import User

with app.app_context():
    existing = User.query.filter_by(username='admin').first()
    if existing:
        print("❌ Uživatel 'admin' už existuje.")
    else:
        user = User(username='admin', secret_word='tajne', is_admin=True)
        db.session.add(user)
        db.session.commit()
        print("✅ Admin uživatel 'admin' byl úspěšně vytvořen.")
