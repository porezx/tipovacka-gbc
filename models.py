from extensions import db

user_competitions = db.Table('user_competitions',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('competition_id', db.Integer, db.ForeignKey('competition.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    secret_word = db.Column(db.String(80), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    custom_id = db.Column(db.Integer, unique=True, nullable=False, default=0)
    competitions = db.relationship('Competition', secondary=user_competitions, backref='users')

class Competition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)  # může být prázdné
    description = db.Column(db.Text, nullable=True)
    rules = db.Column(db.Text, nullable=True)


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competition.id'))
    team_home = db.Column(db.String, nullable=False)
    team_away = db.Column(db.String, nullable=False)
    result_home = db.Column(db.Integer)
    result_away = db.Column(db.Integer)
    match_time = db.Column(db.DateTime)
    match_level_id = db.Column(db.Integer, db.ForeignKey('match_level.id'))
    match_level = db.relationship('MatchLevel', backref='matches')
    
class MatchLevel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competition.id'), nullable=False)
    name = db.Column(db.String, nullable=False)
    base_points = db.Column(db.Integer, nullable=False, default=1)
    goal_diff_bonus = db.Column(db.Integer, nullable=False, default=1)
    exact_score_bonus = db.Column(db.Integer, nullable=False, default=1)

    __table_args__ = (
        db.UniqueConstraint('competition_id', 'name', name='unique_level_per_competition'),
    )

    competition = db.relationship('Competition', backref='levels')

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    predicted_home = db.Column(db.Integer)
    predicted_away = db.Column(db.Integer)