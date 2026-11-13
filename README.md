# Bazar.com — Multi-tier Online Book Store

**Course:** Distributed and Operating Systems  
**Lab:** Lab 1  
**Technology:** Python, Flask, SQLite, REST APIs, Docker, Docker Compose

## 1. Project Overview

Bazar.com is a distributed online bookstore implemented using three independent REST microservices.

The system allows clients to search for books, retrieve book information, and purchase available books.

The services communicate through HTTP requests and exchange data in JSON format.

## 2. System Architecture

The application consists of three services:

| Service | Port | Responsibility |
|---|---|---|
| Frontend | 5000 | Receives client requests and forwards them to backend services |
| Catalog | 5001 | Manages book information, prices, and inventory |
| Order | 5002 | Processes purchases and stores orders |

Communication flow:

```text
                   Client
                      |
                      v
              Frontend Service
                 Port 5000
                 /       \
                v         v
        Catalog Service  Order Service
           Port 5001       Port 5002
                ^             |
                |_____________|

           SQLite Databases
         (Catalog and Order)
```

The Order Service communicates with Catalog to update inventory when a purchase is requested.

## 3. Requirements

- Docker Desktop
- Docker Compose
- Git (optional, for cloning the repository)

Python does not need to be installed locally to run the services using Docker.

## 4. Running the Application

Open a terminal in the project directory.

Build and start the services:

```bash
docker compose up --build -d
```

Verify that the containers are running:

```bash
docker compose ps
```

Expected services:

- Frontend: port 5000
- Catalog: port 5001
- Order: port 5002

Stop the application:

```bash
docker compose down
```

**Important:** Do not use `docker compose down -v` unless you intentionally want to delete the persistent database volumes.

## 5. REST API Endpoints

### Frontend Service

| Method | Endpoint | Description |
|---|---|---|
| GET | `/search/<topic>` | Search books by topic |
| GET | `/info/<item_id>` | Retrieve book information |
| POST | `/purchase/<item_id>` | Purchase a book |

### Catalog Service

| Method | Endpoint | Description |
|---|---|---|
| GET | `/search/<topic>` | Search catalog |
| GET | `/info/<item_id>` | Retrieve book details |
| PUT | `/update/<item_id>` | Update book price or quantity |
| POST | `/decrement/<item_id>` | Decrease available stock |
| POST | `/restore/<item_id>` | Restore stock after a failed purchase |

### Order Service

| Method | Endpoint | Description |
|---|---|---|
| POST | `/purchase/<item_id>` | Process a purchase |
| GET | `/health` | Check service status |

## 6. Example Requests

Search for books:

```bash
curl "http://127.0.0.1:5000/search/distributed%20systems"
```

Retrieve information about book 2:

```bash
curl http://127.0.0.1:5000/info/2
```

Purchase book 2:

```bash
curl -X POST http://127.0.0.1:5000/purchase/2
```

Check Order Service:

```bash
curl http://127.0.0.1:5002/health
```

**Note:** Purchases modify the stored inventory. If a book has no remaining stock, the purchase request returns HTTP 409.

## 7. Database Persistence

The application uses SQLite databases for persistent storage.

Docker Compose defines two named volumes:

- `catalog_data` — stores Catalog database files.
- `order_data` — stores Order database files.

These volumes preserve data when containers are stopped or recreated.

## 8. Concurrency and Transaction Handling

Catalog uses SQLite transactions to protect inventory updates.

Concurrent purchase requests cannot reduce stock below zero.

Each purchase uses a unique transaction ID to support idempotent inventory operations.

If an order cannot be saved after stock is decremented, the Order Service attempts to restore the stock using a compensation request.

## 9. Testing

The project includes the following test scripts:

| Test File | Purpose |
|---|---|
| `tests/test_concurrent.py` | Test concurrent Catalog stock updates |
| `tests/test_order_compensation.py` | Test automatic stock compensation |
| `tests/test_docker_concurrent.py` | Test concurrent purchases through Docker |

To run the Docker integration test:

```bash
python tests/test_docker_concurrent.py
```

**Important:** This test performs real purchases against the running Docker environment and changes inventory. It expects book 2 to have exactly four available copies before execution.

The test requires Python to be installed locally.

## 10. Documentation

Project documentation is located in the `docs/` directory.

- `batool-design.md` — Frontend and Catalog design.
- `batool-output.txt` — Frontend and Catalog test results.
- `raana-design.md` — Order Service, transaction management, and integration design.
- `raana-output.txt` — Docker, concurrency, persistence, and failure-handling test results.

## 11. Limitations

This project is intended for educational purposes.

Current limitations include:

- Flask development servers are not intended for production use.
- Distributed network failures may cause uncertain transaction outcomes.
- Automatic compensation does not provide full distributed transaction guarantees.
- Additional recovery and monitoring mechanisms would be required for production deployment.