import time
import uuid
import random
from datetime import datetime, timezone
import httpx

import os

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/") + "/logs"

NUMBER_OF_LOGS = 100000


def generate_log():
    log = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "application": random.choice(["Banking", "Ecommerce", "CloudStorage"]),
        "level": random.choice(["INFO", "WARNING", "ERROR"]),
        "message": "Performance test log",
        "response_time": random.randint(10, 5000),
        "status_code": random.choice([200, 201, 400, 404, 500, 503]),
    }

    return log


def send_logs():
    start_time = time.time()

    with httpx.Client(timeout=30) as client:
        for i in range(NUMBER_OF_LOGS):
            log = generate_log()

            response = client.post(API_URL, json=log)
            response.raise_for_status()

            if (i + 1) % 100 == 0:
                print(f"{i + 1} logs envoyés")

    end_time = time.time()

    total_time = end_time - start_time

    print(f"Temps total : {total_time:.2f} secondes")
    print(f"Nombre de logs envoyés : {NUMBER_OF_LOGS}")


if __name__ == "__main__":
    send_logs()
