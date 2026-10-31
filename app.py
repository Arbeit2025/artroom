"""お部屋美術館 artroom

パブリックドメインの有名絵画を全画面で自動切替表示する小さな美術館。
「今日の1枚」は JST の日付で決定的に選ばれ、閲覧履歴を SQLite に残す。
画像本体は Wikimedia Commons へのホットリンクで表示する。
単一ファイル Flask + SQLite。
"""
import os
import sqlite3
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, render_template_string, abort, request

app = Flask(__name__)
JST = ZoneInfo("Asia/Tokyo")
DB_PATH = os.environ.get("ARTROOM_DB", os.path.join(os.path.dirname(__file__), "artroom.db"))
COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/"

# パブリックドメインの有名絵画（ファイル名は Wikimedia Commons 上のもの）
ARTWORKS = [
    {"title": "神奈川沖浪裏", "artist": "葛飾北斎", "year": "1831年頃",
     "file": "Great Wave off Kanagawa2.jpg"},
    {"title": "凱風快晴（赤富士）", "artist": "葛飾北斎", "year": "1830年頃",
     "file": "Red Fuji southern wind clear morning.jpg"},
    {"title": "星月夜", "artist": "フィンセント・ファン・ゴッホ", "year": "1889年",
     "file": "Van Gogh - Starry Night - Google Art Project.jpg"},
    {"title": "ひまわり", "artist": "フィンセント・ファン・ゴッホ", "year": "1888年",
     "file": "Vincent van Gogh - Sunflowers - VGM F458.jpg"},
    {"title": "真珠の耳飾りの少女", "artist": "ヨハネス・フェルメール", "year": "1665年頃",
     "file": "1665 Girl with a Pearl Earring.jpg"},
    {"title": "モナ・リザ", "artist": "レオナルド・ダ・ヴィンチ", "year": "1503-1506年",
     "file": "Mona Lisa, by Leonardo da Vinci, from C2RMF retouched.jpg"},
    {"title": "印象、日の出", "artist": "クロード・モネ", "year": "1872年",
     "file": "Claude Monet, Impression, soleil levant.jpg"},
    {"title": "睡蓮の池、緑のハーモニー", "artist": "クロード・モネ", "year": "1899年",
     "file": "Claude Monet - The Japanese Footbridge, Giverny - Google Art Project.jpg"},
    {"title": "叫び", "artist": "エドヴァルド・ムンク", "year": "1893年",
     "file": "Edvard Munch, 1893, The Scream, oil, tempera and pastel on cardboard, 91 x 73 cm, National Gallery of Norway.jpg"},
    {"title": "ヴィーナスの誕生", "artist": "サンドロ・ボッティチェッリ", "year": "1485年頃",
     "file": "Sandro Botticelli - La nascita di Venere - Google Art Project.jpg"},
    {"title": "ムーラン・ド・ラ・ギャレットの舞踏会", "artist": "ピエール＝オーギュスト・ルノワール", "year": "1876年",
     "file": "Auguste Renoir - Dance at Le Moulin de la Galette - Google Art Project.jpg"},
    {"title": "接吻", "artist": "グスタフ・クリムト", "year": "1908年",
     "file": "The Kiss - Gustav Klimt - Google Cultural Institute.jpg"},
    {"title": "落穂拾い", "artist": "ジャン＝フランソワ・ミレー", "year": "1857年",
     "file": "Jean-François Millet - Gleaners - Google Art Project 2.jpg"},
    {"title": "真珠の首飾りの女", "artist": "ヨハネス・フェルメール", "year": "1664年頃",
     "file": "Jan Vermeer van Delft - Young Woman with a Pearl Necklace - Google Art Project.jpg"},
    {"title": "夜警", "artist": "レンブラント・ファン・レイン", "year": "1642年",
     "file": "The Night Watch - HD.jpg"},
    {"title": "ラス・メニーナス", "artist": "ディエゴ・ベラスケス", "year": "1656年",
     "file": "Las Meninas, by Diego Velázquez, from Prado in Google Earth.jpg"},
    {"title": "民衆を導く自由の女神", "artist": "ウジェーヌ・ドラクロワ", "year": "1830年",
     "file": "Eugène Delacroix - La liberté guidant le peuple.jpg"},
    {"title": "牛乳を注ぐ女", "artist": "ヨハネス・フェルメール", "year": "1658年頃",
     "file": "Johannes Vermeer - Het melkmeisje - Google Art Project.jpg"},
    {"title": "アテネの学堂", "artist": "ラファエロ・サンティ", "year": "1509-1511年",
     "file": "The School of Athens by Raffaello Sanzio da Urbino.jpg"},
]


def image_url(work):
    return COMMONS + quote(work["file"]) + "?width=1600"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            view_date TEXT NOT NULL,
            artwork_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            viewed_at TEXT NOT NULL,
            UNIQUE(view_date, artwork_index)
        );
        """
    )
    db.commit()
    db.close()


def record_view(idx):
    now = datetime.now(JST)
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO views(view_date, artwork_index, title, viewed_at) VALUES(?, ?, ?, ?)",
        (now.strftime("%Y-%m-%d"), idx, ARTWORKS[idx]["title"], now.strftime("%Y-%m-%d %H:%M")),
    )
    db.commit()


def todays_index():
    today = datetime.now(JST).date()
    return today.toordinal() % len(ARTWORKS)


BASE_HEAD = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>お部屋美術館</title>
<style>body{font-family:sans-serif;max-width:720px;margin:2em auto;padding:0 1em}
figure img{max-width:100%}figcaption{margin-top:.5em;color:#444}
table{border-collapse:collapse}td,th{border-bottom:1px solid #ccc;padding:.3em .6em}</style>
</head><body>
<h1>お部屋美術館</h1>
<nav><a href="/">今日の1枚</a> ｜ <a href="/slideshow">スライドショー</a> ｜ <a href="/history">閲覧履歴</a></nav>
"""

BASE_TAIL = """
</body></html>"""

TODAY_BODY = """
<h2>今日の1枚（{{ date }}）</h2>
<figure>
  <img src="{{ url }}" alt="{{ work.title }}">
  <figcaption>「{{ work.title }}」 {{ work.artist }}（{{ work.year }}）</figcaption>
</figure>
"""

SLIDESHOW = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>スライドショー - お部屋美術館</title>
<style>html,body{margin:0;height:100%;background:#000}
#stage{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
img{max-width:100%;max-height:100%;object-fit:contain}
#cap{position:fixed;left:0;right:0;bottom:0;color:#fff;background:rgba(0,0,0,.5);
padding:.6em 1em;font-family:sans-serif}</style></head>
<body>
<div id="stage"><img id="pic" src="" alt=""></div>
<div id="cap"></div>
<script>
const works = {{ works_json|safe }};
const intervalMs = {{ interval }} * 1000;
let i = 0;
function show() {
  const w = works[i];
  document.getElementById('pic').src = w.url;
  document.getElementById('cap').textContent = '「' + w.title + '」 ' + w.artist + '（' + w.year + '）';
  fetch('/api/record/' + w.index);
  i = (i + 1) % works.length;
}
show();
setInterval(show, intervalMs);
</script>
</body></html>"""

HISTORY_BODY = """
<h2>閲覧履歴</h2>
<table>
<tr><th>日付</th><th>作品</th><th>時刻</th></tr>
{% for v in views %}
<tr><td>{{ v.view_date }}</td><td>{{ v.title }}</td><td>{{ v.viewed_at }}</td></tr>
{% else %}<tr><td colspan="3">まだ履歴がありません</td></tr>
{% endfor %}
</table>
"""


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/")
def today():
    idx = todays_index()
    record_view(idx)
    work = ARTWORKS[idx]
    return render_template_string(
        BASE_HEAD + TODAY_BODY + BASE_TAIL,
        work=work,
        url=image_url(work),
        date=datetime.now(JST).strftime("%Y-%m-%d"),
    )


@app.route("/slideshow")
def slideshow():
    try:
        interval = int(request.args.get("interval", "30"))
    except (TypeError, ValueError):
        interval = 30
    interval = min(max(interval, 5), 3600)
    import json as _json

    works_json = _json.dumps(
        [
            {"index": i, "title": w["title"], "artist": w["artist"], "year": w["year"], "url": image_url(w)}
            for i, w in enumerate(ARTWORKS)
        ],
        ensure_ascii=False,
    )
    return render_template_string(SLIDESHOW, works_json=works_json, interval=interval)


@app.route("/api/record/<int:idx>")
def api_record(idx):
    if idx < 0 or idx >= len(ARTWORKS):
        abort(404)
    record_view(idx)
    return jsonify({"status": "recorded", "index": idx})


@app.route("/history")
def history():
    db = get_db()
    views = db.execute("SELECT * FROM views ORDER BY id DESC").fetchall()
    return render_template_string(BASE_HEAD + HISTORY_BODY + BASE_TAIL, views=views)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
