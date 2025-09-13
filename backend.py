"""
Simple single-file Flask wellness app (~100 lines)
Features:
- Daily mood check-ins (text + rating)
- Lightweight sentiment analysis (lexicon-based)
- Personalized recommendations based on mood/sentiment
- Trend visualization using Chart.js (endpoint /data)
- Stores entries in SQLite
"""
from flask import Flask, request, g, jsonify, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime
import statistics

DB = 'wellness.db'
app = Flask(__name__)

# --- tiny lexicon-based sentiment ---
POSITIVE = set("happy good great awesome calm relaxed grateful energetic motivated hopeful".split())
NEGATIVE = set("sad depressed anxious stressed angry lonely tired hopeless".split())

def score_sentiment(text):
    if not text:
        return 0.0
    tokens = [w.strip('.,!?').lower() for w in text.split()]
    pos = sum(1 for t in tokens if t in POSITIVE)
    neg = sum(1 for t in tokens if t in NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total

# --- simple recommendations ---
def recommendation(rating, sentiment, text):
    tips = []
    if rating <= 3 or sentiment < -0.2:
        tips.append('Try a 5-minute breathing exercise or short walk.')
        tips.append('If this persists, consider reaching out to a friend or professional.')
    else:
        tips.append('Great! Keep a short gratitude list today.')
    if 'sleep' in text.lower():
        tips.append('Aim for consistent sleep schedule — wind down 30 mins before bed.')
    return tips

# --- database helpers ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB)
    db.execute('''CREATE TABLE IF NOT EXISTS entries(
                    id INTEGER PRIMARY KEY, date TEXT, rating INTEGER, note TEXT, sentiment REAL)
                ''')
    db.commit()
    db.close()

# --- routes ---
INDEX = '''
<!doctype html>
<title>Wellness Check-in</title>
<h2>Daily Mood Check-in</h2>
<form method=post action="/submit">
  Rating (1-5): <input name=rating type=number min=1 max=5 required><br>
  Note: <br><textarea name=note rows=3 cols=40></textarea><br>
  <button type=submit>Submit</button>
</form>
<div id="rec"></div>
<hr>
<canvas id="chart" width=600 height=200></canvas>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
async function loadData(){
  const res = await fetch('/data');
  const js = await res.json();
  const labels = js.map(r=>r.date);
  const ratings = js.map(r=>r.rating);
  const ctx = document.getElementById('chart').getContext('2d');
  new Chart(ctx,{type:'line',data:{labels:labels,datasets:[{label:'Mood rating',data:ratings,fill:false}]}});
}
loadData();
</script>
'''

@app.route('/')
def home():
    return render_template_string(INDEX)

@app.route('/submit', methods=['POST'])
def submit():
    rating = int(request.form['rating'])
    note = request.form.get('note','')
    sent = score_sentiment(note)
    db = get_db()
    db.execute('INSERT INTO entries(date,rating,note,sentiment) VALUES(?,?,?,?)',
               (datetime.utcnow().isoformat(), rating, note, sent))
    db.commit()
    tips = recommendation(rating, sent, note)
    # show simple page with tips and back link
    return render_template_string('<h3>Thanks — Saved!</h3>'
                                  '<p>Recommendations:</p><ul>' + ''.join(f'<li>{t}</li>' for t in tips) +
                                  '</ul><a href="/">Back</a>')

@app.route('/data')
def data():
    cur = get_db().execute('SELECT date,rating FROM entries ORDER BY id ASC')
    rows = cur.fetchall()
    out = [{'date': r['date'][:10], 'rating': r['rating']} for r in rows]
    return jsonify(out)

@app.route('/summary')
def summary():
    cur = get_db().execute('SELECT rating, sentiment FROM entries')
    rows = cur.fetchall()
    if not rows:
        return jsonify({'count':0})
    ratings = [r['rating'] for r in rows]
    sents = [r['sentiment'] for r in rows]
    return jsonify({
        'count': len(rows),
        'avg_rating': statistics.mean(ratings),
        'median_rating': statistics.median(ratings),
        'avg_sentiment': statistics.mean(sents)
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
