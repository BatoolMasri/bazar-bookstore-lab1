import os
import sys
import sqlite3
import tempfile

from unittest.mock import patch
from urllib.parse import urlparse

# ==========================================
# Bazar.com - Order Compensation Test
# ==========================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

from catalog import app as catalog_module
from order import app as order_module


# ==========================================
# Fake HTTP Response
# ==========================================

class FakeResponse:

    def __init__(self, flask_response):
        self.status_code = flask_response.status_code
        self._data = flask_response.get_json()

    def json(self):
        return self._data


# ==========================================
# Simulate HTTP Calls to Catalog
# ==========================================

def create_fake_post(catalog_client):

    def fake_post(url, json=None, timeout=None):

        parsed = urlparse(url)

        # Only allow Catalog endpoints
        if parsed.path.startswith("/decrement/"):
            response = catalog_client.post(
                parsed.path,
                json=json
            )

        elif parsed.path.startswith("/restore/"):
            response = catalog_client.post(
                parsed.path,
                json=json
            )

        else:
            raise AssertionError(
                f"Unexpected HTTP request: {url}"
            )

        return FakeResponse(response)

    return fake_post


# ==========================================
# Simulate Order Database Failure
# ==========================================

class FailingConnection:

    def __init__(self, real_connection):
        self.real_connection = real_connection

    def execute(self, sql, params=()):

        # Simulate failure only when saving an order
        if "INSERT INTO orders" in sql:
            raise sqlite3.OperationalError(
                "Simulated order storage failure"
            )

        return self.real_connection.execute(
            sql,
            params
        )

    def __getattr__(self, name):
        return getattr(
            self.real_connection,
            name
        )


# ==========================================
# Main Compensation Test
# ==========================================

def test_compensation():

    with tempfile.TemporaryDirectory() as temp_dir:

        # Temporary databases
        catalog_db = os.path.join(
            temp_dir,
            "test_books.db"
        )

        order_db = os.path.join(
            temp_dir,
            "test_orders.db"
        )

        # Replace real database paths
        with patch.object(
            catalog_module,
            "DB_PATH",
            catalog_db
        ), patch.object(
            order_module,
            "DB_PATH",
            order_db
        ):

            # Initialize temporary databases
            catalog_module.init_db()
            order_module.init_db()

            # Create Flask test clients
            catalog_client = (
                catalog_module.app.test_client()
            )

            order_client = (
                order_module.app.test_client()
            )

            # ----------------------------------
            # Check stock before purchase
            # ----------------------------------

            initial_response = catalog_client.get(
                "/info/2"
            )

            initial_stock = initial_response.get_json()[
                "quantity"
            ]

            print(
                "INITIAL STOCK:",
                initial_stock
            )

            # ----------------------------------
            # Mock HTTP communication
            # ----------------------------------

            fake_post = create_fake_post(
                catalog_client
            )

            original_get_connection = (
                order_module.get_connection
            )

            def failing_connection():

                return FailingConnection(
                    original_get_connection()
                )

            # ----------------------------------
            # Run purchase with simulated failure
            # ----------------------------------

            with patch.object(
                order_module.requests,
                "post",
                side_effect=fake_post
            ), patch.object(
                order_module,
                "get_connection",
                side_effect=failing_connection
            ):

                response = order_client.post(
                    "/purchase/2"
                )

            result = response.get_json()

            print(
                "HTTP STATUS:",
                response.status_code
            )

            print(
                "PURCHASE RESPONSE:",
                result
            )

            # ----------------------------------
            # Check stock after compensation
            # ----------------------------------

            final_response = catalog_client.get(
                "/info/2"
            )

            final_stock = final_response.get_json()[
                "quantity"
            ]

            print(
                "FINAL STOCK:",
                final_stock
            )

            # ----------------------------------
            # Check transaction status
            # ----------------------------------

            conn = sqlite3.connect(order_db)

            transaction = conn.execute(
                """
                SELECT transaction_id, status
                FROM purchase_transactions
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()

            order_count = conn.execute(
                "SELECT COUNT(*) FROM orders"
            ).fetchone()[0]

            conn.close()

            print(
                "TRANSACTION:",
                transaction
            )

            print(
                "ORDERS SAVED:",
                order_count
            )

            # ----------------------------------
            # Assertions
            # ----------------------------------

            assert response.status_code == 500

            assert result["stock_restored"] is True

            assert initial_stock == final_stock

            assert transaction is not None

            assert transaction[1] == "compensated"

            assert order_count == 0

            print(
                "\nTEST PASSED: "
                "Automatic compensation successful"
            )


# ==========================================
# Run Test
# ==========================================

if __name__ == "__main__":
    test_compensation()