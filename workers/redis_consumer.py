import os
import redis
import json
import time
from workers.worker import detect_anomalies

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
REDIS_QUEUE = os.getenv("REDIS_QUEUE", "cloudlog:incoming")

def connect_to_redis():
    """Établit une connexion avec Redis."""

    client = redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_timeout=None
    )

    client.ping()

    print("Connexion à Redis réussie !")

    return client

def get_log(client):
    """Récupère un log depuis la file Redis."""

    result = client.brpop(REDIS_QUEUE, timeout=5)

    if result is None:
        print("Aucun log disponible.")
        return None

    queue_name, log_data = result

    log = json.loads(log_data)

    print("Log récupéré :", log)

    anomalies = detect_anomalies(log)

    print("Anomalies détectées :", anomalies)

    return log


def process_log(client):
    """Récupère et analyse un log."""

    log = get_log(client)

    if log is None:
        return

    print("Traitement du log terminé.")
    return True


def run_worker():
    """Lance le worker en continu."""
    total_processed = 0
    start_time = time.time()

    client = connect_to_redis()

    print("Worker démarré. En attente de nouveaux logs...")

    while True:
        processed = process_log(client)

        if processed:
            total_processed += 1

            elapsed_time = time.time() - start_time

            print(f"Nombre total de logs traités : {total_processed}")
            print(f"Temps écoulé : {elapsed_time:.2f} secondes")

if __name__ == "__main__":
    run_worker()