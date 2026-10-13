# Tiny Instagram (minimal) on Google App Engine

This repository contains a tiny Instagram-like demo implemented with Flask and Google Cloud Datastore (Firestore in Datastore mode). It is a small, educational project that demonstrates posting, following, and reading a simple timeline.

**Project subject (2026): see [SUJET.md](SUJET.md).**

This README describes how to run, seed and test the app, plus notes about GQL queries and common deployment troubleshooting.

## Prerequisites
- Create a GCP Project:`https://console.cloud.google.com/`
  - See the prof.

- Open a cloud shell 
  - see the prof.

* Initialize or select your GCP project and create the App Engine application (if not already created):

```sh
gcloud init
gcloud app create
```

- clone the course repository : 
```
git clone https://gitlab.univ-nantes.fr/molli-p/tinyinsta-2026.git
cd tinyinsta-2026
```

* Install dependencies
```sh
pip install -r requirements.txt
```

* Deploy the app:

```sh
gcloud app deploy
```

* [OPTIONAL] Index does not matter:

```sh
gcloud app deploy index.yaml
# or
gcloud datastore indexes create index.yaml
```

* open the URL address of the you application, create account, post, follow. Does it Works?? If something is wrong where to find the error ?? 
  * See the prof


* How many servers are working for this app?? How much are you paying for running this app ? What is the cloud model for this app (Iaas, Paas, Saas). What is the Platform in PaaS ??

* See the impact in the datastore: do you see your data ?
  * See the prof

* How much are you paying for hosting these data in this store ?? 
* What is the consistency of this store ?
* What is the sharding strategy of this store ? How to be sure of that ? 
* What queries can you write with store (expressivity)

## HTTP Endpoints

- `/` — HTML UI for simple interactions
- `POST /login` — login with a username (no password)
- `POST /post` — create a new post (form)
- `POST /follow` — follow another user (form)
- `GET /api/timeline?user=<username>&limit=<n>` — JSON timeline for a user (default limit 20). Response headers: `X-Instance` (App Engine instance that served the request) and `Server-Timing: timeline;dur=<ms>` (time spent in `get_timeline` on the server)
- `POST /admin/seed` — server-side seed (requires `SEED_TOKEN` via header `X-Seed-Token` or `token` param)

Example server-side seed call:

```sh
curl -X POST \
  -H "X-Seed-Token: change-me-seed-token" \
  "https://<YOUR_APP>.appspot.com/admin/seed?users=8&posts=100&follows_min=1&follows_max=4&prefix=load"
```

## Benchmark toolkit (project)

The project uses the tools below (`bench/` is not uploaded to App Engine). Install them in Cloud Shell:

```sh
pip install -r bench/requirements.txt
```

**Data generator** — exact parameters: `U` users, each with exactly `P` posts and following exactly `F` other users of the same dataset. Each dataset has its own prefix; re-running a prefix *adds* posts, so purge first.

```sh
python bench/seed_exact.py --prefix base --users 1000 --posts-per-user 20 --followees 20
python bench/seed_exact.py --prefix base --purge                  # delete the whole dataset
python bench/seed_exact.py --prefix base --users 1000 --posts-per-user 20 --followees 20 --dry-run
```

User names are `<prefix>_u00000 … <prefix>_u<U-1>`.

**Deployment variants**

| Configuration | Command | Version URL |
|---|---|---|
| Autoscaling, at most 10 instances (`app.yaml`) | `gcloud app deploy --version auto-r1 --no-promote` | `https://auto-r1-dot-<PROJECT>.<REGION>.r.appspot.com` |
| Exactly N instances, no autoscaling | `./deploy_fixed.sh N` | `https://fixedN-dot-<PROJECT>.<REGION>.r.appspot.com` |

Fixed-instance versions are billed as long as they run: `gcloud app versions stop fixedN` when you are done.

**Load generator** — [Locust](https://locust.io), closed loop, one distinct TinyInsta user per Locust user, one CSV line per request (`T_START, LATENCY_MS, STATUS, INSTANCE, SERVER_MS, ERROR, USERS`):

```sh
# constant load: 16 concurrent users for 75 s
TINY_PREFIX=base TINY_USERS=1000 TINY_LOG=raw/run.csv \
  locust -f bench/locustfile.py --headless -u 16 -r 16 -t 75s --only-summary --host <VERSION_URL>

```

## GQL & Datastore notes

The timeline query used by the app is roughly:

```sql
SELECT * FROM Post WHERE author IN @authors ORDER BY created DESC
```

Consistency and transactions: the app runs on Firestore in Datastore mode.

- Lookups and queries, including non-ancestor queries, are strongly consistent by default.
- Transactions are ACID and may span any entities, even entities stored on different partitions (distributed transactions, serializable isolation).
- The database's concurrency mode decides how conflicting transactions are handled: `PESSIMISTIC` (locks) or `OPTIMISTIC` (validation at commit; a conflicting transaction fails and must be retried).
- Databases automatically upgraded from legacy Cloud Datastore may still run in `OPTIMISTIC_WITH_ENTITY_GROUPS`, which keeps the legacy limits: at most 25 entity groups per transaction and 1 write per second per entity group. Check the mode of your database in the console, or with `gcloud firestore databases describe --database='(default)'` (field `concurrencyMode`, requires the Firestore API).

## Troubleshooting: Cloud Build / staging bucket error

If you encounter an error like:

```
Failed to create cloud build: ... invalid bucket "staging.<PROJECT>.appspot.com"; service account ... does not have access
```

Check the following:

1. Required services are enabled:

```sh
gcloud services enable appengine.googleapis.com cloudbuild.googleapis.com iam.googleapis.com storage.googleapis.com
```

2. Ensure the App Engine service account has sufficient permissions on the staging bucket. For example, grant storage admin at project level (adjust to least privilege required):

```sh
PROJECT_ID="<YOUR_PROJECT>"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/storage.admin"
```

3. If the staging bucket is missing, create it and grant the service account object admin on the bucket:

```sh
gsutil mb -p "$PROJECT_ID" -l europe-west1 "gs://staging.${PROJECT_ID}.appspot.com"
gsutil iam ch serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com:objectAdmin "gs://staging.${PROJECT_ID}.appspot.com"
```

Index deployment (if GCP prompts for missing indexes):

```sh
gcloud datastore indexes create index.yaml || gcloud app deploy index.yaml
```

## License
MIT
