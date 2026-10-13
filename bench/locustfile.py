"""Locust : charge sur /api/timeline avec des utilisateurs TinyInsta distincts.

Chaque utilisateur Locust interroge en boucle fermée (une requête dès la réponse
précédente) la timeline d'un utilisateur TinyInsta qui lui est propre.
Une ligne par requête est écrite dans TINY_LOG à la fin du test :
  T_START (s, epoch), LATENCY_MS, STATUS, INSTANCE (en-tête X-Instance),
  SERVER_MS (en-tête Server-Timing), ERROR, USERS (utilisateurs Locust actifs)

Variables d'environnement :
  TINY_PREFIX  préfixe du jeu de données          (défaut : base)
  TINY_USERS   nombre d'utilisateurs de ce jeu      (défaut : 1000)
  TINY_LIMIT   taille de la timeline                (défaut : 20)
  TINY_LOG     fichier CSV de sortie                (défaut : requests.csv)

Exemple (16 requêtes simultanées pendant 75 s) :
  TINY_PREFIX=base TINY_USERS=1000 TINY_LOG=raw/p2_n2_c16_r1.csv \\
  locust -f bench/locustfile.py --headless -u 16 -r 16 -t 75s --only-summary \\
         --host https://fixed2-dot-<PROJET>.ew.r.appspot.com
"""
import csv
import itertools
import os
import time

from locust import HttpUser, constant, events, task

PREFIX = os.environ.get('TINY_PREFIX', 'base')
N_USERS = int(os.environ.get('TINY_USERS', '1000'))
LIMIT = int(os.environ.get('TINY_LIMIT', '20'))
LOG = os.environ.get('TINY_LOG', 'requests.csv')

_next_user = itertools.count()
_rows = []
_env = None


class TimelineUser(HttpUser):
    wait_time = constant(0)  # boucle fermée

    def on_start(self):
        self.tiny_user = f"{PREFIX}_u{next(_next_user) % N_USERS:05d}"

    @task
    def timeline(self):
        self.client.get(f"/api/timeline?user={self.tiny_user}&limit={LIMIT}", name="/api/timeline")


@events.init.add_listener
def _on_init(environment, **kwargs):
    global _env
    _env = environment


@events.request.add_listener
def _on_request(request_type, name, response_time, response_length, response=None,
                context=None, exception=None, start_time=None, **kwargs):
    headers = getattr(response, 'headers', None) or {}
    timing = headers.get('Server-Timing', '')
    server_ms = timing.split('dur=')[1].split(';')[0].split(',')[0] if 'dur=' in timing else ''
    _rows.append((
        f"{start_time if start_time else time.time() - response_time / 1000:.3f}",
        f"{response_time:.1f}",
        getattr(response, 'status_code', 0) or 0,
        headers.get('X-Instance', ''),
        server_ms,
        type(exception).__name__ if exception else '',
        _env.runner.user_count if _env and _env.runner else '',
    ))


@events.quitting.add_listener
def _on_quitting(environment, **kwargs):
    os.makedirs(os.path.dirname(LOG) or '.', exist_ok=True)
    with open(LOG, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['T_START', 'LATENCY_MS', 'STATUS', 'INSTANCE', 'SERVER_MS', 'ERROR', 'USERS'])
        w.writerows(_rows)
    print(f"[tinyinsta] {len(_rows)} requêtes écrites dans {LOG}")
