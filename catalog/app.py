
from flask import Flask, jsonify
import sqlite3
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "books.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        )
    """)

    count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    if count == 0:
        books = [
            (1, "How to get a good grade in DOS in 40 minutes a day",
             "distributed systems", 40, 10),
            (2, "RPCs for Noobs",
             "distributed systems", 50, 5),
            (3, "Xen and the Art of Surviving Undergraduate School",
             "undergraduate school", 35, 8),
            (4, "Cooking for the Impatient Undergrad",
             "undergraduate school", 25, 12)
        ]

        conn.executemany(
            "INSERT INTO books (id, title, topic, price, quantity) VALUES (?, ?, ?, ?, ?)",
            books
        )

    conn.commit()
    conn.close()


@app.route("/search/<topic>", methods=["GET"])
def search(topic):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title FROM books WHERE LOWER(topic) = LOWER(?)",
        (topic,)
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT title, quantity, price FROM books WHERE id = ?",
        (item_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Book not found"}), 404

    return jsonify(dict(row))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
