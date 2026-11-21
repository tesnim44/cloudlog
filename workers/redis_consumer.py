import json
import os
import time

import psycopg2
import redis

from workers.worker import detect_anomalies

# --- Redis ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
REDIS_QUEUE = os.getenv("REDIS_QUEUE", "cloudlog:incoming")

# --- PostgreSQL ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cloudlog")
DB_USER = os.getenv("DB_USER", "clouduser")
DB_PASSWORD = os.environ["DB_PASSWORD"]  # obligatoire : pas de valeur par défaut

LOG_EVERY = int(os.getenv("WORKER_LOG_EVERY", "1000"))

INSERT_SQL = """
INSERT INTO logs (event_id, timestamp, application, level, message,
                  response_time, status_code, is_anomaly)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id) DO NOTHING
"""

_db = None


def connect_to_redis():
    """Établit une connexion avec Redis."""

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=None)

    client.ping()

    print("Connexion à Redis réussie !")

    return client


def connect_to_db(retries=10, delay=3):
    """Se connecte à PostgreSQL, avec plusieurs tentatives."""

    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=5,
            )
            conn.autocommit = True
            print("Connexion à PostgreSQL réussie !")
            return conn
        except psycopg2.OperationalError as error:
            print(f"PostgreSQL indisponible ({attempt}/{retries}) : {error}")
            time.sleep(delay)

    raise RuntimeError("Impossible de se connecter à PostgreSQL")


def get_db():
    """Retourne la connexion PostgreSQL, en la recréant si besoin."""

    global _db

    if _db is None or _db.closed:
        _db = connect_to_db()

    return _db


def reset_db():
    """Oublie la connexion actuelle pour forcer une reconnexion."""

    global _db

    try:
        if _db is not None:
            _db.close()
    except psycopg2.Error:
        pass

    _db = None


def process_log(client):
    """Récupère un log dans Redis, l'analyse et l'enregistre en base.

    Retourne : None (file vide), "inserted", "duplicate" ou "rejected".
    """

    result = client.brpop(REDIS_QUEUE, timeout=5)

    if result is None:
        return None

    _, raw = result

    try:
        log = json.loads(raw)
        anomalies = detect_anomalies(log)
        values = (
            log["event_id"],
            log["timestamp"],
            log["application"],
            log["level"],
            log["message"],
            log["response_time"],
            log["status_code"],
            len(anomalies) > 0,
        )
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        print("Log invalide ignoré :", error)
        return "rejected"

    try:
        with get_db().cursor() as cursor:
            cursor.execute(INSERT_SQL, values)
            inserted = cursor.rowcount == 1
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as error:
        # Base indisponible : on remet le log dans la file pour ne pas le perdre.
        print("Base indisponible, log remis dans la file :", error)
        client.rpush(REDIS_QUEUE, raw)
        reset_db()
        time.sleep(2)
        return "rejected"
    except (psycopg2.DataError, psycopg2.IntegrityError) as error:
        print("Log refusé par la base :", error)
        return "rejected"

    return "inserted" if inserted else "duplicate"


def print_summary(counts, duration):
    """Affiche le bilan du traitement."""

    total = sum(counts.values())
    rate = total / duration if duration > 0 else 0

    print(
        f"Logs lus : {total} | enregistrés : {counts['inserted']} | "
        f"doublons : {counts['duplicate']} | rejetés : {counts['rejected']} | "
        f"{duration:.1f} s | {rate:.0f} logs/s"
    )


def run_worker():
    """Lance le worker en continu."""

    counts = {"inserted": 0, "duplicate": 0, "rejected": 0}
    burst_start = None  # début de la série de logs en cours
    last_log_time = None
    pending_summary = False

    client = connect_to_redis()
    get_db()

    print("Worker démarré. En attente de nouveaux logs...")

    while True:
        status = process_log(client)

        if status is None:
            # File vide : bilan final de la série, une seule fois.
            if pending_summary:
                print_summary(counts, last_log_time - burst_start)
                pending_summary = False
            continue

        now = time.time()

        if not pending_summary:
            # Première série, ou nouvelle série après une pause.
            counts = {"inserted": 0, "duplicate": 0, "rejected": 0}
            burst_start = now
            pending_summary = True

        last_log_time = now
        counts[status] += 1

        if sum(counts.values()) % LOG_EVERY == 0:
            print_summary(counts, now - burst_start)


if __name__ == "__main__":
    run_worker()
