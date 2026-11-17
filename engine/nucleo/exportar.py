"""Exportar una copia limpia para regalar: el motor, el panel, los mundos públicos y la plantilla del mundo inventado,
sin nada privado (ni partidas jugadas, ni EnSueño, ni llaves, ni túneles, ni la biblia, ni mejoras). Queda con su
LEEME.md, un CLAUDE.md que convierte a Claude en el director, y un git con su primer commit."""
import json
import re
import shutil
import subprocess
from pathlib import Path

PUBLICOS = ("baleares_123",)
FUERA = ("__pycache__", "*.pyc", ".llave", "agentes.json")
# lo de la casa de quien exporta (rutas, servidores, el túnel); partido para que esta línea no case consigo misma
PRIVADO = [r"/home/" + "[a-z]", r"192\." + r"168\.", "sirv" + "ici", r"hq\." + "randomite", "randomite" + "@"]


def exportar(raiz, destino, mundos=PUBLICOS):
    raiz, destino = Path(raiz).resolve(), Path(destino).resolve()
    if destino.exists() and any(destino.iterdir()):
        raise SystemExit(f"exportar: {destino} no está vacía")
    if raiz in destino.parents or destino == raiz:
        raise SystemExit("exportar: el destino no puede estar dentro de este repo")
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copytree(raiz / "engine", destino / "engine", ignore=shutil.ignore_patterns(*FUERA))
    for m in mundos:
        if not (raiz / "mundos" / m / "mundo.json").exists():
            raise SystemExit(f"exportar: no existe el mundo '{m}'")
        shutil.copytree(raiz / "mundos" / m, destino / "mundos" / m, ignore=shutil.ignore_patterns(*FUERA))
    (destino / "partidas").mkdir()
    (destino / "partidas" / ".gitkeep").write_text("")
    (destino / "hq.json").write_text(json.dumps({"_": "Partidas de otros motores que el HQ enseña (ninguna) y, si hubiera, el túnel a un servidor de fuera.",
                                                 "externas": []}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for f in ("LEEME.md", "CLAUDE.md"):
        shutil.copy(raiz / "engine" / "plantillas" / "copia" / f, destino / f)
    (destino / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    sucio = revisar(destino)
    if sucio:
        shutil.rmtree(destino)
        raise SystemExit("exportar: algo privado se ha colado y no se exporta:\n" + "\n".join(sucio))
    git = lambda *a: subprocess.run(["git", "-C", str(destino), "-c", "user.name=EnSueño", "-c", "user.email=motor@localhost", *a],
                                    capture_output=True, text=True)
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "EnSueño: motor de rol con Claude de director (copia limpia)")
    return destino


def revisar(destino):
    """Las líneas con algo privado (rutas de una casa, servidores, túneles). Debe salir vacía."""
    out = []
    for f in Path(destino).rglob("*"):
        if f.is_file() and f.suffix in (".py", ".md", ".json", ".html", ".txt") and ".git" not in f.parts:
            for i, linea in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if any(re.search(p, linea) for p in PRIVADO):
                    out.append(f"{f.relative_to(destino)}:{i}: {linea.strip()[:100]}")
    return out
