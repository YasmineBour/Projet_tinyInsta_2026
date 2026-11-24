

import json
import sys
import urllib.request


def lire(url, user):
    with urllib.request.urlopen(f"{url}/api/timeline?user={user}", timeout=90) as r:
        return json.load(r)["items"]


a, b, *users = sys.argv[1:]
identiques = True
for u in users:
    ia, ib = lire(a, u), lire(b, u)
    ka = [(i["author"], i["created"]) for i in ia]
    kb = [(i["author"], i["created"]) for i in ib]
    commun = len(set(ka) & set(kb))
    print(f"{u} : {len(ia)} et {len(ib)} posts, {commun} en commun, meme ordre : {ka == kb}")
    identiques = identiques and set(ka) == set(kb)
print("RESULTAT : timelines identiques" if identiques else "RESULTAT : DIFFERENCES (voir ci-dessus)")
sys.exit(0 if identiques else 1)
