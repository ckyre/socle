"""Met à jour la version du socle référencée par chaque application.

Usage, depuis le dossier qui contient tous les dépôts (ex. E:\\dev) :

    python socle/scripts/mettre-a-jour.py v1.0.1

- lit les empreintes publiées (SHA256SUMS de la version GitHub) ;
- remplace la ligne « socle @ … » de chaque requirements.txt qui en contient une ;
- relance « npm install » de l'archive CSS dans chaque package.json qui la référence (met à jour package-lock.json).

Rien n'est poussé : relancez les tests de chaque application, puis commitez et poussez.
"""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

DEPOT = "https://github.com/ckyre/socle/releases/download"
IGNORES = {"node_modules", ".git", ".venv", "venv", "dist"}


def fichiers(racine: Path, nom: str):
    for p in racine.rglob(nom):
        if not IGNORES & set(p.parts):
            yield p


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"v\d+\.\d+\.\d+", sys.argv[1]):
        print(__doc__)
        return 2
    tag = sys.argv[1]
    version = tag[1:]
    with urllib.request.urlopen(f"{DEPOT}/{tag}/SHA256SUMS", timeout=30) as r:  # noqa: S310 (URL fixe en https)
        sommes = dict(reversed(line.split()) for line in r.read().decode().splitlines() if line.strip())
    roue = f"socle-{version}-py3-none-any.whl"
    archive = f"socle-{version}.tgz"
    if roue not in sommes or archive not in sommes:
        print(f"SHA256SUMS de {tag} incomplet : {sorted(sommes)}")
        return 1
    ligne = f"socle @ {DEPOT}/{tag}/{roue}#sha256={sommes[roue]}"
    url_css = f"{DEPOT}/{tag}/{archive}"

    racine = Path.cwd()
    for req in fichiers(racine, "requirements*.txt"):
        texte = req.read_text(encoding="utf-8")
        nouveau = re.sub(r"(?m)^socle @ \S+$", ligne, texte)
        if nouveau != texte:
            req.write_text(nouveau, encoding="utf-8", newline="")
            print(f"Python : {req.relative_to(racine)}", flush=True)
    echecs = []
    for pkg in fichiers(racine, "package.json"):
        deps = json.loads(pkg.read_text(encoding="utf-8")).get("dependencies", {})
        if "socle" in deps and pkg.parent.name != "socle":
            r = subprocess.run(["npm", "install", "--save-exact", f"socle@{url_css}"], cwd=pkg.parent,
                               shell=sys.platform == "win32")
            if r.returncode == 0:
                print(f"CSS : {pkg.relative_to(racine)}", flush=True)
            else:
                print(f"[x] CSS : {pkg.relative_to(racine)} : npm install a échoué", flush=True)
                echecs.append(str(pkg.relative_to(racine)))
    if echecs:
        print(f"\nÀ reprendre : {', '.join(echecs)}")
        return 1
    print(f"\nSocle {tag} référencé. Lancez les tests de chaque application, puis commitez et poussez.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
