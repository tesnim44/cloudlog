import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="CloudLog", layout="wide")


@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://{os.getenv('DB_USER', 'clouduser')}"
        f":{os.getenv('DB_PASSWORD', 'test')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
        f"/{os.getenv('DB_NAME', 'cloudlog')}"
    )
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=10)  # recalcule au maximum toutes les 10 secondes
def query(sql: str, params: dict) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


st.title("CloudLog : Distributed Log Monitoring")

# ---------- FILTRES (barre latérale) ----------
apps_df = query("SELECT DISTINCT application FROM logs ORDER BY 1", {})
all_apps = apps_df["application"].tolist()

st.sidebar.header("Filtres")
apps = st.sidebar.multiselect("Application", all_apps, default=all_apps)
levels = st.sidebar.multiselect(
    "Niveau", ["INFO", "WARNING", "ERROR"], default=["INFO", "WARNING", "ERROR"]
)
period = st.sidebar.date_input(
    "Période", (date.today() - timedelta(days=7), date.today())
)
only_anomalies = st.sidebar.checkbox("Anomalies seulement")

if len(period) != 2:  # l'utilisateur n'a choisi qu'une date pour l'instant
    st.info("Choisis une date de début et une date de fin.")
    st.stop()
if not apps or not levels:
    st.warning("Sélectionne au moins une application et un niveau.")
    st.stop()

WHERE = """
WHERE application = ANY(:apps)
  AND level = ANY(:levels)
  AND timestamp >= :d1
  AND timestamp < :d2
  AND (NOT :only_anom OR is_anomaly)
"""
params = {
    "apps": apps,
    "levels": levels,
    "d1": period[0],
    "d2": period[1] + timedelta(days=1),
    "only_anom": only_anomalies,
}

# ---------- INDICATEURS ----------
kpi = query(
    f"""
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE level = 'ERROR') AS errors,
           COUNT(*) FILTER (WHERE is_anomaly) AS anomalies,
           COALESCE(AVG(response_time), 0) AS avg_rt
    FROM logs {WHERE}
""",
    params,
).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Logs traités", f"{int(kpi.total):,}")
c2.metric("Erreurs", f"{int(kpi.errors):,}")
c3.metric("Anomalies", f"{int(kpi.anomalies):,}")
c4.metric("Temps moyen (ms)", f"{kpi.avg_rt:.0f}")

# ---------- GRAPHIQUES ----------
left, right = st.columns(2)

with left:
    st.subheader("Répartition par niveau")
    df = query(f"SELECT level, COUNT(*) AS n FROM logs {WHERE} GROUP BY level", params)
    st.bar_chart(df.set_index("level"))

    st.subheader("Erreurs par application")
    df = query(
        f"""
        SELECT application, COUNT(*) AS erreurs FROM logs {WHERE}
        AND level = 'ERROR' GROUP BY application ORDER BY erreurs DESC
    """,
        params,
    )
    st.bar_chart(df.set_index("application"))

with right:
    st.subheader("Erreurs dans le temps")
    df = query(
        f"""
        SELECT date_trunc('second', timestamp) AS minute, COUNT(*) AS erreurs
        FROM logs {WHERE} AND level = 'ERROR'
        GROUP BY 1 ORDER BY 1
    """,
        params,
    )
    st.line_chart(df.set_index("minute"))

    st.subheader("Codes HTTP")
    df = query(
        f"""
        SELECT status_code::text AS code, COUNT(*) AS n FROM logs {WHERE}
        GROUP BY status_code ORDER BY status_code
    """,
        params,
    )
    st.bar_chart(df.set_index("code"))

# ---------- ALERTES ----------
st.subheader("Dernières anomalies")
alerts = query(
    f"""
    SELECT timestamp, application, status_code, response_time, message,
           CASE WHEN status_code >= 500 OR response_time > 2000 THEN 'High'
                ELSE 'Medium' END AS gravite
    FROM logs {WHERE} AND is_anomaly
    ORDER BY timestamp DESC LIMIT 50
""",
    params,
)
st.dataframe(alerts, use_container_width=True)
