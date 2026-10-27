import requests
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

# Catalog Service endpoint
URL = "http://127.0.0.1:5001/decrement/2"

# Number of concurrent purchase requests
TOTAL_REQUESTS = 10


def purchase_book(request_number):
    try:
        response = requests.post(URL, timeout=10)

        print(
            f"Request {request_number}: "
            f"HTTP {response.status_code}"
        )

        return response.status_code

    except requests.RequestException as error:
        print(f"Request {request_number}: ERROR - {error}")
        return 0


def main():
    print("Starting concurrent purchase test...\n")

    # Send 10 requests using 10 threads
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(
            executor.map(
                purchase_book,
                range(1, TOTAL_REQUESTS + 1)
            )
        )

    counts = Counter(results)

    print("\n===== TEST RESULTS =====")
    print(f"Successful purchases (200): {counts[200]}")
    print(f"Out of stock (409): {counts[409]}")
    print(f"Other responses: {TOTAL_REQUESTS - counts[200] - counts[409]}")

    # Check remaining stock
    response = requests.get(
        "http://127.0.0.1:5001/info/2",
        timeout=10
    )

    if response.status_code != 200:
        print("Failed to retrieve final stock")
        return

    book = response.json()

    print(f"Final stock: {book['quantity']}")

    if (
        counts[200] == 5
        and counts[409] == 5
        and book["quantity"] == 0
    ):
        print("\nTEST PASSED")
    else:
        print("\nTEST FAILED")


if __name__ == "__main__":
    main()