# Bazar.com – Lab 1 Design Documentation

**Course:** Distributed and Operating Systems  
**Project:** Multi-tier Online Book Store  
**Contributor:** Batool Masri  
**Components:** Frontend Service and Catalog Service

## 1. System Architecture

Bazar.com is a distributed online bookstore based on a two-tier microservices architecture. The system consists of three independent services: Frontend, Catalog, and Order.

The Frontend accepts client requests and forwards them to the appropriate backend service. The Catalog manages book information and inventory data, while the Order service is responsible for processing purchases.

The services communicate through HTTP REST APIs and exchange data in JSON format.

The implementation uses Python, Flask, SQLite, and Docker.

## 2. Frontend Microservice

The Frontend service is implemented using Python Flask and runs on port 5000.

It provides three REST endpoints:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/search/<topic>` | Search for books by topic |
| GET | `/info/<item_id>` | Retrieve book details |
| POST | `/purchase/<item_id>` | Forward purchase requests to Order |

The Frontend uses the Python `requests` library to communicate with backend services.

Backend service URLs are configured through environment variables, allowing communication both locally and inside Docker networks.

Request timeouts and exception handling are implemented to manage backend failures. For example, the Frontend returns HTTP 503 when the Catalog service is unavailable.

## 3. Catalog Microservice

The Catalog service runs on port 5001 and stores book information using SQLite.

Each book record contains an ID, title, topic, price, and available quantity.

The implemented endpoints are:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/search/<topic>` | Retrieve books matching a topic |
| GET | `/info/<item_id>` | Retrieve a book's title, price, and stock quantity |

The database initialization function creates the required table and inserts the four initial books when the table is empty.

The Catalog returns JSON responses and HTTP 404 when a requested book does not exist.

The database location can be configured through the `DB_PATH` environment variable.

## 4. Docker Deployment and Persistence

Separate Dockerfiles and dependency files were created for the Frontend and Catalog services.

The Frontend exposes port 5000, while the Catalog exposes port 5001.

Both services were successfully built and executed in separate Linux Docker containers connected through a Docker network.

The Frontend communicates with the Catalog using its container name and the `CATALOG_URL` environment variable.

A named Docker volume, `bazar-catalog-data`, was configured to provide persistent SQLite storage.

Persistence was verified by changing a book's quantity, deleting and recreating the Catalog container, and confirming that the modified quantity remained stored.

## 5. Testing and Results

The following tests were performed successfully:

| Test | Result |
|---|---|
| Catalog search by topic | Passed |
| Catalog book information | Passed |
| Frontend-to-Catalog communication | Passed |
| Docker container communication | Passed |
| SQLite persistence after container recreation | Passed |
| Invalid book ID — HTTP 404 | Passed |
| Catalog unavailable — HTTP 503 | Passed |
| 20 concurrent read requests using 10 workers | 20/20 passed |

The successful responses confirmed that both services communicate correctly using HTTP REST calls.

Docker logs also confirmed successful requests with HTTP status code 200.

The complete recorded results are available in `docs/batool-output.txt`.

## 6. Design Decisions and Trade-offs

Flask was selected because it is lightweight and appropriate for small REST microservices.

SQLite was selected because it provides file-based persistence without requiring a separate database server.

Docker improves deployment consistency and provides isolation between services.

Separating functionality into microservices improves modularity and independent deployment. However, it introduces network overhead and requires error handling for unavailable services.

Using a Docker volume ensures that database changes survive container recreation.

## 7. Limitations and Future Improvements

The current implementation has the following limitations:

- End-to-end purchase processing requires integration with the Order service.
- Catalog stock and price update APIs remain to be integrated.
- Concurrent inventory modifications require transaction handling to prevent incorrect stock quantities.
- Flask's built-in development server is unsuitable for production deployment.
- Full three-container deployment using Docker Compose remains to be tested.

Possible improvements include automated integration tests, more structured logging, production-ready web servers, and stronger handling of concurrent inventory updates.

---

**Integration Note:** This document describes Batool's Frontend and Catalog implementation. The final project report will combine this work with Rana's Order service, Docker Compose configuration, and end-to-end purchase testing.