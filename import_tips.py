import pandas as pd
from datetime import datetime
from main import app       # nebo jak spouštíš Flask
from extensions import db
from models import User, Match, Prediction

# 1) Context Flasku
app.app_context().push()

# 2) Načti data
df = pd.read_csv('import_vysledky.csv', sep=';')
print("Sloupce v souboru:", list(df.columns))

# 3) Najdi uživatele Mário
user = User.query.filter_by(username='Sugar').first()
if not user:
    raise RuntimeError("Uživatel 'Mário' nenalezen!")

imported = 0
skipped = 0

# 4) Pro každý řádek najdi odpovídající match a vytvoř/aktualizuj Prediction
for idx, row in df.iterrows():
    home = row['HOME'].strip()
    away = row['AWAY'].strip()
    try:
        ph = int(row['PRED_HOME'])
        pa = int(row['PRED_AWAY'])
    except ValueError:
        print(f"Řádek {idx}: neplatný formát skóre, přeskočeno")
        skipped += 1
        continue

    # Hledání existujícího zápasu
    match = Match.query.filter_by(team_home=home, team_away=away).first()
    if not match:
        print(f"Řádek {idx}: zápas {home}–{away} nenalezen, přeskočeno")
        skipped += 1
        continue

    # Vytvoř nebo updejtuje tip
    pred = Prediction.query.filter_by(user_id=user.id, match_id=match.id).first()
    if pred:
        pred.predicted_home = ph
        pred.predicted_away = pa
    else:
        pred = Prediction(
            user_id=user.id,
            match_id=match.id,
            predicted_home=ph,
            predicted_away=pa
        )
        db.session.add(pred)

    imported += 1

# 5) Commit jednou na konec
db.session.commit()
print(f"Hotovo – importováno: {imported}, přeskočeno: {skipped}")
