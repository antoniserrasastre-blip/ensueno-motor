"""La mesa: el chat de una partida entre el jugador, el director y el motor, en <partida>/mesa.jsonl. Mismo
formato que la de EnSueño, para que un solo vigilante las escuche todas y el panel las pinte igual:
  {"id": n, "ts": "2026-11-17T19:26:25", "de": "toni" | "director" | "motor", "texto"?, "evento"?, "tipo"?, …}
- evento: lo que dice un botón del panel sin que el jugador escriba («empezar», «crear_mundo»…). El director lo
  recibe como un mensaje más y actúa sin esperar.
- escuchar(): las líneas nuevas del jugador en cualquier mesa (las de las partidas y las de los mundos de otros motores
  que estén en hq.json con su «mesa»)."""
import datetime as dt
import json
import threading
import time
from pathlib import Path

_cerrojo = threading.Lock()
MAX_TEXTO = 4000


def leer(f):
    f = Path(f)
    if not f.exists():
        return []
    out = []
    for linea in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(linea))
        except ValueError:
            continue                           # una línea a medio escribir no rompe la mesa
    return out


def escribir(f, de, **campos):
    """Añade un mensaje a la mesa. Devuelve el mensaje."""
    if "texto" in campos and len(str(campos["texto"])) > MAX_TEXTO:
        raise SystemExit(f"mesa: el mensaje es demasiado largo (más de {MAX_TEXTO} caracteres)")
    f = Path(f)
    with _cerrojo:
        n = max((m.get("id", 0) for m in leer(f)), default=0) + 1
        m = {"id": n, "ts": dt.datetime.now().isoformat(timespec="seconds"), "de": de, **campos}
        with f.open("a", encoding="utf-8") as h:
            h.write(json.dumps(m, ensure_ascii=False) + "\n")
    return m


def esperando(mensajes):
    """¿Lo último lo ha dicho el jugador y el director aún no ha contestado?"""
    ult = next((m for m in reversed(mensajes) if m.get("de") in ("toni", "director")), None)
    return bool(ult and ult["de"] == "toni")


def nombre_jugador(raiz):
    """Cómo se llama el jugador en las líneas del vigilante (hq.json, «jugador»; si no, «Jugador»)."""
    hq = Path(raiz) / "hq.json"
    return (json.loads(hq.read_text(encoding="utf-8")).get("jugador") if hq.exists() else None) or "Jugador"


def linea(pid, m, jugador="Jugador"):
    """Lo que el vigilante imprime por cada mensaje del jugador («de»: «toni» en la mesa, el nombre de su papel)."""
    if m.get("evento"):
        extra = f" «{m['nombre']}»" if m.get("nombre") else ""
        return f"EVENTO {pid} {m['evento']}{extra}"
    return f"MESA {pid} #{m['id']} {jugador}: {' / '.join(str(m.get('texto', '')).splitlines())}"


def mesas(raiz):
    """{id: archivo de su mesa}: las partidas del motor nuevo y las de otros motores con «mesa» en hq.json."""
    raiz = Path(raiz)
    out = {d.name: d / "mesa.jsonl" for d in sorted((raiz / "partidas").glob("*")) if (d / "partida.json").exists()} \
        if (raiz / "partidas").exists() else {}
    hq = raiz / "hq.json"
    if hq.exists():
        for x in json.loads(hq.read_text(encoding="utf-8")).get("externas", []):
            if x.get("mesa"):
                out[x["id"]] = raiz / x["mesa"]
    return out


def pendientes(f):
    """Al empezar a escuchar: lo que el jugador ha dicho desde la última respuesta sigue pendiente."""
    ms = leer(f)
    desde = max((i + 1 for i, m in enumerate(ms) if m.get("de") != "toni"), default=0)
    return ms[desde:], len(ms)


def escuchar(raiz, salida=print, vueltas=None, pausa=1.0):
    """Vigila todas las mesas: una línea por cada mensaje nuevo del jugador (y lo pendiente al arrancar). Las partidas
    que aparezcan mientras escucha también entran. vueltas: para los tests (None = siempre)."""
    vistos, quien = {}, nombre_jugador(raiz)
    for pid, f in mesas(raiz).items():
        pend, n = pendientes(f)
        for m in pend:
            if m.get("de") == "toni":
                salida(linea(pid, m, quien))
        vistos[pid] = n
    i = 0
    while vueltas is None or i < vueltas:
        i += 1
        time.sleep(pausa)
        for pid, f in mesas(raiz).items():
            ms = leer(f)
            for m in ms[vistos.get(pid, 0):]:
                if m.get("de") == "toni":
                    salida(linea(pid, m, quien))
            vistos[pid] = len(ms)
