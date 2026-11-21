import random
import uuid
from datetime import datetime, timezone

import httpx


import os

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/") + "/logs"


def generate_log():
    """Génère un log fictif au format attendu par CloudLog."""

    log = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "application": random.choice(["Banking", "Ecommerce", "CloudStorage"]),
        "level": random.choice(["INFO", "WARNING", "ERROR"]),
        "message": random.choice(
            [
                "Request processed successfully",
                "Database connection failed",
                "User authentication successful",
                "Server response delayed",
                "Payment processing error",
            ]
        ),
        "response_time": random.randint(10, 5000),
        "status_code": random.choice([200, 201, 400, 404, 500, 503]),
    }

    return log


def send_log(log):
    """Envoie le log à l'API CloudLog."""

    try:
        response = httpx.post(API_URL, json=log, timeout=5)

        response.raise_for_status()

        print("Log envoyé avec succès !")
        print(response.json())

    except httpx.HTTPError as error:
        print("Erreur lors de l'envoi :", error)


if __name__ == "__main__":
    for i in range(1000):
        log = generate_log()

        print(f"Log numéro {i + 1} :")
        print(log)

        send_log(log)
