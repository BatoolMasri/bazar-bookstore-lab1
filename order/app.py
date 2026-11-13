from flask import Flask, jsonify
import sqlite3
import os
import uuid
import requests

# ==========================================
# Bazar.com - Order Microservice
# ==========================================

app = Flask(__name__)


# ==========================================
# Configuration
# ==========================================

CATALOG_URL = os.getenv(
    "CATALOG_URL",
    "http://127.0.0.1:5001"
)

DB_PATH = os.getenv(
    "ORDER_DB_PATH",
    os.path.join(os.path.dirname(__file__), "orders.db")
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
        # Existing orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                book_title TEXT NOT NULL,
                price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Persistent purchase transaction log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchase_transactions (
                transaction_id TEXT PRIMARY KEY,
                item_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN (
                        'pending',
                        'decrement_requested',
                        'stock_decremented',
                        'completed',
                        'compensation_pending',
                        'compensated',
                        'needs_review'
                    )
                ),
                order_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

    finally:
        conn.close()


# ==========================================
# Update Transaction Status
# ==========================================

def update_transaction(
    transaction_id,
    status,
    order_id=None,
    details=None
):
    conn = get_connection()

    try:
        conn.execute(
            """
            UPDATE purchase_transactions
            SET status = ?,
                order_id = COALESCE(?, order_id),
                details = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (
                status,
                order_id,
                details,
                transaction_id
            )
        )

        conn.commit()

    finally:
        conn.close()


# ==========================================
# Record New Transaction
# ==========================================

def create_transaction(transaction_id, item_id):
    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO purchase_transactions (
                transaction_id,
                item_id,
                status
            )
            VALUES (?, ?, 'pending')
            """,
            (transaction_id, item_id)
        )

        conn.commit()

    finally:
        conn.close()


# ==========================================
# Health Check
# ==========================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "order",
        "status": "running"
    }), 200


# ==========================================
# Get Transaction Status
# ==========================================

@app.route(
    "/transactions/<transaction_id>",
    methods=["GET"]
)
def transaction_status(transaction_id):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT
                transaction_id,
                item_id,
                status,
                order_id,
                details,
                created_at,
                updated_at
            FROM purchase_transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,)
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        return jsonify({
            "error": "Transaction not found"
        }), 404

    return jsonify(dict(row)), 200


# ==========================================
# Compensate Failed Purchase
# ==========================================

def compensate_purchase(transaction_id, item_id):
    """
    Attempt to restore stock after order storage fails.

    Catalog uses transaction_id to prevent duplicate
    restoration of the same stock transaction.
    """

    try:
        response = requests.post(
            f"{CATALOG_URL}/restore/{item_id}",
            json={
                "transaction_id": transaction_id
            },
            timeout=5
        )

    except requests.RequestException:
        return False

    if response.status_code != 200:
        return False

    try:
        result = response.json()

        return result.get("transaction_id") == transaction_id

    except (ValueError, TypeError):
        return False


# ==========================================
# Purchase Book
# ==========================================

@app.route("/purchase/<int:item_id>", methods=["POST"])
def purchase_book(item_id):

    # --------------------------------------
    # Step 1: Generate unique transaction ID
    # --------------------------------------

    transaction_id = str(uuid.uuid4())

    # --------------------------------------
    # Step 2: Persist transaction before
    # contacting Catalog Service
    # --------------------------------------

    try:
        create_transaction(
            transaction_id,
            item_id
        )

    except sqlite3.Error:
        return jsonify({
            "error": "Failed to initialize purchase"
        }), 500

    # --------------------------------------
    # Step 3: Mark decrement as requested
    # --------------------------------------

    try:
        update_transaction(
            transaction_id,
            "decrement_requested"
        )

    except sqlite3.Error:
        return jsonify({
            "error": "Failed to prepare purchase",
            "transaction_id": transaction_id
        }), 500

    # --------------------------------------
    # Step 4: Request stock decrement
    # --------------------------------------

    try:
        response = requests.post(
            f"{CATALOG_URL}/decrement/{item_id}",
            json={
                "transaction_id": transaction_id
            },
            timeout=5
        )

    except requests.RequestException:

        # The request might have reached Catalog.
        # We cannot safely assume stock was unchanged.

        try:
            update_transaction(
                transaction_id,
                "needs_review",
                details="Catalog request outcome unknown"
            )
        except sqlite3.Error:
            pass

        return jsonify({
            "error": "Catalog Service unavailable",
            "transaction_id": transaction_id,
            "status": "needs_review"
        }), 503

    # --------------------------------------
    # Step 5: Handle Catalog errors
    # --------------------------------------

    if response.status_code == 404:

        update_transaction(
            transaction_id,
            "compensated",
            details="Book not found; no stock changed"
        )

        return jsonify({
            "error": "Book not found"
        }), 404

    if response.status_code == 409:

        update_transaction(
            transaction_id,
            "compensated",
            details="Catalog rejected purchase"
        )

        return jsonify({
            "error": "Out of stock"
        }), 409

    if response.status_code != 200:

        update_transaction(
            transaction_id,
            "needs_review",
            details="Unexpected Catalog response"
        )

        return jsonify({
            "error": "Catalog Service error",
            "transaction_id": transaction_id
        }), 503

    # --------------------------------------
    # Step 6: Validate Catalog response
    # --------------------------------------

    try:
        book = response.json()

        if book.get("transaction_id") != transaction_id:
            raise ValueError("Transaction ID mismatch")

        title = book["title"]
        price = book["price"]
        remaining_quantity = book["remaining_quantity"]

    except (ValueError, KeyError, TypeError):

        update_transaction(
            transaction_id,
            "needs_review",
            details="Invalid Catalog response"
        )

        return jsonify({
            "error": "Invalid response from Catalog Service",
            "transaction_id": transaction_id
        }), 502

    # --------------------------------------
    # Step 7: Mark stock as decremented
    # --------------------------------------

    try:
        update_transaction(
            transaction_id,
            "stock_decremented"
        )

    except sqlite3.Error:

        # Stock was decremented, but the local
        # transaction state could not be updated.

        return jsonify({
            "error": "Failed to update purchase state",
            "transaction_id": transaction_id,
            "status": "needs_review"
        }), 500

    # --------------------------------------
    # Step 8: Save order to SQLite
    # --------------------------------------

    conn = None

    try:
        conn = get_connection()

        conn.execute("BEGIN IMMEDIATE")

        cursor = conn.execute(
            """
            INSERT INTO orders (
                item_id,
                book_title,
                price
            )
            VALUES (?, ?, ?)
            """,
            (
                item_id,
                title,
                price
            )
        )

        order_id = cursor.lastrowid

        # Save the order and completion status
        # in the SAME SQLite transaction.

        conn.execute(
            """
            UPDATE purchase_transactions
            SET status = 'completed',
                order_id = ?,
                details = 'Purchase completed',
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (
                order_id,
                transaction_id
            )
        )

        conn.commit()

    except sqlite3.Error:

        if conn is not None:
            conn.rollback()

        # ----------------------------------
        # Step 9: Attempt compensation
        # ----------------------------------

        try:
            update_transaction(
                transaction_id,
                "compensation_pending",
                details="Order storage failed"
            )
        except sqlite3.Error:
            pass

        restored = compensate_purchase(
            transaction_id,
            item_id
        )

        if restored:

            try:
                update_transaction(
                    transaction_id,
                    "compensated",
                    details="Stock restored after order failure"
                )
            except sqlite3.Error:
                pass

            return jsonify({
                "error": "Failed to save order",
                "transaction_id": transaction_id,
                "stock_restored": True
            }), 500

        try:
            update_transaction(
                transaction_id,
                "needs_review",
                details="Order failed; compensation unconfirmed"
            )
        except sqlite3.Error:
            pass

        return jsonify({
            "error": "Failed to save order",
            "transaction_id": transaction_id,
            "stock_restored": False,
            "status": "needs_review"
        }), 500

    finally:
        if conn is not None:
            conn.close()

    # --------------------------------------
    # Step 10: Successful purchase
    # --------------------------------------

    # Required Lab 1 purchase output message.
    # Print only after the order is saved successfully.
    print(f"bought book {title}", flush=True)

    return jsonify({
        "message": "Purchase successful",
        "transaction_id": transaction_id,
        "order_id": order_id,
        "item_id": item_id,
        "title": title,
        "price": price,
        "remaining_quantity": remaining_quantity
    }), 200


# ==========================================
# Main Application
# ==========================================

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )