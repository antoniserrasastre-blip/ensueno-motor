"""Órdenes del panel: lo mecánico se hace en el panel, sin chat. El panel manda una orden, el motor la valida
al momento y:
- si no tiene consecuencias (quién trabaja en qué), la aplica ya: estado «aplicada»;
- si las tiene (ir a otro sitio), la deja «para_narrar»: el briefing se la da al director, que la cuenta en el
  turno y la aplica con «ordenes» en el bloque de cambios (o la rechaza con «ordenes_no»).
Se guardan en <partida>/ordenes.json: [{id, tipo, datos, cuando, turno, estado, motivo?}].

Cada tipo declara: validar(e, mundo, datos) → [errores], aplicar(e, mundo, datos), narrar (bool) y texto(e, datos)."""
import time
from . import briefing as B, cambios as C, cierre as Ci
from .partida import escribir_json, leer_json

TIPOS = {}


def tipo(nombre, narrar=False):
    def reg(cls):
        TIPOS[nombre] = cls(); TIPOS[nombre].narrar = narrar
        return cls
    return reg


def lista(partida):
    return leer_json(partida.dir / "ordenes.json", [])


def guardar(partida, xs):
    escribir_json(partida.dir / "ordenes.json", xs)


def nueva(partida, t, datos):
    """La orden que manda el panel. Devuelve la orden guardada; para (SystemExit) si no vale."""
    if t not in TIPOS:
        raise SystemExit(f"orden: tipo '{t}' no existe (hay: {', '.join(TIPOS)})")
    e, mundo = partida.estado(), partida.mundo
    err = TIPOS[t].validar(e, mundo, datos or {})
    if err:
        raise SystemExit("; ".join(err))
    xs = lista(partida)
    o = {"id": (max((x["id"] for x in xs), default=0) + 1), "tipo": t, "datos": datos, "cuando": time.strftime("%d-%m-%Y %H:%M"),
         "turno": e["turno"] + 1, "texto": TIPOS[t].texto(e, datos)}
    if TIPOS[t].narrar:
        o["estado"] = "para_narrar"
    else:
        TIPOS[t].aplicar(e, mundo, datos)
        partida.guardar(e)
        o["estado"] = "aplicada"
    xs.append(o)
    guardar(partida, xs)
    return o


# ------------------------------------------------------------------ en el cierre: «ordenes» y «ordenes_no»

def en_bloque(e, valor, mundo, res):
    """«ordenes»: [ids] para narrar que el turno cuenta y aplica."""
    xs = {x["id"]: x for x in lista(res["partida"])}
    for oid in valor:
        o = xs.get(oid)
        if not o or o["estado"] != "para_narrar":
            raise SystemExit(f"ordenes: la {oid} no está para narrar")
        err = TIPOS[o["tipo"]].validar(e, mundo, o["datos"])
        if err:
            raise SystemExit(f"orden {oid}: ya no vale ({'; '.join(err)}). Recházala con «ordenes_no»")
        TIPOS[o["tipo"]].aplicar(e, mundo, o["datos"])
        res.setdefault("ordenes", {})[oid] = ("narrada", None)


def rechazadas(e, valor, mundo, res):
    """«ordenes_no»: {id: porque}: las que el turno no hace, con su motivo (el panel lo enseña)."""
    xs = {x["id"]: x for x in lista(res["partida"])}
    for oid, porque in valor.items():
        oid = int(oid)
        if xs.get(oid, {}).get("estado") != "para_narrar":
            raise SystemExit(f"ordenes_no: la {oid} no está para narrar")
        res.setdefault("ordenes", {})[oid] = ("rechazada", str(porque))


def al_guardar(partida, e, res):
    cambios = res.get("ordenes")
    if not cambios:
        return
    xs = lista(partida)
    for x in xs:
        if x["id"] in cambios:
            x["estado"], motivo = cambios[x["id"]]
            if motivo:
                x["motivo"] = motivo
            x["en_turno"] = e["turno"]
    guardar(partida, xs)


def seccion_briefing(partida, e):
    xs = lista(partida)
    pend = [x for x in xs if x["estado"] == "para_narrar"]
    hechas = [x for x in xs if x["estado"] == "aplicada" and x["turno"] == e["turno"] + 1]
    out = []
    if pend:
        out.append("--- ÓRDENES DEL PANEL PARA NARRAR (cuéntalas y ponlas en «ordenes»: [ids]; o «ordenes_no»: {id: porque})")
        out += [f"  #{x['id']} {x['texto']}" for x in pend]
    if hechas:
        out.append("--- hecho en el panel desde el último turno (ya aplicado)")
        out += [f"  #{x['id']} {x['texto']}" for x in hechas]
    return out


# ------------------------------------------------------------------ los tipos de orden

def persona(e, pid):
    return e["colecciones"].get("personas", {}).get(pid)


@tipo("trabajo")
class Trabajo:
    """Quién trabaja en qué y con qué prioridad (la tabla de trabajos): {persona, trabajo, prioridad 0–4}. 1 es lo
    primero que hace; 0 quita el trabajo. Los trabajos los define el mundo en datos/trabajos.json."""
    def validar(self, e, mundo, d):
        trabajos = {t["id"] for t in (mundo.datos.get("trabajos") or {}).get("trabajos", [])}
        p = persona(e, d.get("persona"))
        err = [] if p else [f"no existe la persona '{d.get('persona')}'"]
        if d.get("trabajo") not in trabajos:
            err.append(f"el trabajo '{d.get('trabajo')}' no existe en este mundo")
        if d.get("prioridad") not in (0, 1, 2, 3, 4):
            err.append("prioridad: 0 (no lo hace) a 4")
        if p and not p.get("tuyo"):
            err.append(f"{p['nombre']} no es de los tuyos: no le mandas tú")
        return err

    def aplicar(self, e, mundo, d):
        t = persona(e, d["persona"]).setdefault("trabajos", {})
        if d["prioridad"]:
            t[d["trabajo"]] = d["prioridad"]
        else:
            t.pop(d["trabajo"], None)

    def texto(self, e, d):
        p = persona(e, d["persona"])
        return f"{p['nombre']}: {d['trabajo']} → " + (f"prioridad {d['prioridad']}" if d["prioridad"] else "no lo hace")


@tipo("ir", narrar=True)
class Ir:
    """Mandar a alguien de los tuyos a otro sitio: {persona, a: lugar}. Tiene consecuencias (el camino, lo que
    deja), así que el director lo narra."""
    def validar(self, e, mundo, d):
        p = persona(e, d.get("persona"))
        err = [] if p else [f"no existe la persona '{d.get('persona')}'"]
        if d.get("a") not in e["colecciones"].get("lugares", {}):
            err.append(f"no existe el lugar '{d.get('a')}'")
        if p and not p.get("tuyo"):
            err.append(f"{p['nombre']} no es de los tuyos: no le mandas tú")
        if p and p.get("donde") == d.get("a"):
            err.append(f"{p['nombre']} ya está ahí")
        return err

    def aplicar(self, e, mundo, d):
        persona(e, d["persona"])["donde"] = d["a"]

    def texto(self, e, d):
        return f"{persona(e, d['persona'])['nombre']} va a {e['colecciones']['lugares'][d['a']]['nombre']}"


C.registrar("ordenes", en_bloque)
C.registrar("ordenes_no", rechazadas)
Ci.AL_GUARDAR.append(al_guardar)
B.SECCIONES.append(seccion_briefing)
