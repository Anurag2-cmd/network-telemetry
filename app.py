"""Flask dashboard: serves the web UI and telemetry data from SQLite."""

import sqlite3
import time

from flask import Flask, jsonify, render_template

app = Flask(__name__)
DB_PATH = "telemetry.db"


def query_samples(seconds=7200):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM samples WHERE ts >= ? ORDER BY ts",
        (int(time.time()) - seconds,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    return jsonify(query_samples())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
