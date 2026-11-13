# Bazar.com – Lab 1 Design Documentation

**Course:** Distributed and Operating Systems  
**Project:** Multi-tier Online Book Store  
**Contributor:** Raana Saadaldein  
**Components:** Order Service, Catalog Updates, Transaction Management, Docker Compose, and Integration Testing

## 1. System Architecture and Integration

Bazar.com is a distributed online bookstore implemented using three independent Python Flask microservices:

- **Frontend Service (Port 5000):** Receives client requests and forwards them to the appropriate backend service.
- **Catalog Service (Port 5001):** Manages book information, prices, and available inventory.
- **Order Service (Port 5002):** Processes purchases, communicates with Catalog, and stores completed orders.

The services communicate through HTTP REST APIs using JSON.

Docker Compose orchestrates all three services in separate Linux containers. Docker service names are used for internal communication.

## 2. Order Microservice

The Order Service processes purchase requests through:

`POST /purchase/<item_id>`

When a purchase request is received, the service generates a unique transaction ID and contacts the Catalog Service to decrement the available stock.

If the stock update succeeds, the Order Service saves the purchase information in its SQLite database.

Successful purchases return HTTP 200, including the order ID, item ID, price, remaining quantity, and transaction ID.

The service also provides:

`GET /health`

This endpoint returns the service's running status.

Order data is stored in SQLite using the configurable `ORDER_DB_PATH` environment variable.

## 3. Catalog Inventory Updates

The Catalog Service was extended with inventory management endpoints:

| Method | Endpoint | Description |
|---|---|---|
| PUT | `/update/<item_id>` | Update book price or quantity |
| POST | `/decrement/<item_id>` | Decrease available stock |
| POST | `/restore/<item_id>` | Restore stock after a failed purchase |

SQLite transactions are used to protect inventory modifications.

The decrement operation uses `BEGIN IMMEDIATE` to serialize competing database writes.

This prevents multiple concurrent requests from purchasing more copies than the available quantity.

## 4. Transaction Management and Compensation

Each purchase receives a unique transaction ID.

The Catalog Service records processed stock transactions to support idempotent operations. Repeated decrement requests using the same transaction ID do not reduce the stock multiple times.

If Catalog successfully decreases the stock but Order fails to save the purchase, the Order Service attempts to compensate by calling Catalog's restore endpoint.

The restore operation is also designed to be idempotent.

A simulated database failure test confirmed that stock was restored and no incomplete order was saved.

This approach provides application-level compensation rather than a distributed database transaction.

## 5. Docker Compose Deployment

Docker Compose manages the three microservices:

| Service | Port | Persistent Storage |
|---|---|---|
| Frontend | 5000 | Not required |
| Catalog | 5001 | `catalog_data` |
| Order | 5002 | `order_data` |

Environment variables configure communication between services.

The Catalog and Order databases are stored in Docker named volumes, allowing data to survive container removal and recreation.

Deployment was verified using:

`docker compose up -d`

All three services started successfully and communicated through the Docker network.

## 6. Testing and Results

The integrated system was tested using HTTP requests, Python scripts, Docker commands, and SQLite queries.

| Test | Result |
|---|---|
| End-to-end purchase | Passed |
| Order SQLite persistence | Passed |
| Docker Compose deployment | Passed |
| Docker volume persistence | Passed |
| Concurrent purchases | Passed |
| Prevention of overselling | Passed |
| Automatic stock compensation | Passed |
| Catalog failure and recovery | Passed |
| Order failure and recovery | Passed |

### Concurrent Purchase Test

Ten concurrent purchase requests were sent through the Frontend Service for a book with four available copies.

Results:

- Successful purchases: 4
- Out-of-stock responses: 6
- Other errors: 0
- Final stock: 0

SQLite verification confirmed that all four new successful purchases were saved.

### Failure and Recovery Tests

Stopping the Catalog Service caused the Frontend to return HTTP 503. After restarting Catalog, the same information request returned HTTP 200.

Stopping the Order Service caused purchase requests through the Frontend to return HTTP 503.

After restarting Order, its health endpoint returned HTTP 200.

Detailed test results are recorded in `docs/raana-output.txt`.

## 7. Design Decisions and Limitations

SQLite was selected for lightweight persistent storage. Transactions protect inventory updates from concurrent modifications.

Unique transaction IDs and idempotent stock operations reduce the risk of duplicate inventory changes.

Docker Compose simplifies deployment and service communication.

However, the system has limitations:

- Flask's development server is not intended for production deployment.
- Docker Compose startup dependencies do not guarantee application readiness.
- Network failures can create uncertain transaction outcomes.
- The compensation mechanism does not provide the same guarantees as a fully coordinated distributed transaction.
- The current implementation is intended for a laboratory environment rather than production use.

Future improvements could include retry policies, transaction recovery procedures, centralized logging, automated health checks, and production-ready application servers.

---

**Integration Note:** This document complements `batool-design.md`. The final submission should combine both contributors' work into one consistent 2–3-page design report.