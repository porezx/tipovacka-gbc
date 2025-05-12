# -*- coding: utf-8 -*-
from flask import Flask
from extensions import db
from routes import bp as routes_bp
import models

app = Flask(__name__)
app.secret_key = 'sluchatka'  # pro fungování flash zpráv
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tipovacka.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

app.register_blueprint(routes_bp)

from datetime import datetime

@app.context_processor
def inject_helpers():
    def format_datetime_cz(dt):
        months = [
            '', 'ledna', 'února', 'března', 'dubna', 'května', 'června',
            'července', 'srpna', 'září', 'října', 'listopadu', 'prosince'
        ]
        return f"{dt.day}. {months[dt.month]} {dt.year} – {dt.strftime('%H:%M')}"

    return {
        'now': datetime.now,
        'format_datetime_cz': format_datetime_cz
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)