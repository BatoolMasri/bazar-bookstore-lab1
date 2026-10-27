
from flask import Flask, jsonify
import requests
import os

app = Flask(__name__)

CATALOG_URL = os.getenv("CATALOG_URL", "http://127.0.0.1:5001")
ORDER_URL = os.getenv("ORDER_URL", "http://127.0.0.1:5002")


@app.route("/search/<topic>", methods=["GET"])
def search(topic):
    try:
        response = requests.get(
            f"{CATALOG_URL}/search/{topic}",
            timeout=5
        )
        return jsonify(response.json()), response.status_code
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Catalog service unavailable or invalid response"}), 503


@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    try:
        response = requests.get(
            f"{CATALOG_URL}/info/{item_id}",
            timeout=5
        )
        return jsonify(response.json()), response.status_code
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Catalog service unavailable or invalid response"}), 503


@app.route("/purchase/<int:item_id>", methods=["POST"])
def purchase(item_id):
    try:
        response = requests.post(
            f"{ORDER_URL}/purchase/{item_id}",
            timeout=5
        )
        return jsonify(response.json()), response.status_code
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Order service unavailable or invalid response"}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
