#!/usr/bin/env python3
"""Générateur de données exact et rapide pour TinyInsta.

Crée un jeu de données identifié par un préfixe :
  - U utilisateurs  <prefix>_u00000 ... <prefix>_u<U-1>
  - chaque utilisateur suit EXACTEMENT F autres utilisateurs du jeu (tirés au hasard)
  - chaque utilisateur a EXACTEMENT P posts (dates aléatoires sur les 30 derniers jours)

Écritures par lots (put_multi), en parallèle : ~1000 à 2500 entités/s depuis Cloud Shell.

Exemples :
  python bench/seed_exact.py --prefix base --users 1000 --posts-per-user 20 --followees 20
  python bench/seed_exact.py --prefix f35  --users 120  --posts-per-user 20 --followees 35
  python bench/seed_exact.py --prefix f35 --purge          # supprime tout le jeu f35
  python bench/seed_exact.py --prefix base --users 1000 --posts-per-user 20 --followees 20 --dry-run

Un même préfixe ne doit être généré qu'une fois : relancer AJOUTE des posts.
Pour régénérer un jeu, purgez-le d'abord (--purge).
"""
import argparse
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from google.cloud import datastore
from google.cloud.datastore.query import PropertyFilter

BATCH = 500  # maximum Datastore par put_multi / delete_multi
_local = threading.local()


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--prefix', required=True, help="préfixe du jeu de données (ex: base, p100, f35)")
    p.add_argument('--users', type=int, help="U : nombre d'utilisateurs")
    p.add_argument('--posts-per-user', type=int, help="P : nombre exact de posts par utilisateur")
    p.add_argument('--followees', type=int, help="F : nombre exact de comptes suivis par utilisateur")
    p.add_argument('--project', help="projet GCP (défaut : projet gcloud courant)")
    p.add_argument('--threads', type=int, default=6)
    p.add_argument('--seed', type=int, default=42, help="graine aléatoire (reproductibilité)")
    p.add_argument('--purge', action='store_true', help="supprimer tout le jeu de données de ce préfixe")
    p.add_argument('--dry-run', action='store_true', help="n'écrit rien, affiche le plan")
    p.add_argument('--rest', action='store_true', help="utiliser l'API REST au lieu de gRPC")
    a = p.parse_args()
    if not a.purge:
        if None in (a.users, a.posts_per_user, a.followees):
            p.error("--users, --posts-per-user et --followees sont requis (sauf avec --purge)")
        if not 0 <= a.followees < a.users:
            p.error("il faut 0 <= F < U")
    return a


def make_client(args):
    kw = {'project': args.project} if args.project else {}
    if args.rest:
        kw['_use_grpc'] = False
    return datastore.Client(**kw)


def user_name(prefix, i):
    return f"{prefix}_u{i:05d}"


def run_batches(args, op, batches):
    """Exécute op(client, batch) sur chaque lot, en parallèle, avec reprise sur erreur."""
    def work(batch):
        if not hasattr(_local, 'client'):
            _local.client = make_client(args)
        for attempt in range(6):
            try:
                op(_local.client, batch)
                return len(batch)
            except Exception as e:  # contention, quota, 5xx : on réessaie
                wait = 2 ** attempt
                print(f"  erreur ({type(e).__name__}), nouvel essai dans {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError("lot abandonné après 6 essais")

    with ThreadPoolExecutor(args.threads) as ex:
        return sum(ex.map(work, batches))


def seed(args):
    rng = random.Random(args.seed)
    client = make_client(args)
    names = [user_name(args.prefix, i) for i in range(args.users)]
    now = datetime.now(timezone.utc)

    entities = []
    for i, name in enumerate(names):
        others = names[:i] + names[i + 1:]
        u = datastore.Entity(client.key('User', name))
        u['follows'] = sorted(rng.sample(others, args.followees))
        entities.append(u)

    # Posts entrelacés entre auteurs : chaque lot touche beaucoup d'auteurs différents.
    authors = names * args.posts_per_user
    rng.shuffle(authors)
    for i, author in enumerate(authors):
        p = datastore.Entity(client.key('Post'))
        p['author'] = author
        p['content'] = f"Post {i} by {author}"
        p['created'] = now - timedelta(seconds=rng.randint(0, 30 * 86400))
        entities.append(p)

    n_posts = len(authors)
    print(f"[{args.prefix}] U={args.users} P={args.posts_per_user} F={args.followees} "
          f"-> {args.users} users + {n_posts} posts = {len(entities)} entités")
    if args.dry_run:
        print("[dry-run] rien n'est écrit")
        return
    t0 = time.time()
    batches = [entities[i:i + BATCH] for i in range(0, len(entities), BATCH)]
    n = run_batches(args, lambda c, b: c.put_multi(b), batches)
    dt = time.time() - t0
    print(f"[{args.prefix}] {n} entités écrites en {dt:.1f}s ({n / dt:.0f}/s)")


def purge(args):
    client = make_client(args)
    lo, hi = f"{args.prefix}_u", f"{args.prefix}_u￿"
    q = client.query(kind='Post')
    q.add_filter(filter=PropertyFilter('author', '>=', lo))
    q.add_filter(filter=PropertyFilter('author', '<', hi))
    q.keys_only()
    keys = [e.key for e in q.fetch()]
    q = client.query(kind='User')
    q.add_filter(filter=PropertyFilter('__key__', '>=', client.key('User', lo)))
    q.add_filter(filter=PropertyFilter('__key__', '<', client.key('User', hi)))
    q.keys_only()
    keys += [e.key for e in q.fetch()]
    print(f"[{args.prefix}] {len(keys)} entités à supprimer")
    if args.dry_run or not keys:
        return
    batches = [keys[i:i + BATCH] for i in range(0, len(keys), BATCH)]
    n = run_batches(args, lambda c, b: c.delete_multi(b), batches)
    print(f"[{args.prefix}] {n} entités supprimées")


if __name__ == '__main__':
    a = parse_args()
    purge(a) if a.purge else seed(a)
