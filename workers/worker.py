def detect_anomalies(log):
    """Détecte les anomalies dans un log."""

    anomalies = []

    response_time = log.get("response_time")
    status_code = log.get("status_code")
    level = log.get("level")

    if isinstance(response_time, (int, float)) and response_time > 2000:
        anomalies.append("Temps de réponse trop élevé")

    if isinstance(status_code, int) and status_code >= 500:
        anomalies.append("Erreur serveur")

    if isinstance(level, str) and level == "ERROR":
        anomalies.append("Niveau de log ERROR")

    return anomalies