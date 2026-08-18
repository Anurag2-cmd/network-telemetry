"""Unified telemetry dashboard (task 10).

One Flask app with a tab per telemetry protocol — INT / sFlow / NetFlow /
IPFIX / SNMP / gNMI — all reading from db/telemetry.db (written by the
collectors of tasks 5-9). Charts poll /api/<source> every 5 s without a
page reload; /api/status drives the green/red live badges.

Run inside WSL from the project dir:
    python3 dashboard/app.py
Then open http://localhost:5000 from Windows.
"""

from flask import Flask, jsonify, render_template

from db import SOURCES, last_rows, status

app = Flask(__name__)

MAX_ROWS = 200


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/<source>")
def api_source(source):
    table = SOURCES.get(source)
    if table is None:
        return jsonify({"error": "unknown source"}), 404
    return jsonify(last_rows(table, MAX_ROWS))


@app.route("/api/status")
def api_status():
    return jsonify(status())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)