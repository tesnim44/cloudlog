# CloudLog : Distributed Log Monitoring

Système distribué de surveillance de logs : un générateur envoie des logs à une API, une file Redis les met en attente, un worker les analyse et les enregistre dans PostgreSQL, et un dashboard Streamlit les affiche.

```
generator -> API (FastAPI) -> Redis -> worker -> PostgreSQL -> dashboard (Streamlit)
```

## Services

| Service | Rôle | Port sur le PC |
|---|---|---|
| `redis` | File d'attente des logs | non publié |
| `postgres` | Stockage permanent (volume `postgres-data`) | 5432 |
| `api` | Reçoit et valide les logs, les place dans Redis | 8000 |
| `worker` | Lit Redis, détecte les anomalies, insère dans PostgreSQL | non publié |
| `dashboard` | Interface de visualisation | 8501 |
| `generator` | Envoie des logs de test (profil `tools`, lancé à la demande) | non publié |

## Structure du dépôt

```
api/          API FastAPI (+ Dockerfile)
workers/      worker et consommateur Redis (+ Dockerfile)
generator/    générateur de logs et test de performance (+ Dockerfile)
dashbord/     dashboard Streamlit (+ Dockerfile)
Database/     init.sql (schéma), fakedata.sql (fausses données de test)
docker-compose.yml
.env.example  modèle des variables d'environnement
```

## Prérequis

- Docker Desktop lancé
- Aucun autre programme sur les ports 5432, 8000 et 8501 (sinon l'erreur est `port is already allocated`)

## Configuration

Les variables utilisées par Compose :

| Variable | Rôle | Valeur dans Compose |
|---|---|---|
| `DB_HOST` | Hôte PostgreSQL | `postgres` (nom du service, pas `localhost`) |
| `DB_PORT`, `DB_NAME`, `DB_USER` | Connexion à la base | `5432`, `cloudlog`, `clouduser` |
| `DB_PASSWORD` | Mot de passe de la base | à choisir |
| `REDIS_HOST`, `REDIS_PORT` | Connexion Redis | `redis`, `6379` |
| `REDIS_QUEUE` | Nom de la file | `cloudlog:incoming` |
| `API_URL` | Adresse de l'API vue depuis le générateur | voir `.env.example` |
| `WORKER_LOG_EVERY` | Un message de progression tous les N logs (défaut 1000) | optionnel |



## Démarrer

```powershell
docker compose up --build -d
docker compose ps
```

Tous les services doivent être `Up`, et `postgres`, `redis`, `api` doivent être `healthy`.

| Adresse | Contenu |
|---|---|
| http://localhost:8000/docs | API (Swagger) |
| http://localhost:8501 | Dashboard |

## Envoyer des logs

Le générateur n'est pas démarré par `up`. Il envoie 1000 logs puis s'arrête :

```powershell
docker compose --profile tools run --build --rm generator
```

`--build` est nécessaire après toute modification du générateur, sinon l'ancienne image est réutilisée.

Le worker affiche un bilan environ 5 secondes après que la file est vide :

```powershell
docker compose logs worker --tail 5
```

## Vérifier la chaîne

```powershell
docker compose exec redis redis-cli LLEN cloudlog:incoming
docker compose exec postgres psql -U clouduser -d cloudlog -c "SELECT COUNT(*) FROM logs;"
```

- `LLEN` : nombre de logs encore en attente dans Redis.
- `COUNT(*)` : nombre de logs enregistrés. Après une série, il doit augmenter du nombre de logs envoyés (moins les rejets et doublons).

## Arrêter

| Commande | Effet |
|---|---|
| `docker compose stop` | Arrête les conteneurs |
| `docker compose down` | Supprime conteneurs et réseau, garde les données |
| `docker compose down -v` | Supprime aussi le volume : les données sont perdues |

`Database/init.sql` ne s'exécute qu'au premier démarrage, quand le volume est vide. Après une modification du schéma : `docker compose down -v`.

## Documentation par partie

- API : `api/README.md`
- Dashboard et base de données : `Database/READMEdashbord.md`

## Problèmes fréquents

| Symptôme | Cause probable |
|---|---|
| `port is already allocated` au démarrage | Un autre conteneur ou programme occupe le port (souvent 5432) |
| Le dashboard affiche une erreur de connexion à la base | PostgreSQL n'était pas démarré : le relancer puis `docker compose restart dashboard` |
| `COUNT(*)` n'augmente pas après le générateur | Le worker n'est pas connecté : `docker compose logs worker` |
| Les logs envoyés ne sont plus les mêmes qu'avant | Image du générateur non reconstruite : utiliser `--build` |