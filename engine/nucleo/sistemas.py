"""Sistemas enchufables. Cada uno es un .py en engine/sistemas/ (los del motor) o en <mundo>/sistemas/ (los
propios de un mundo), y el mundo los enciende en su sistemas.json, en el orden en que corren.

El contrato, en cabeza de cada sistema:
    NOMBRE   = "comida"
    LEE      = ["personas", "objetos"]        colecciones (o "reloj") que mira
    ESCRIBE  = ["objetos"]                    las únicas que puede cambiar: si toca otra, el turno no cierra
    PRODUCE  = ["aviso:hambre"]               qué avisos u órdenes puede sacar (para el director y el panel)
    DATOS    = ["alimentos"]                  los datos/<x>.json del mundo que necesita: sin ellos, no arranca
ganchos (todos opcionales): cada_tramo(s, horas, dia) · cada_dia(s, dia) · al_cerrar(s) · informe(s) → [avisos]
`s` es la Sesion: el estado, el mundo y lo que va pasando en el turno."""
import copy
import importlib.util
import json
from pathlib import Path

MOTOR = Path(__file__).resolve().parent.parent
CAMPOS = ("NOMBRE", "LEE", "ESCRIBE", "PRODUCE", "DATOS")


class Sesion:
    """Lo que ve un sistema: el estado (e), las colecciones (col), los datos del mundo y lo del turno (inc)."""
    def __init__(self, e, mundo):
        self.e, self.mundo, self.datos, self.inc = e, mundo, mundo.datos, {}

    @property
    def col(self):
        return self.e["colecciones"]

    def parte(self, nombre):
        return self.e["reloj"] if nombre == "reloj" else self.e["colecciones"].get(nombre)


class ForjaFallo(Exception):
    """Un sistema de la forja ha fallado (o ha tocado lo que no declara): el cierre lo apaga y se rehace sin él."""
    def __init__(self, fid, nota):
        super().__init__(nota)
        self.fid, self.nota = fid, nota


def cargar_forja(partida, d, ficha):
    """Un sistema de la forja (<partida>/forja/<id>/sistema.py) con su contrato comprobado. Sus datos se suman a los
    del mundo mientras está cargado."""
    f = d / "sistema.py"
    spec = importlib.util.spec_from_file_location(f"forja_{partida.dir.name}_{ficha['id']}", f)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as ex:  # noqa: BLE001 — cualquier error al cargar es de la pieza, no del motor
        raise SystemExit(f"forja {ficha['id']}: no carga ({type(ex).__name__}: {ex})")
    falta = [c for c in CAMPOS if not hasattr(mod, c)]
    if falta:
        raise SystemExit(f"forja {ficha['id']}: le falta {', '.join(falta)} en su contrato")
    for g in (d / "datos").glob("*.json") if (d / "datos").exists() else []:
        partida.mundo.datos.setdefault(g.stem, json.loads(g.read_text(encoding="utf-8")))
    sin = [x for x in mod.DATOS if x not in partida.mundo.datos]
    if sin:
        raise SystemExit(f"forja {ficha['id']}: no hay datos/{', '.join(sin)}.json")
    mod.FORJA = ficha["id"]
    return mod


def cargar(mundo, partida=None, excluir=()):
    """Los sistemas encendidos del mundo, en su orden, con el contrato comprobado; y, si se da la partida, los de su
    forja que estén listos y encendidos (menos los de «excluir»: los que el cierre ha apagado por fallar)."""
    out = []
    for sid, on in mundo.sistemas_on.items():
        if sid.startswith("_") or not on:
            continue
        f = next((d / f"{sid}.py" for d in (mundo.dir / "sistemas", MOTOR / "sistemas") if (d / f"{sid}.py").exists()), None)
        if not f:
            raise SystemExit(f"sistemas.json: no existe el sistema '{sid}' (ni en el mundo ni en el motor)")
        spec = importlib.util.spec_from_file_location(f"sistema_{mundo.id}_{sid}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        falta = [c for c in CAMPOS if not hasattr(mod, c)]
        if falta:
            raise SystemExit(f"sistema {sid}: le falta {', '.join(falta)} en su contrato")
        sin = [d for d in mod.DATOS if d not in mundo.datos]
        if sin:
            raise SystemExit(f"sistema {sid}: el mundo no trae datos/{', '.join(sin)}.json")
        out.append(mod)
    if partida is not None and (partida.dir / "forja").exists():
        for d in sorted((partida.dir / "forja").iterdir()):
            fx = d / "ficha.json"
            if not fx.exists():
                continue
            x = json.loads(fx.read_text(encoding="utf-8"))
            if x.get("estado") == "listo" and x.get("encendido") and x["id"] not in excluir:
                try:
                    out.append(cargar_forja(partida, d, x))
                except SystemExit as ex:
                    raise ForjaFallo(x["id"], str(ex))
    return out


def correr(s, gancho, ses, *args):
    """Llama a un gancho y comprueba que el sistema solo ha cambiado lo que declara en ESCRIBE."""
    fn = getattr(s, gancho, None)
    if not fn:
        return None
    partes = set(ses.col) | {"reloj"}
    antes = {k: json.dumps(ses.parte(k), sort_keys=True) for k in partes if k not in s.ESCRIBE}
    forja = getattr(s, "FORJA", None)
    try:
        r = fn(ses, *args)
    except Exception as ex:  # noqa: BLE001 — una pieza de la forja que falla no rompe la partida
        if forja:
            raise ForjaFallo(forja, f"{gancho}: {type(ex).__name__}: {ex}")
        raise
    except SystemExit as ex:
        if forja:
            raise ForjaFallo(forja, f"{gancho}: {ex}")
        raise
    for k, v in antes.items():
        if json.dumps(ses.parte(k), sort_keys=True) != v:
            nota = f"sistema {s.NOMBRE}: ha tocado '{k}', que no está en su ESCRIBE"
            if forja:
                raise ForjaFallo(forja, nota)
            raise SystemExit(nota)
    return r


def contratos(mundo):
    """Para `motor sistemas`: el contrato de cada sistema encendido."""
    return [{c.lower(): copy.copy(getattr(s, c)) for c in CAMPOS} for s in cargar(mundo)]
