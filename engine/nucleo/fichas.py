"""La ficha de una persona, al modo de D&D 5e (SRD 5.1, CC BY 4.0; ver engine/LICENCIAS.md).

persona.ficha = {"atributos": {"fue": 10, "des": 14, "con": 12, "int": 10, "sab": 13, "car": 8},
                 "nivel": 1, "competencias": ["honda"], "pg": {"max": 9, "actual": 9}, "ca": 12, "puntos": 1}
- Modificador de un atributo: (valor − 10) // 2. Bonificador de competencia por nivel: +2 (1–4), +3, +4, +5, +6.
- Las habilidades son del mundo (datos/habilidades.json: [{id, nombre, atributo}]). Tirar una habilidad suma el
  modificador de su atributo y, si es competente, el bonificador: `tirar --quien tala --hab honda --cd 12`.
- «puntos»: los da el director (al subir de nivel, por lo aprendido en la historia). Con uno, el panel deja
  aprender una habilidad: orden «aprender», al momento."""
from . import cierre as Ci, ordenes as O

ATRIBUTOS = ("fue", "des", "con", "int", "sab", "car")
NOMBRES = {"fue": "Fuerza", "des": "Destreza", "con": "Constitución", "int": "Inteligencia", "sab": "Sabiduría", "car": "Carisma"}


def mod(valor):
    return (valor - 10) // 2


def competencia(nivel):
    return 2 + (max(1, min(20, nivel)) - 1) // 4


def habilidades(mundo):
    return {h["id"]: h for h in (mundo.datos.get("habilidades") or {}).get("habilidades", [])}


def mod_de(e, mundo, pid, hab=None, atributo=None):
    """El modificador de una tirada de esa persona: el del atributo (de la habilidad o el pedido) y, si es
    competente en la habilidad, el bonificador. Devuelve (mod, explicación)."""
    p = e["colecciones"].get("personas", {}).get(pid)
    if not p:
        raise SystemExit(f"tirar: no existe la persona '{pid}'")
    f = p.get("ficha")
    if not f:
        raise SystemExit(f"tirar: {p['nombre']} no tiene ficha (cámbiasela con «ficha»)")
    hs = habilidades(mundo)
    if hab and hab not in hs:
        raise SystemExit(f"tirar: la habilidad '{hab}' no existe en este mundo")
    at = atributo or (hs[hab]["atributo"] if hab else None)
    if at not in ATRIBUTOS:
        raise SystemExit(f"tirar: atributo '{at}' (vale: {', '.join(ATRIBUTOS)})")
    m = mod(f["atributos"][at])
    partes = [f"{NOMBRES[at]} {m:+d}"]
    if hab and hab in f.get("competencias", []):
        b = competencia(f.get("nivel", 1))
        m += b
        partes.append(f"competencia {b:+d}")
    return m, f"{p['nombre']}" + (f" · {hs[hab]['nombre']}" if hab else "") + f" ({', '.join(partes)})"


def validar(e, mundo, narr, c):
    """Validador del cierre: fichas bien hechas (atributos 1–20, habilidades que existen, PG coherentes)."""
    err, hs = [], habilidades(mundo)
    for pid, p in e["colecciones"].get("personas", {}).items():
        f = p.get("ficha")
        if not f:
            continue
        a = f.get("atributos", {})
        if set(a) != set(ATRIBUTOS) or not all(isinstance(v, int) and 1 <= v <= 30 for v in a.values()):
            err.append(f"ficha de {pid}: atributos {', '.join(ATRIBUTOS)}, enteros de 1 a 30")
        if not isinstance(f.get("nivel", 1), int) or not 1 <= f.get("nivel", 1) <= 20:
            err.append(f"ficha de {pid}: nivel de 1 a 20")
        malas = [h for h in f.get("competencias", []) if h not in hs]
        if malas:
            err.append(f"ficha de {pid}: habilidades que no existen en este mundo: {', '.join(malas)}")
        pg = f.get("pg") or {}
        if pg and not 0 <= pg.get("actual", 0) <= pg.get("max", 0):
            err.append(f"ficha de {pid}: pg.actual entre 0 y pg.max")
    return err, []


@O.tipo("aprender")
class Aprender:
    """Gastar un punto en aprender una habilidad: {persona, habilidad}. Al momento."""
    def validar(self, e, mundo, d):
        p = O.persona(e, d.get("persona"))
        if not p:
            return [f"no existe la persona '{d.get('persona')}'"]
        f = p.get("ficha")
        err = []
        if not p.get("tuyo"):
            err.append(f"{p['nombre']} no es de los tuyos")
        if not f:
            err.append(f"{p['nombre']} no tiene ficha")
        elif f.get("puntos", 0) < 1:
            err.append(f"{p['nombre']} no tiene puntos para aprender")
        elif d.get("habilidad") in f.get("competencias", []):
            err.append(f"{p['nombre']} ya sabe eso")
        if d.get("habilidad") not in habilidades(mundo):
            err.append(f"la habilidad '{d.get('habilidad')}' no existe en este mundo")
        return err

    def aplicar(self, e, mundo, d):
        f = O.persona(e, d["persona"])["ficha"]
        f.setdefault("competencias", []).append(d["habilidad"])
        f["puntos"] -= 1

    def texto(self, e, d):
        return f"{O.persona(e, d['persona'])['nombre']} aprende {d['habilidad']}"


Ci.VALIDADORES.append(validar)
