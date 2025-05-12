from flask import Blueprint, request, jsonify
from extensions import db
from models import User, Competition, Match, Prediction, MatchLevel
import pandas as pd
import re
from datetime import datetime
from flask import flash
from datetime import timedelta



CZ_MESICE = {
    "ledna": 1, "února": 2, "března": 3, "dubna": 4,
    "května": 5, "června": 6, "července": 7, "srpna": 8,
    "září": 9, "října": 10, "listopadu": 11, "prosince": 12
}

def parse_czech_date(date_str):
    match = re.match(r"(\d{1,2})\.\s*(\w+)", date_str.strip())
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        month = CZ_MESICE.get(month_name)
        if month:
            return datetime(2025, month, day)  # Fixní rok
    return None


bp = Blueprint('routes', __name__)

@bp.route('/users', methods=['POST'])
def create_user():
    username = request.json.get('username')
    user = User(username=username)
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id})

@bp.route('/competitions', methods=['POST'])
def create_competition():
    name = request.json.get('name')
    comp = Competition(name=name)
    db.session.add(comp)
    db.session.commit()
    return jsonify({'id': comp.id})

@bp.route('/matches', methods=['POST'])
def create_match():
    data = request.json
    match = Match(
        competition_id=data['competition_id'],
        team_home=data['team_home'],
        team_away=data['team_away']
    )
    db.session.add(match)
    db.session.commit()
    return jsonify({'id': match.id})

@bp.route('/predictions', methods=['POST'])
def add_prediction():
    data = request.json
    pred = Prediction(
        user_id=data['user_id'],
        match_id=data['match_id'],
        predicted_home=data['predicted_home'],
        predicted_away=data['predicted_away']
    )
    db.session.add(pred)
    db.session.commit()
    return jsonify({'id': pred.id})

from flask import render_template, redirect, url_for

@bp.route('/register', methods=['GET', 'POST'])
def register():
    competitions = Competition.query.all()

    if request.method == 'POST':
        username = request.form.get('username').strip()
        secret_word = request.form.get('secret_word').strip()
        selected_ids = request.form.getlist('competition_ids')

        if not selected_ids:
            return "Musíš vybrat alespoň jednu soutěž!", 400

        selected_ids = list(map(int, selected_ids))
        selected_competitions = Competition.query.filter(Competition.id.in_(selected_ids)).all()

        user = User.query.filter_by(username=username).first()
        newly_added = []

        if not user:
            # vytvoření nového uživatele
            user = User(username=username, secret_word=secret_word)
            user.competitions = selected_competitions
            db.session.add(user)
            newly_added = selected_competitions
            msg = f"Uživatel <strong>{username}</strong> byl úspěšně zaregistrován."
        else:
            if user.secret_word != secret_word:
                return "❌ Uživatelské jméno už existuje, ale tajné slovo nesouhlasí!", 403

            for comp in selected_competitions:
                if comp not in user.competitions:
                    user.competitions.append(comp)
                    newly_added.append(comp)
            msg = f"Uživatel <strong>{username}</strong> už existuje."

        db.session.commit()
        flash('✅ Účet byl vytvořen. Nyní se prosím přihlas.')
        return redirect('/login')

        if newly_added:
            msg += " Přihlášen do soutěží: " + ", ".join([f"<strong>{c.name}</strong>" for c in newly_added])
        else:
            msg += " Nebyla přidána žádná nová soutěž."

        return f"{msg}. <a href=\"/register\">Zpět</a>"

    return render_template('register.html', competitions=competitions)


@bp.route('/predict', methods=['GET', 'POST'])
def predict():
    if 'user_id' not in session:
        return redirect('/login')

    from datetime import datetime

    users = User.query.all()
    prediction_map = {}
    user_id = session['user_id']

    if request.method == 'POST' and user_id:
        user = User.query.get(int(user_id))
        if user:
            matches = Match.query.filter(Match.competition_id.in_([c.id for c in user.competitions])).all()

            for match in matches:
                home_key = f'predicted_home_{match.id}'
                away_key = f'predicted_away_{match.id}'

                if home_key in request.form and away_key in request.form:
                    try:
                        predicted_home = int(request.form.get(home_key))
                        predicted_away = int(request.form.get(away_key))
                    except ValueError:
                        continue  # přeskoč neplatný vstup

                    if match.match_time and match.match_time <= datetime.now():
                        continue  # nelze tipovat zpětně

                    pred = Prediction.query.filter_by(user_id=user.id, match_id=match.id).first()
                    if pred:
                        pred.predicted_home = predicted_home
                        pred.predicted_away = predicted_away
                    else:
                        pred = Prediction(
                            user_id=user.id,
                            match_id=match.id,
                            predicted_home=predicted_home,
                            predicted_away=predicted_away
                        )
                        db.session.add(pred)

            db.session.commit()
            flash("✅ Tipy byly uloženy.")

        return redirect('/predict')

    # GET část – zobrazení zápasů a tipů
    user = User.query.get(int(user_id)) if user_id else None
    matches = []
    prediction_map = {}

    if user:
        print(f"User: {user.username}")
        print(f"Soutěže: {[c.name for c in user.competitions]}")
        matches = Match.query.filter(Match.competition_id.in_([c.id for c in user.competitions])).order_by(Match.match_time).all()
        predictions = Prediction.query.filter_by(user_id=user.id).all()
        prediction_map = {(p.user_id, p.match_id): p for p in predictions}

    return render_template(
        'predict.html',
        users=users,
        matches=matches,
        prediction_map=prediction_map,
        user_id=user_id,
    )

@bp.route('/result', methods=['GET', 'POST'])
def result():
    competitions = Competition.query.all()

    if request.method == 'POST' and 'competition_id' in request.form and any(k.startswith('result_home_') for k in request.form.keys()):
        comp_id = int(request.form.get('competition_id'))
        matches = Match.query.filter_by(competition_id=comp_id).all()

        for match in matches:
            home_key = f'result_home_{match.id}'
            away_key = f'result_away_{match.id}'

            if home_key in request.form and away_key in request.form:
                try:
                    result_home = int(request.form.get(home_key))
                    result_away = int(request.form.get(away_key))
                    match.result_home = result_home
                    match.result_away = result_away
                except ValueError:
                    continue

        db.session.commit()
        return redirect(f'/result?competition_id={comp_id}')

    comp_id = request.args.get('competition_id', type=int)
    matches = Match.query.filter_by(competition_id=comp_id).order_by(Match.match_time).all() if comp_id else []

    return render_template('result.html',
                           competitions=competitions,
                           selected_competition=comp_id,
                           matches=matches)

def calculate_points(pred, match):
    if match.result_home is None or match.result_away is None:
        return 0

    points = 0

    # Správný vítěz nebo remíza
    predicted_diff = pred.predicted_home - pred.predicted_away
    actual_diff = match.result_home - match.result_away

    if ((pred.predicted_home > pred.predicted_away and match.result_home > match.result_away) or
        (pred.predicted_home < pred.predicted_away and match.result_home < match.result_away) or
        (pred.predicted_home == pred.predicted_away and match.result_home == match.result_away)):
        points += 20

    # Správný rozdíl
    if predicted_diff == actual_diff:
        points += 10

    # Přesný výsledek
    if (pred.predicted_home == match.result_home and
        pred.predicted_away == match.result_away):
        points += 10

    return points

@bp.route('/scores')
def scores():
    competitions = Competition.query.all()
    comp_id = request.args.get('competition_id', type=int)

    if not comp_id:
        return render_template('scores.html', competitions=competitions, selected_competition=None, scores=[])

    selected_comp = Competition.query.get(comp_id)
    if not selected_comp:
        return f"Soutěž s ID {comp_id} nenalezena", 404

    users = selected_comp.users
    username_to_custom = { u.username: u.custom_id for u in users }
    matches = Match.query.filter_by(competition_id=comp_id).all()
    predictions = Prediction.query.filter(Prediction.match_id.in_([m.id for m in matches])).all()

    user_scores = {}

    for user in users:
        user_total = 0
        for pred in predictions:
            if pred.user_id == user.id:
                match = next((m for m in matches if m.id == pred.match_id), None)
                if match:
                    user_total += calculate_points(pred, match)
        user_scores[user.username] = user_total

    sorted_scores = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)

    return render_template('scores.html',
                           competitions=competitions,
                           selected_competition=comp_id,
                           scores=sorted_scores)

@bp.route('/admin/scores')
def admin_scores():
    competitions = Competition.query.all()
    comp_id = request.args.get('competition_id', type=int) or (competitions[0].id if competitions else None)
    selected = Competition.query.get(comp_id) if comp_id else None

    levels = MatchLevel.query.filter_by(competition_id=comp_id).all() if selected else []

    # Celková skóre (jako ve scores)
    users = selected.users if selected else []
    username_to_custom = { u.username: u.custom_id for u in users }
    matches = Match.query.filter_by(competition_id=comp_id).all() if selected else []
    predictions = Prediction.query.filter(Prediction.match_id.in_([m.id for m in matches])).all()
    user_scores = {u.username: 0 for u in users}
    user_map = {u.id: u.username for u in users}
    match_map = {m.id: m for m in matches}
#    for p in predictions:
#        # reuse calculate_points()
#        points = calculate_points(p, next(m for m in matches if m.id == p.match_id))
#        user_scores[p.user.username] += points

    for p in predictions:
        # najdi uživatelské jméno z user_map
        username = user_map.get(p.user_id)
        if not username:
            continue  # tento tip ignoruj, pokud uživatel neexistuje

        # najdi zápas z match_map
        match = match_map.get(p.match_id)
        if not match:
            continue  # ignoruj, pokud zápas neexistuje

        # spočítej body a přidej k uživatelovu skóre
        pts = calculate_points(p, match)
        user_scores[username] += pts

    # ── Připrav metriky pro tiebreakery založené na bodech ────────────────────
    # slovník username → { total, base_pts, diff_pts, exact_pts }
    metrics = {
        u.username: {'total': 0, 'base_pts': 0, 'diff_pts': 0, 'exact_pts': 0}
        for u in users
    }

    for p in predictions:
        username = user_map.get(p.user_id)
        match    = match_map.get(p.match_id)
        # ignoruj, pokud zápas ještě nemá nastavený výsledek
        if match.result_home is None or match.result_away is None:
            continue
        # ignoruj, pokud uživatel nezadal tip
        if p.predicted_home is None or p.predicted_away is None:
            continue

        if not username or not match:
            continue

        # načti bonusy z dané úrovně (default 1/1/1)
        lvl = match.match_level or MatchLevel(base_points=1, goal_diff_bonus=1, exact_score_bonus=1)
        # spočítej body jednotlivých složek
        bp = lvl.base_points if (
            (p.predicted_home > p.predicted_away and match.result_home > match.result_away) or
            (p.predicted_home < p.predicted_away and match.result_home < match.result_away) or
            (p.predicted_home == p.predicted_away and match.result_home == match.result_away)
        ) else 0

        dp = lvl.goal_diff_bonus if (p.predicted_home - p.predicted_away) == (match.result_home - match.result_away) else 0
        ep = lvl.exact_score_bonus if (p.predicted_home == match.result_home and p.predicted_away == match.result_away) else 0

        total = bp + dp + ep

        # akumulace
        metrics[username]['total']    += total
        metrics[username]['base_pts'] += bp
        metrics[username]['diff_pts'] += dp
        metrics[username]['exact_pts']+= ep

    # seřazení podle čtyř kritérií (sestupně)
    sorted_players = sorted(
        metrics.items(),
        key=lambda item: (
            -item[1]['total'],
            -item[1]['base_pts'],
            -item[1]['diff_pts'],
            -item[1]['exact_pts'],
            username_to_custom[item[0]]
        )
    )

    # sestavíme final_scores s unikátním rankem
    final_scores = []
    for idx, (username, data) in enumerate(sorted_players, start=1):
        final_scores.append({
            'rank': idx,
            'username': username,
            **data
        })

# ── Dení rozpad bodů ────────────────────────────────────────────────────────
# Seskup zápasy podle data (bez času)
    from collections import defaultdict
    daily_scores = defaultdict(lambda: {u.username: 0 for u in users})

    for p in predictions:
        # najdi zápas a uživatele (mapy jsme už vytvořili výše)
        username = user_map.get(p.user_id)
        match = match_map.get(p.match_id)
        if not username or not match:
            continue

        # den bez času
        day = match.match_time.date()
        pts = calculate_points(p, match)
        daily_scores[day][username] += pts
    # Převod na normální dict a seřazení podle dne
    daily_scores = dict(sorted(daily_scores.items()))

    # ── Připrav detailní rozpad bodů po dnech ──────────────────────────
    # Inicializace: pro každý den a každého uživatele struktura bodů
    daily_breakdown = {
        day: { u.username: {'total':0,'base_pts':0,'diff_pts':0,'exact_pts':0}
               for u in users }
        for day in daily_scores
    }

    # Naplnění bodů z predikcí
    for p in predictions:
        username = user_map.get(p.user_id)
        match    = match_map.get(p.match_id)
        # ignoruj nekompletní data
        if not username or not match or match.result_home is None or match.result_away is None:
            continue

        day = match.match_time.date()
        lvl = match.match_level or MatchLevel(
            base_points=1, goal_diff_bonus=1, exact_score_bonus=1
        )

        # spočti složky
        bp = lvl.base_points if (
            (p.predicted_home > p.predicted_away and match.result_home > match.result_away) or
            (p.predicted_home < p.predicted_away and match.result_home < match.result_away) or
            (p.predicted_home == p.predicted_away and match.result_home == match.result_away)
        ) else 0
        dp = lvl.goal_diff_bonus if (p.predicted_home - p.predicted_away) == (match.result_home - match.result_away) else 0
        ep = lvl.exact_score_bonus if (p.predicted_home == match.result_home and p.predicted_away == match.result_away) else 0
        total = bp + dp + ep

        db = daily_breakdown[day][username]
        db['total']    += total
        db['base_pts'] += bp
        db['diff_pts'] += dp
        db['exact_pts']+= ep

    # ── Spočti kumulativní breakdown bodů do každého dne ───────────────────
    cumulative_breakdown = {}
    # Inicializace prázdných „běžců“
    running = {
        u.username: {'total':0,'base_pts':0,'diff_pts':0,'exact_pts':0}
        for u in users
    }

    # Pro každý den seřazeně navýšíme běžce o hodnoty z daily_breakdown
    for day in sorted(daily_breakdown):
        running_for_day = {}
        for user, vals in daily_breakdown[day].items():
            running[user]['total']    += vals['total']
            running[user]['base_pts'] += vals['base_pts']
            running[user]['diff_pts'] += vals['diff_pts']
            running[user]['exact_pts']+= vals['exact_pts']
            # Ulož snapshot aktuálních běžců
            running_for_day[user] = running[user].copy()
        cumulative_breakdown[day] = running_for_day



    import io
    import base64
    import matplotlib.pyplot as plt
    import pandas as pd

    # --- Připrav data pro graf ---
    # daily_scores: dict[date -> dict[username -> points]]
#    # Nejprve DataFrame
#    df_daily = pd.DataFrame(daily_scores).T.fillna(0)      # dny x hráči
#    df_cum = df_daily.cumsum()                             # kumulativní body
#    # Spočti pořadí (rank, 1 = nejlepší)
#    ranks = df_cum.rank(axis=1, method='min', ascending=False)
    # ── Připrav pořadí hráčů po každém dni s full tiebreakery ───────────
    daily_ranks = {}
    for day, metrics_for_day in cumulative_breakdown.items():
        # metrics_for_day: { username -> {total, base_pts, diff_pts, exact_pts} }
        # seřadíme hráče podle všech 4 kritérií
        ordered = sorted(
            metrics_for_day.items(),
            key=lambda item: (
                -item[1]['total'],
                -item[1]['base_pts'],
                -item[1]['diff_pts'],
                -item[1]['exact_pts'],
                username_to_custom[item[0]]
            )
        )
        # přiřaďme rank (1 = nejlepší, 2 = druhý, …)
        ranks_for_day = {}
        for idx, (username, _) in enumerate(ordered, start=1):
            ranks_for_day[username] = idx
        daily_ranks[day] = ranks_for_day

    # ── Připrav data pro graf z daily_ranks ───────────────────────────────
    # Seřazené dny
    days = sorted(daily_ranks.keys())
    # Seřazené seznamy hráčů
    players = [entry['username'] for entry in final_scores]

    # Sestroj matici: řada = hráč, sloupec = den → rank
    data = {pl: [ daily_ranks[day][pl] for day in days ] for pl in players}


    # --- Vykresli do PNG v paměti ---
    fig, ax = plt.subplots(figsize=(16,8))
    for player in players:
        ax.plot(days, data[player], marker='o', label=player)
    # Přidej jméno hráče vlevo vedle začátku čáry
    for player in players:
        # hodnota ranku prvního dne
        y0 = data[player][0]
        # lehce posuň x-ovou souřadnici před první den
        x0 = days[0] - timedelta(days=0.3)
        ax.text(x0, y0, player, va='center', ha='right', fontsize='small', clip_on=False)

    ax.invert_yaxis()
    ax.set_xlabel('Datum')
    ax.set_ylabel('Pozice (1=nejlepší)')
    ax.set_title('Vývoj pozice hráčů podle kumulativního skóre')
    ax.legend(title='Hráč', bbox_to_anchor=(1.05,1), loc='upper left')
    fig.autofmt_xdate()


    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('ascii')
    rank_graph = f"data:image/png;base64,{img_b64}"


    return render_template('admin_scores.html',
                           competitions=competitions,
                           selected_competition=selected,
                           final_scores=final_scores,
                           scores=sorted(user_scores.items(), key=lambda x: x[1], reverse=True),
                           levels=levels,
#                           detailed_scores=detailed,
                           daily_scores=daily_scores,
                           daily_ranks=daily_ranks,
                           daily_breakdown=daily_breakdown,
                           cumulative_breakdown=cumulative_breakdown,
                           rank_graph=rank_graph)


@bp.route('/tips')
def tips():
    matches = Match.query.all()
    users = {user.id: user.username for user in User.query.all()}
    predictions = Prediction.query.all()

    # Přiřadíme predikce k zápasům
    tips_by_match = {}
    for match in matches:
        tips_by_match[match.id] = {
            'match': match,
            'predictions': []
        }

    for pred in predictions:
        match = tips_by_match.get(pred.match_id)
        if match:
            match_obj = match['match']
            points = calculate_points(pred, match_obj)
            match['predictions'].append({
                'username': users.get(pred.user_id, f'ID {pred.user_id}'),
                'predicted_home': pred.predicted_home,
                'predicted_away': pred.predicted_away,
                'points': points if match_obj.result_home is not None else None
            })

    return render_template('tips.html', tips_by_match=tips_by_match)

from datetime import datetime

@bp.route('/admin/matches', methods=['GET', 'POST'])
def admin_matches():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update':
            match_id = int(request.form.get('match_id'))
            match = Match.query.get(match_id)
            if match:
                match.team_home = request.form.get('team_home')
                match.team_away = request.form.get('team_away')
                dt_str = request.form.get('match_time')
                if dt_str:
                    match.match_time = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')

                level_id = request.form.get('match_level_id')
                match.match_level_id = int(level_id) if level_id else None

                db.session.commit()

        elif action == 'delete':
            match_id = int(request.form.get('match_id'))
            match = Match.query.get(match_id)
            if match:
                db.session.delete(match)
                db.session.commit()
                
        elif action == 'bulk_update':
            for key in request.form:
                if key.startswith('match_id_'):
                    match_id = int(request.form[key])
                    match = Match.query.get(match_id)
                    if match:
                        match.team_home = request.form.get(f'team_home_{match_id}')
                        match.team_away = request.form.get(f'team_away_{match_id}')
                        match_time_str = request.form.get(f'match_time_{match_id}')
                        level_id = request.form.get(f'match_level_id_{match_id}') or None

                        match.match_time = datetime.strptime(match_time_str, '%Y-%m-%dT%H:%M') if match_time_str else None
                        match.match_level_id = int(level_id) if level_id else None
            db.session.commit()
            flash("✅ Všechny změny byly uloženy.", "success")

        elif action == 'import':
            comp_id = int(request.form.get('competition_id'))
            file = request.files.get('match_file')
            imported = 0
            skipped = 0

            if file and file.filename.endswith('.xlsx'):
                df = pd.read_excel(file)

                for _, row in df.iterrows():
                    try:
                        date_part = parse_czech_date(str(row.get("DATUM")))
                        time_raw = row.get("ČAS")
                        time_part = pd.to_datetime(str(time_raw)).time() if pd.notna(time_raw) else None

                        if not date_part or not time_part:
                            skipped += 1
                            continue

                        match_time = datetime.combine(date_part.date(), time_part)
                        team_home = str(row.get("ZÁPAS")).strip()
                        team_away = str(row.get("Unnamed: 4")).strip()

                        if not team_home or not team_away:
                            skipped += 1
                            continue

                        level_name = str(row.get("ÚROVEŇ")).strip() if pd.notna(row.get("ÚROVEŇ")) else None
                        match_level = None
                        if level_name:
                            match_level = MatchLevel.query.filter_by(competition_id=comp_id, name=level_name).first()
                            
                        match = Match(
                            team_home=team_home,
                            team_away=team_away,
                            match_time=match_time,
                            competition_id=comp_id,
                            match_level_id=match_level.id if match_level else None
                        )
                        db.session.add(match)
                        imported += 1
                    except:
                        skipped += 1

                db.session.commit()
                flash(f'✅ Importováno {imported} zápasů. Přeskočeno {skipped}.', 'success')

        elif action == 'add':
            match_level_id = request.form.get('match_level_id')
            new_match = Match(
                team_home=request.form.get('team_home'),
                team_away=request.form.get('team_away'),
                match_time=datetime.strptime(request.form.get('match_time'), '%Y-%m-%dT%H:%M'),
                competition_id=int(request.form.get('competition_id')),
                match_level_id=int(match_level_id) if match_level_id else None
            )
            db.session.add(new_match)
            db.session.commit()

        return redirect('/admin/matches')

    competitions = Competition.query.all()
    matches_by_competition = {}
    levels_by_competition = {}

    for comp in competitions:
        matches = Match.query.filter_by(competition_id=comp.id).order_by(Match.match_time).all()
        matches_by_competition[comp] = matches
        levels = MatchLevel.query.filter_by(competition_id=comp.id).order_by(MatchLevel.base_points).all()
        levels_by_competition[comp.id] = levels

    return render_template(
        'admin_matches.html',
        matches_by_competition=matches_by_competition,
        competitions=competitions,
        levels_by_competition=levels_by_competition
    )

@bp.route('/admin/competitions', methods=['GET', 'POST'])
def admin_competitions():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            name = request.form.get('name')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            description = request.form.get('description')
            rules = request.form.get('rules')

            new_comp = Competition(
                name=name,
                start_date=datetime.strptime(start_date, '%Y-%m-%d') if start_date else None,
                end_date=datetime.strptime(end_date, '%Y-%m-%d') if end_date else None,
                description=description,
                rules=rules
            )
            db.session.add(new_comp)
            db.session.commit()

        elif action == 'update':
            comp_id = int(request.form.get('competition_id'))
            comp = Competition.query.get(comp_id)
            if comp:
                comp.name = request.form.get('name')
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                comp.start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
                comp.end_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
                comp.description = request.form.get('description')
                comp.rules = request.form.get('rules')
                db.session.commit()

        elif action == 'delete':
            comp_id = int(request.form.get('competition_id'))
            comp = Competition.query.get(comp_id)
            if comp:
                db.session.delete(comp)
                db.session.commit()

        return redirect('/admin/competitions')

    competitions = Competition.query.order_by(Competition.start_date.desc().nullslast()).all()
    match_levels_by_competition = {
        comp.id: MatchLevel.query.filter_by(competition_id=comp.id).all()
        for comp in competitions
    }

    return render_template(
        'admin_competitions.html',
        competitions=competitions,
        match_levels_by_competition=match_levels_by_competition
    )

@bp.route('/admin/user_tips', methods=['GET', 'POST'])
def admin_user_tips():
    users = User.query.order_by(User.username).all()
    competitions = Competition.query.order_by(Competition.start_date.desc()).all()

    if request.method == 'POST':
        action = request.form.get('action')

        user_id = int(request.form.get('user_id'))
        competition_id = request.form.get('competition_id', type=int)

        if action == 'update':
            prediction = Prediction.query.get(int(request.form.get('prediction_id')))
            if prediction:
                prediction.predicted_home = int(request.form.get('predicted_home'))
                prediction.predicted_away = int(request.form.get('predicted_away'))
                db.session.commit()

        elif action == 'delete':
            prediction = Prediction.query.get(int(request.form.get('prediction_id')))
            if prediction:
                db.session.delete(prediction)
                db.session.commit()

        elif action == 'create':
            new_prediction = Prediction(
                user_id=user_id,
                match_id=int(request.form.get('match_id')),
                predicted_home=int(request.form.get('predicted_home')),
                predicted_away=int(request.form.get('predicted_away'))
            )
            db.session.add(new_prediction)
            db.session.commit()
        
        return redirect(f'/admin/user_tips?user_id={user_id}&competition_id={competition_id}')
        
    else:
        user_id = request.args.get('user_id', type=int)
        competition_id = request.args.get('competition_id', type=int)

    selected_user = User.query.get(user_id) if user_id else None

    if not competition_id and competitions:
        competition_id = competitions[0].id

    selected_competition = Competition.query.get(competition_id) if competition_id else None

    predictions = []
    matches = {}

    if selected_user:
        if selected_competition:
            match_list = Match.query.filter_by(competition_id=selected_competition.id).order_by(Match.match_time).all()
        else:
            competition_ids = [c.id for c in selected_user.competitions]
            match_list = Match.query.filter(Match.competition_id.in_(competition_ids)).order_by(Match.match_time).all()

        matches = {m.id: m for m in match_list}
        predictions = Prediction.query.filter_by(user_id=selected_user.id).all()

    prediction_map = {p.match_id: p for p in predictions}

    return render_template('admin_user_tips.html',
                           users=users,
                           competitions=competitions,
                           selected_user=selected_user,
                           selected_competition=selected_competition,
                           predictions=predictions,
                           matches=matches,
                           prediction_map=prediction_map)


@bp.route('/user/<username>', methods=['GET', 'POST'])
def user_dashboard(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return f"Uživatel <strong>{username}</strong> neexistuje.", 404

    all_comps = Competition.query.all()
    registered = set(user.competitions)
    not_registered = [c for c in all_comps if c not in registered]

    if request.method == 'POST':
        selected_ids = request.form.getlist('competition_ids')
        selected_comps = Competition.query.filter(Competition.id.in_(selected_ids)).all()

        newly_added = []
        for comp in selected_comps:
            if comp not in user.competitions:
                user.competitions.append(comp)
                newly_added.append(comp)

        db.session.commit()

        return redirect(url_for('routes.user_dashboard', username=username))

    return render_template('user_dashboard.html',
                           user=user,
                           registered=registered,
                           not_registered=not_registered)

@bp.route('/user')
def user_redirect():
    username = request.args.get('username')
    if not username:
        return "Chybí uživatelské jméno.", 400
    return redirect(url_for('routes.user_dashboard', username=username.strip()))

@bp.route('/my-tips')
def my_tips():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        return "Uživatel neexistuje.", 404

    matches = Match.query.filter(Match.competition_id.in_([c.id for c in user.competitions])).order_by(Match.match_time).all()
    predictions = Prediction.query.filter_by(user_id=user.id).all()
    prediction_map = {p.match_id: p for p in predictions}

    return render_template('my_tips.html',
                           user=user,
                           matches=matches,
                           prediction_map=prediction_map,
                           now=datetime.now())


from flask import session

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        secret_word = request.form['secret_word']
        user = User.query.filter_by(username=username).first()

        if user and user.secret_word == secret_word:
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin

            flash("✅ Přihlášení úspěšné.")

            next_url = request.args.get('next')
            return redirect(next_url or '/predict')  # fallback pokud není next

        flash("❌ Neplatné přihlašovací údaje.")
        return redirect('/login')

    return render_template('login.html')



@bp.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@bp.route('/admin/competition_tips')
def admin_competition_tips():
    competition_id = request.args.get('competition_id', type=int)

    competitions = Competition.query.order_by(Competition.start_date.desc()).all()
    if not competition_id and competitions:
        competition_id = competitions[0].id

    selected_competition = Competition.query.get(competition_id) if competition_id else None

    users = selected_competition.users if selected_competition else []
    matches = Match.query.filter_by(competition_id=competition_id).order_by(Match.match_time).all() if selected_competition else []

    predictions = {}
    if selected_competition:
        all_preds = Prediction.query.join(User).filter(User.id.in_([u.id for u in users])).all()
        predictions = {(p.user_id, p.match_id): p for p in all_preds}

    return render_template('admin_competition_tips.html',
                           competitions=competitions,
                           selected_competition=selected_competition,
                           users=users,
                           matches=matches,
                           predictions=predictions)
                           
@bp.route('/')
def home():
    return render_template('home.html')


@bp.route('/admin/match_levels', methods=['GET', 'POST'])
def admin_match_levels():
    competitions = Competition.query.order_by(Competition.name).all()
    selected_id = request.form.get('competition_id') or request.args.get('competition_id')
    selected_competition = Competition.query.get(int(selected_id)) if selected_id else None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add' and selected_competition:
            name = request.form.get('name').strip()
            base_points = int(request.form.get('base_points'))
            goal_diff_bonus = int(request.form.get('goal_diff_bonus'))
            exact_score_bonus = int(request.form.get('exact_score_bonus'))

            new_level = MatchLevel(
                name=name,
                competition_id=selected_competition.id,
                base_points=base_points,
                goal_diff_bonus=goal_diff_bonus,
                exact_score_bonus=exact_score_bonus
            )
            db.session.add(new_level)
            db.session.commit()

        elif action == 'update':
            level = MatchLevel.query.get(int(request.form.get('level_id')))
            if level:
                level.name = request.form.get('name').strip()
                level.base_points = int(request.form.get('base_points'))
                level.goal_diff_bonus = int(request.form.get('goal_diff_bonus'))
                level.exact_score_bonus = int(request.form.get('exact_score_bonus'))
                db.session.commit()

        elif action == 'delete':
            level = MatchLevel.query.get(int(request.form.get('level_id')))
            if level:
                db.session.delete(level)
                db.session.commit()

        return redirect(f'/admin/match_levels?competition_id={request.form.get("competition_id")}')

    levels = MatchLevel.query.filter_by(competition_id=selected_competition.id).order_by(MatchLevel.base_points).all() if selected_competition else []

    return render_template(
        'admin_match_levels.html',
        competitions=competitions,
        selected_competition=selected_competition,
        levels=levels
    )

@bp.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    competitions = Competition.query.order_by(Competition.name).all()

    if request.method == 'POST':
        action = request.form.get('action')
        user_id = int(request.form.get('user_id'))
        user = User.query.get(user_id)

        if action == 'update' and user:
            user.username = request.form.get('username')
            user.custom_id = int(request.form.get('custom_id') or 0)
            selected_ids = request.form.getlist('competition_ids[]')
            selected_competitions = Competition.query.filter(Competition.id.in_(selected_ids)).all()
            user.competitions = selected_competitions
            db.session.commit()

        elif action == 'delete' and user:
            db.session.delete(user)
            db.session.commit()

        return redirect('/admin/users')

    users = User.query.order_by(User.username).all()
    return render_template('admin_users.html', users=users, competitions=competitions)
                           