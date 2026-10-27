from flask import Flask, jsonify, request
import sqlite3
import os

app = Flask(__name__)

# Database path - supports Docker persistent storage
DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "books.db")
)

os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)


# Connect to SQLite database
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize database and insert initial books
def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            quantity INTEGER NOT NULL CHECK(quantity >= 0)
        )
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    if count == 0:
        books = [
            (
                1,
                "How to get a good grade in DOS in 40 minutes a day",
                "distributed systems",
                40,
                10
            ),
            (
                2,
                "RPCs for Noobs",
                "distributed systems",
                50,
                5
            ),
            (
                3,
                "Xen and the Art of Surviving Undergraduate School",
                "undergraduate school",
                35,
                8
            ),
            (
                4,
                "Cooking for the Impatient Undergrad",
                "undergraduate school",
                25,
                12
            )
        ]

        conn.executemany("""
            INSERT INTO books
            (id, title, topic, price, quantity)
            VALUES (?, ?, ?, ?, ?)
        """, books)

    conn.commit()
    conn.close()


# Search books by topic
@app.route("/search/<topic>", methods=["GET"])
def search(topic):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, title
        FROM books
        WHERE LOWER(topic) = LOWER(?)
        """,
        (topic,)
    ).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows]), 200


# Get book information by ID
@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT title, quantity, price
        FROM books
        WHERE id = ?
        """,
        (item_id,)
    ).fetchone()

    conn.close()

    if row is None:
        return jsonify({"error": "Book not found"}), 404

    return jsonify(dict(row)), 200


# Update book price or stock quantity
@app.route("/update/<int:item_id>", methods=["PUT"])
def update_book(item_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Valid JSON data is required"}), 400

    if set(data) - {"price", "quantity"}:
        return jsonify({"error": "Unsupported update field"}), 400

    for field in ("price", "quantity"):
        if field in data:
            value = data[field]

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return jsonify({"error": f"Invalid {field}"}), 400

            if value < 0:
                return jsonify({"error": f"{field} cannot be negative"}), 400

            if field == "quantity" and not isinstance(value, int):
                return jsonify({"error": "Quantity must be an integer"}), 400

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        book = conn.execute(
            "SELECT id FROM books WHERE id = ?",
            (item_id,)
        ).fetchone()

        if book is None:
            conn.rollback()
            return jsonify({"error": "Book not found"}), 404

        if "price" in data:
            conn.execute(
                "UPDATE books SET price = ? WHERE id = ?",
                (data["price"], item_id)
            )

        if "quantity" in data:
            conn.execute(
                "UPDATE books SET quantity = ? WHERE id = ?",
                (data["quantity"], item_id)
            )

        conn.commit()

        return jsonify({
            "message": "Book updated successfully",
            "item_id": item_id
        }), 200

    except sqlite3.Error:
        conn.rollback()
        return jsonify({"error": "Database update failed"}), 500

    finally:
        conn.close()


# Atomically purchase one book from stock
@app.route("/decrement/<int:item_id>", methods=["POST"])
def decrement_stock(item_id):
    conn = get_connection()

    try:
        # Acquire a write lock before checking stock
        conn.execute("BEGIN IMMEDIATE")

        book = conn.execute(
            """
            SELECT title, price, quantity
            FROM books
            WHERE id = ?
            """,
            (item_id,)
        ).fetchone()

        if book is None:
            conn.rollback()
            return jsonify({"error": "Book not found"}), 404

        if book["quantity"] <= 0:
            conn.rollback()
            return jsonify({"error": "Out of stock"}), 409

        # Conditional update prevents negative stock
        conn.execute(
            """
            UPDATE books
            SET quantity = quantity - 1
            WHERE id = ? AND quantity > 0
            """,
            (item_id,)
        )

        conn.commit()

        return jsonify({
            "message": "Stock decremented successfully",
            "item_id": item_id,
            "title": book["title"],
            "price": book["price"],
            "remaining_quantity": book["quantity"] - 1
        }), 200

    except sqlite3.Error:
        conn.rollback()
        return jsonify({"error": "Database transaction failed"}), 500

    finally:
        conn.close()


# Start the Catalog microservice
if __name__ == "__main__":
    init_db()

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )