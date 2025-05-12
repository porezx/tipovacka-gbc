from main import app
from extensions import db
from models import User

with app.app_context():
    # smažeme starého admina (pokud existuje)
    User.query.filter_by(username='admin').delete()
    db.session.commit()

    # vytvoříme nového
    user = User(
        username='admin',
        secret_word='tajne',
        is_admin=True,
        custom_id=1
    )
    db.session.add(user)
    db.session.commit()
    print("✅ Admin uživatel 'admin' byl úspěšně vytvořen.")
