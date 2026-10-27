from flask import Flask, jsonify
import sqlite3
import os

app = Flask(__name__)

# Database path - supports Docker persistent storage
DB_PATH = os.getenv(
    "ORDER_DB_PATH",
    os.path.join(os.path.dirname(__file__), "orders.db")
)

# Ensure database directory exists
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)


# Connect to SQLite database
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize orders database
def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            book_title TEXT NOT NULL,
            price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# Health check endpoint
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "order",
        "status": "running"
    }), 200


if __name__ == "__main__":
    init_db()

    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )