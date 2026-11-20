#Logs par niveau
SELECT level, COUNT(*) AS total FROM logs GROUP BY level ORDER BY total DESC;
#  level  | total 
#---------+-------
# INFO    |  3511
#WARNING |   968
#ERROR   |   521


# . Erreurs par application
SELECT application, COUNT(*) AS erreurs FROM logs WHERE level = 'ERROR' GROUP BY application ORDER BY erreurs DESC; 
# application  | erreurs 
--------------+---------
 #Ecommerce    |     176
 #Banking      |     173
 #CloudStorage |     172


#Erreurs par minute
SELECT date_trunc('minute', timestamp) AS minute, COUNT(*) AS erreurs FROM logs WHERE level = 'ERROR' GROUP BY 1 ORDER BY 1 LIMIT 20; 

#date_trunc('minute', ...) supprime les secondes, donc tous les logs de 10:30:12 et 10:30:48 tombent dans la même minute. GROUP BY 1 veut dire « regrouper par la première colonne du SELECT ». LIMIT 20 évite d’afficher des centaines de lignes dans le terminal. C’est la requête de ton graphique « Erreurs dans le temps ».
#         minute         | erreurs 
------------------------+---------
# 2026-11-19 02:41:00+00 |       1
# 2026-11-19 02:45:00+00 |       1


# Temps de réponse moyen
sql
SELECT ROUND(AVG(response_time)) AS temps_moyen_ms, MAX(response_time) AS temps_max_ms FROM logs;
# temps_moyen_ms | temps_max_ms 
----------------+--------------
#           975 |         4988

#. Dix dernières anomalies
SELECT timestamp, application, status_code, response_time, message FROM logs WHERE is_anomaly ORDER BY timestamp DESC LIMIT 10; 
#           timestamp           | application  | status_code | response_time |          message           
-------------------------------+--------------+-------------+---------------+----------------------------
# 2026-11-20 02:38:49.572534+00 | Ecommerce    |         400 |          2762 | Slow database query
# 2026-11-20 02:38:24.419129+00 | CloudStorage |         404 |          2258 | Server response delayed



# toutes les statistiques en une requête

#Ton dashboard affichera plusieurs indicateurs côte à côte. On peut les calculer en un seul passage :
SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE level = 'ERROR') AS erreurs, COUNT(*) FILTER (WHERE is_anomaly) AS anomalies, ROUND(AVG(response_time)) AS temps_moyen_ms FROM logs;
# total | erreurs | anomalies | temps_moyen_ms 
-------+---------+-----------+----------------
#  5000 |     521 |       974 |            975
