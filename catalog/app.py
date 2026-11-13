from flask import Flask, jsonify, request
import sqlite3
import os

# ==========================================
# Bazar.com - Catalog Microservice
# ==========================================

app = Flask(__name__)


# ==========================================
# Database Configuration
# ==========================================

DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "books.db")
)

os.makedirs(
    os.path.dirname(os.path.abspath(DB_PATH)),
    exist_ok=True
)


# ==========================================
# Database Connection
# ==========================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================
# Initialize Database
# ==========================================

def init_db():
    conn = get_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                quantity INTEGER NOT NULL CHECK(quantity >= 0)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_transactions (
                transaction_id TEXT PRIMARY KEY,
                item_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('decremented', 'restored')
                ),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    finally:
        conn.close()


# ==========================================
# Validate Transaction ID
# ==========================================

def get_transaction_id():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None

    transaction_id = data.get("transaction_id")

    if not isinstance(transaction_id, str):
        return None

    transaction_id = transaction_id.strip()

    if not transaction_id or len(transaction_id) > 128:
        return None

    return transaction_id


# ==========================================
# Search Books by Topic
# ==========================================

@app.route("/search/<topic>", methods=["GET"])
def search(topic):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT id, title
            FROM books
            WHERE LOWER(topic) = LOWER(?)
            """,
            (topic,)
        ).fetchall()

        return jsonify([
            dict(row) for row in rows
        ]), 200

    finally:
        conn.close()


# ==========================================
# Get Book Information
# ==========================================

@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT title, quantity, price
            FROM books
            WHERE id = ?
            """,
            (item_id,)
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        return jsonify({
            "error": "Book not found"
        }), 404

    return jsonify(dict(row)), 200


# ==========================================
# Update Book Price or Stock
# ==========================================

@app.route("/update/<int:item_id>", methods=["PUT"])
def update_book(item_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "error": "Valid JSON data is required"
        }), 400

    if set(data) - {"price", "quantity"}:
        return jsonify({
            "error": "Unsupported update field"
        }), 400

    for field in ("price", "quantity"):
        if field in data:
            value = data[field]

            if isinstance(value, bool) or not isinstance(
                value, (int, float)
            ):
                return jsonify({
                    "error": f"Invalid {field}"
                }), 400

            if value < 0:
                return jsonify({
                    "error": f"{field} cannot be negative"
                }), 400

            if field == "quantity" and not isinstance(value, int):
                return jsonify({
                    "error": "Quantity must be an integer"
                }), 400

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        book = conn.execute(
            "SELECT id FROM books WHERE id = ?",
            (item_id,)
        ).fetchone()

        if book is None:
            conn.rollback()

            return jsonify({
                "error": "Book not found"
            }), 404

        if "price" in data:
            conn.execute(
                """
                UPDATE books
                SET price = ?
                WHERE id = ?
                """,
                (data["price"], item_id)
            )

        if "quantity" in data:
            conn.execute(
                """
                UPDATE books
                SET quantity = ?
                WHERE id = ?
                """,
                (data["quantity"], item_id)
            )

        conn.commit()

        return jsonify({
            "message": "Book updated successfully",
            "item_id": item_id
        }), 200

    except sqlite3.Error:
        conn.rollback()

        return jsonify({
            "error": "Database update failed"
        }), 500

    finally:
        conn.close()


# ==========================================
# Decrement Stock - Idempotent Transaction
# ==========================================

@app.route("/decrement/<int:item_id>", methods=["POST"])
def decrement_stock(item_id):
    transaction_id = get_transaction_id()

    if transaction_id is None:
        return jsonify({
            "error": "Valid transaction_id is required"
        }), 400

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        existing = conn.execute(
            """
            SELECT item_id, status
            FROM stock_transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,)
        ).fetchone()

        # Prevent duplicate stock decrement
        if existing is not None:

            if existing["item_id"] != item_id:
                conn.rollback()

                return jsonify({
                    "error": "Transaction ID belongs to another book"
                }), 409

            if existing["status"] == "restored":
                conn.rollback()

                return jsonify({
                    "error": "Transaction already restored"
                }), 409

            book = conn.execute(
                """
                SELECT title, price, quantity
                FROM books
                WHERE id = ?
                """,
                (item_id,)
            ).fetchone()

            conn.rollback()

            return jsonify({
                "message": "Transaction already processed",
                "transaction_id": transaction_id,
                "item_id": item_id,
                "title": book["title"],
                "price": book["price"],
                "remaining_quantity": book["quantity"],
                "already_processed": True
            }), 200

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

            return jsonify({
                "error": "Book not found"
            }), 404

        if book["quantity"] <= 0:
            conn.rollback()

            return jsonify({
                "error": "Out of stock"
            }), 409

        cursor = conn.execute(
            """
            UPDATE books
            SET quantity = quantity - 1
            WHERE id = ? AND quantity > 0
            """,
            (item_id,)
        )

        if cursor.rowcount != 1:
            conn.rollback()

            return jsonify({
                "error": "Out of stock"
            }), 409

        conn.execute(
            """
            INSERT INTO stock_transactions (
                transaction_id,
                item_id,
                status
            )
            VALUES (?, ?, 'decremented')
            """,
            (transaction_id, item_id)
        )

        conn.commit()

        return jsonify({
            "message": "Stock decremented successfully",
            "transaction_id": transaction_id,
            "item_id": item_id,
            "title": book["title"],
            "price": book["price"],
            "remaining_quantity": book["quantity"] - 1,
            "already_processed": False
        }), 200

    except sqlite3.Error:
        conn.rollback()

        return jsonify({
            "error": "Database transaction failed"
        }), 500

    finally:
        conn.close()


# ==========================================
# Restore Stock - Idempotent Compensation
# ==========================================

@app.route("/restore/<int:item_id>", methods=["POST"])
def restore_stock(item_id):
    transaction_id = get_transaction_id()

    if transaction_id is None:
        return jsonify({
            "error": "Valid transaction_id is required"
        }), 400

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        transaction = conn.execute(
            """
            SELECT item_id, status
            FROM stock_transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,)
        ).fetchone()

        if transaction is None:
            conn.rollback()

            return jsonify({
                "error": "Transaction not found"
            }), 404

        if transaction["item_id"] != item_id:
            conn.rollback()

            return jsonify({
                "error": "Transaction ID belongs to another book"
            }), 409

        book = conn.execute(
            """
            SELECT title, quantity
            FROM books
            WHERE id = ?
            """,
            (item_id,)
        ).fetchone()

        if book is None:
            conn.rollback()

            return jsonify({
                "error": "Book not found"
            }), 404

        # Prevent duplicate restoration
        if transaction["status"] == "restored":
            conn.rollback()

            return jsonify({
                "message": "Stock already restored",
                "transaction_id": transaction_id,
                "item_id": item_id,
                "remaining_quantity": book["quantity"],
                "already_restored": True
            }), 200

        cursor = conn.execute(
            """
            UPDATE books
            SET quantity = quantity + 1
            WHERE id = ?
            """,
            (item_id,)
        )

        if cursor.rowcount != 1:
            conn.rollback()

            return jsonify({
                "error": "Stock restoration failed"
            }), 500

        conn.execute(
            """
            UPDATE stock_transactions
            SET status = 'restored'
            WHERE transaction_id = ?
            """,
            (transaction_id,)
        )

        conn.commit()

        return jsonify({
            "message": "Stock restored successfully",
            "transaction_id": transaction_id,
            "item_id": item_id,
            "title": book["title"],
            "remaining_quantity": book["quantity"] + 1,
            "already_restored": False
        }), 200

    except sqlite3.Error:
        conn.rollback()

        return jsonify({
            "error": "Stock restoration failed"
        }), 500

    finally:
        conn.close()


# ==========================================
# Start Catalog Microservice
# ==========================================

if __name__ == "__main__":
    init_db()

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )