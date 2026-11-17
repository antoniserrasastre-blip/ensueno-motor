"""El briefing: lo que el director lee al empezar un turno, en una pantalla. Lo comprobable no se le pide
recordar: viene aquí."""
from . import reloj as R

SECCIONES = []       # fn(partida, e) → [líneas]: las fases siguientes añaden las suyas (constitución, órdenes…)


def texto(partida):
    from . import enganches
    enganches.cargar()
    e = partida.estado()
    m = partida.mundo
    out = [f"=== {partida.info.get('nombre', partida.dir.name)} · mundo {m.id} · turno {e['turno'] + 1} (cerrado: {e['turno']})",
           f"reloj: {R.texto(e['reloj'])}"]
    for f in SECCIONES:
        out += f(partida, e)
    cuenta = [f"{len(xs)} {col}" for col, xs in e["colecciones"].items() if xs]
    out.append("hay: " + (", ".join(cuenta) or "nada todavía"))
    if e["avisos"]:
        out.append("--- avisos del último cierre")
        out += [f"  {a}" for a in e["avisos"]]
    if e["timeline"]:
        u = e["timeline"][-1]
        out.append(f"--- último turno ({u['turno']}): {u['titulo']} · {u['evento']}")
    return "\n".join(out)
