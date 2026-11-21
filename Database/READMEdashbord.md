# CloudLog – Dashboard et base de test 
Ce README documente uniquement ma partie : la base PostgreSQL de test et le dashboard Streamlit.
Il est séparé du README principal et de celui de l'API.

## 1. Démarche

1. Créer un conteneur PostgreSQL de test.
2. Créer la table `logs` avec `database/init.sql`.
3. Remplir la table avec de fausses données (`database/fakedata.sql`).
4. Écrire et valider les requêtes SQL du dashboard.
5. Construire le dashboard Streamlit au-dessus de ces requêtes.
6. Plus tard : remplacer les fausses données par les vraies (voir section 4).

## 2. Créer le conteneur PostgreSQL

Image utilisée : `postgres:16-alpine` (Docker Hub). Il faut la télécharger et créer le conteneur **avant** de pouvoir charger les données, car `fakedata.sql` s'exécute à l'intérieur de ce conteneur.

```powershell
docker run -d --name pg-test `
  -e POSTGRES_USER=clouduser `
  -e POSTGRES_PASSWORD=test `
  -e POSTGRES_DB=cloudlog `
  -p 5432:5432 `
  postgres:16-alpine
```

| Option | Rôle |
|---|---|
| `--name pg-test` | nom du conteneur, utilisé dans les commandes suivantes |
| `-e POSTGRES_*` | utilisateur, mot de passe et base créés au premier démarrage |
| `-p 5432:5432` | rend la base accessible depuis le PC (`localhost:5432`) |
| `postgres:16-alpine` | image de départ |

Vérifier : `docker ps` doit montrer `pg-test` avec le statut `Up`.

> Remarque : ce conteneur n'a pas de volume. Si on le supprime (`docker rm`), les données disparaissent. Il suffit alors de refaire les étapes 2, 3 et 4. Le volume permanent viendra avec Docker Compose.

## 3. Charger la table et les fausses données

Depuis la racine du dépôt, dans cet ordre :

```powershell
Get-Content database/init.sql | docker exec -i pg-test psql -U clouduser -d cloudlog
Get-Content database/fakedata.sql | docker exec -i pg-test psql -U clouduser -d cloudlog
```

- `init.sql` crée la table `logs`.
- `fakedata.sql` insère 5000 lignes. Il affiche `INSERT 0 5000`.
- `fakedata.sql` ne doit contenir que du SQL (pas la commande PowerShell).
- `init.sql` doit être appliqué avant : sinon l'erreur est `relation "logs" does not exist`.

Contenu des fausses données :

| Niveau | Part | Code HTTP | Temps de réponse |
|---|---|---|---|
| INFO | 70 % | 200, 201 | 10 à 800 ms |
| WARNING | 20 % | 400, 404, 429 | 800 à 3000 ms |
| ERROR | 10 % | 500, 503 | 1000 à 5000 ms |

`is_anomaly` suit la règle du worker : `response_time > 2000` ou `status_code >= 500` ou `level = 'ERROR'`.

Vérifier :

```powershell
docker exec -it pg-test psql -U clouduser -d cloudlog -c "SELECT COUNT(*) FROM logs;"
```

Résultat attendu : `5000`. Pour repartir de zéro : `TRUNCATE logs RESTART IDENTITY;`

## 4. Pourquoi les données réelles ne sont pas utilisées pour le moment

La chaîne prévue est :

```
generator -> API -> Redis -> worker -> PostgreSQL -> dashboard
```

À la date de ce README, le worker lit les logs dans Redis et les affiche, mais **n'écrit rien dans PostgreSQL**. Lancer le générateur laisserait donc la table `logs` vide (`SELECT COUNT(*) FROM logs;` renverrait 0).

Deux autres raisons :

- **Volume** : le générateur envoie 10 logs. Il en faut des milliers pour tester les graphiques et les filtres.
- **Qualité** : le générateur tire niveau, code HTTP et temps de réponse indépendamment, ce qui produirait une très forte proportion d'anomalies (estimation à partir du code, non mesurée). Le graphique des anomalies serait peu lisible.
- **Indépendance** : avec des fausses données, le dashboard se développe et se teste sans attendre l'API, Redis et le worker.

Ce que le dashboard a donc validé : l'affichage, les requêtes SQL et les filtres sur des données de même schéma que les vraies. Ce qui n'est **pas** validé : le comportement avec les vrais logs écrits par le worker.

## 5. Condition pour passer aux données réelles

Le passage se fera quand le worker écrit dans PostgreSQL. Alors :

```powershell
docker exec -it pg-test psql -U clouduser -d cloudlog -c "TRUNCATE logs RESTART IDENTITY;"
python generator/generator.py
docker exec -it pg-test psql -U clouduser -d cloudlog -c "SELECT COUNT(*) FROM logs;"
```

Le test est réussi si `COUNT(*)` correspond au nombre de logs envoyés (moins les rejets et doublons). Le dashboard pointe ensuite vers la même base : seules les variables de connexion changent, pas le code.

## 6. Lancer le dashboard en local

```powershell
python -m pip install -r dashboard/requirements.txt
$env:DB_HOST="localhost"
$env:DB_PASSWORD="test"
python -m streamlit run dashboard/app.py
```

L'adresse locale est `http://localhost:8501`. On utilise `python -m streamlit` car la commande `streamlit` seule n'est pas dans le PATH de Windows sur ce poste.

## 7. Limites connues

- Données fausses uniquement, pas encore testé avec le worker.
- Pas de volume sur le conteneur de test.
- Dashboard testé en local sous Python 3.14 ; l'image Docker utilisera Python 3.12.