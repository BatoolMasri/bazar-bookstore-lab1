import concurrent.futures
import urllib.request
import urllib.error
import json
from collections import Counter

BASE_URL = "http://127.0.0.1:5000"
BOOK_ID = 2
REQUEST_COUNT = 10


def purchase_book(_):
    url = f"{BASE_URL}/purchase/{BOOK_ID}"

    request = urllib.request.Request(
        url,
        data=b"",
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode())
            return response.status, body

    except urllib.error.HTTPError as error:
        body = json.loads(error.read().decode())
        return error.code, body

    except Exception as error:
        return "ERROR", {"error": str(error)}


print("Starting 10 concurrent purchase requests...")

with concurrent.futures.ThreadPoolExecutor(
    max_workers=REQUEST_COUNT
) as executor:
    results = list(executor.map(purchase_book, range(REQUEST_COUNT)))

counts = Counter(status for status, _ in results)

for index, (status, body) in enumerate(results, start=1):
    print(f"Request {index}: HTTP {status} | {body}")

print("\nRESULTS:")
print("Successful purchases:", counts[200])
print("Out of stock responses:", counts[409])
print("Other responses:", {
    status: count
    for status, count in counts.items()
    if status not in (200, 409)
})

with urllib.request.urlopen(
    f"{BASE_URL}/info/{BOOK_ID}",
    timeout=15
) as response:
    book = json.loads(response.read().decode())

print("Final stock:", book["quantity"])

assert counts[200] == 4, "Expected exactly 4 successful purchases"
assert counts[409] == 6, "Expected exactly 6 out-of-stock responses"
assert book["quantity"] == 0, "Final stock should be zero"

print("\nTEST PASSED: No overselling detected!")