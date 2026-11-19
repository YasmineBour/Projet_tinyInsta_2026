from flask import Flask, request, redirect, url_for, render_template_string, session, jsonify
from google.cloud import datastore
from datetime import datetime, timedelta
import os
import random
import time

app = Flask(__name__)
app.secret_key = 'dev-key'  # À changer en prod
client = datastore.Client()

# Templates HTML minimalistes
TEMPLATE_INDEX = '''
<h2>Bienvenue sur Tiny Instagram</h2>
{% if user %}
  Connecté en tant que <b>{{ user }}</b> | <a href="/logout">Déconnexion</a><br><br>
  <form action="/post" method="post">
    <input name="content" placeholder="Votre message" required>
    <button>Poster</button>
  </form>
  <h3>Timeline</h3>
  {% for post in timeline %}
    <div><b>{{ post['author'] }}</b>: {{ post['content'] }}</div>
  {% endfor %}
  <h3>Suivre un utilisateur</h3>
  <form action="/follow" method="post">
    <input name="to_follow" placeholder="Nom d'utilisateur" required>
    <button>Suivre</button>
  </form>
{% else %}
  <form action="/login" method="post">
    <input name="username" placeholder="Nom d'utilisateur" required>
    <button>Connexion</button>
  </form>
{% endif %}
'''

MAX_IN = 30  # Datastore refuse un filtre IN de plus de 30 valeurs


def _groupes(liste, taille):
    """Decoupe une liste en morceaux de `taille` elements au plus."""
    for i in range(0, len(liste), taille):
        yield liste[i:i + taille]


def get_timeline(user: str, limit: int = 20):
    """Retourne la liste des posts (entites) pour la timeline d'un utilisateur.

    Correction (partie 3) : les auteurs sont envoyes a Datastore par groupes de
    30 au plus (une requete IN par groupe), au lieu d'une requete par auteur
    quand il y a plus de 30 auteurs.
    """
    if not user:
        return []
    follow_key = client.key('User', user)
    user_entity = client.get(follow_key)
    follows = []
    if user_entity:
        follows = user_entity.get('follows', [])
    follows = list({*follows, user})

    posts = []
    for groupe in _groupes(follows, MAX_IN):
        query = client.query(kind='Post')
        query.add_filter('author', 'IN', groupe)
        query.order = ['-created']
        posts.extend(list(query.fetch(limit=limit)))
    # Les `limit` posts les plus recents de l'ensemble font partie des `limit`
    # plus recents de leur groupe : on trie l'ensemble puis on garde `limit` posts.
    return sorted(posts, key=lambda p: p.get('created'), reverse=True)[:limit]


def seed_data(users: int = 5, posts: int = 30, follows_min: int = 1, follows_max: int = 3, prefix: str = 'user'):
    """Crée des utilisateurs, leurs relations de suivi et des posts.
    Retourne un dict avec les compteurs. Fait des écritures directes dans Datastore.
    """
    user_names = [f"{prefix}{i}" for i in range(1, users + 1)]
    created_users = 0
    for name in user_names:
        key = client.key('User', name)
        entity = client.get(key)
        if entity is None:
            entity = datastore.Entity(key)
            entity['follows'] = []
            client.put(entity)
            created_users += 1
    # Assign follows
    for name in user_names:
        key = client.key('User', name)
        entity = client.get(key)
        others = [u for u in user_names if u != name]
        if not others:
            continue
        target = random.randint(min(follows_min, len(others)), min(follows_max, len(others))) if follows_max > 0 else 0
        selection = random.sample(others, target) if target > 0 else []
        merged = sorted(set(entity.get('follows', [])).union(selection))
        entity['follows'] = merged
        client.put(entity)
    # Posts
    created_posts = 0
    base_time = datetime.utcnow()
    for i in range(posts):
        author = random.choice(user_names)
        p = datastore.Entity(client.key('Post'))
        p['author'] = author
        p['content'] = f"Seed post {i+1} by {author}"
        p['created'] = base_time - timedelta(seconds=i)
        client.put(p)
        created_posts += 1
    return {
        'users_total': users,
        'users_created': created_users,
        'posts_created': created_posts,
        'prefix': prefix
    }


@app.route('/', methods=['GET'])
def index():
    user = session.get('user')
    timeline = get_timeline(user) if user else []
    return render_template_string(TEMPLATE_INDEX, user=user, timeline=timeline)


@app.route('/api/timeline')
def api_timeline():
    """Endpoint JSON pour tests de charge (utilise paramètre user=)."""
    user = request.args.get('user') or session.get('user')
    if not user:
        return jsonify({"error": "missing user"}), 400
    try:
        limit = int(request.args.get('limit', '20'))
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 100))
    t0 = time.perf_counter()
    entities = get_timeline(user, limit=limit)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    data = [
        {
            'author': e.get('author'),
            'content': e.get('content'),
            'created': (e.get('created') or datetime.utcnow()).isoformat() + 'Z'
        }
        for e in entities
    ]
    resp = jsonify({
        'user': user,
        'count': len(data),
        'items': data
    })
    # Instrumentation pour le benchmark : instance qui a servi la requête
    # et temps passé côté serveur dans get_timeline (ms).
    resp.headers['X-Instance'] = os.environ.get('GAE_INSTANCE', 'local')
    resp.headers['Server-Timing'] = f'timeline;dur={elapsed_ms:.1f}'
    return resp


@app.route('/admin/seed', methods=['POST'])
def admin_seed():
    """Endpoint pour exécuter un seed serveur-side.
    Sécurité minimale: en-tête X-Seed-Token ou ?token= doit correspondre à SEED_TOKEN.
    Paramètres (query string ou form): users, posts, follows_min, follows_max, prefix.
    """
    expected = os.environ.get('SEED_TOKEN')
    provided = request.headers.get('X-Seed-Token') or request.args.get('token') or request.form.get('token')
    if expected and provided != expected:
        return jsonify({'error': 'forbidden'}), 403
    def _int(name, default):
        try:
            return int(request.values.get(name, default))
        except ValueError:
            return default
    users = _int('users', 5)
    posts = _int('posts', 30)
    follows_min = _int('follows_min', 1)
    follows_max = _int('follows_max', 3)
    prefix = request.values.get('prefix', 'user')
    if users <= 0 or posts < 0:
        return jsonify({'error': 'invalid parameters'}), 400
    result = seed_data(users=users, posts=posts, follows_min=follows_min, follows_max=follows_max, prefix=prefix)
    return jsonify({'status': 'ok', **result})

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    key = client.key('User', username)
    if not client.get(key):
        entity = datastore.Entity(key)
        entity.update({'follows': []})
        client.put(entity)
    session['user'] = username
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/post', methods=['POST'])
def post():
    user = session.get('user')
    if not user:
        return redirect(url_for('index'))
    content = request.form['content']
    entity = datastore.Entity(client.key('Post'))
    entity.update({
        'author': user,
        'content': content,
        'created': datastore.helpers.datetime.datetime.utcnow()
    })
    client.put(entity)
    return redirect(url_for('index'))

@app.route('/follow', methods=['POST'])
def follow():
    user = session.get('user')
    to_follow = request.form['to_follow']
    if not user or user == to_follow:
        return redirect(url_for('index'))
    user_key = client.key('User', user)
    user_entity = client.get(user_key)
    if to_follow not in user_entity['follows']:
        user_entity['follows'].append(to_follow)
        client.put(user_entity)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
