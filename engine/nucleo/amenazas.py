"""Amenazas con fecha (el reloj de las naves de Roma): una colección «amenazas» del mundo, {que, dia, nota?}. El
briefing las pone siempre arriba con lo que falta, y el cierre avisa al cruzar 30, 14 y 7 días, y al llegar. El
director las mueve con «cambiar» («dia»: lo que el jugador logra retrasar o adelantar), y una vez llegadas se marcan
«llego»: true o se quitan."""
from . import briefing as B, cierre as Ci

UMBRALES = (30, 14, 7, 0)


def activas(e):
    return [(aid, a) for aid, a in (e["colecciones"].get("amenazas") or {}).items() if not a.get("llego")]


def avisos(e, mundo, narr, c):
    out, hoy = [], e["reloj"]["dia"]
    for aid, a in activas(e):
        falta = a["dia"] - hoy
        cruzado = next((u for u in sorted(UMBRALES) if falta <= u), None)     # el umbral más cercano ya cruzado
        if cruzado is not None and cruzado != a.get("avisado"):
            a["avisado"] = cruzado
            out.append(f"⏳ {a['que']}: " + ("¡ya está aquí! (márcala «llego»: true cuando lo cuentes)" if falta <= 0 else f"faltan {falta} días"))
    return [], out


def seccion(partida, e):
    xs = activas(e)
    if not xs:
        return []
    hoy = e["reloj"]["dia"]
    return ["--- AMENAZAS CON FECHA"] + [f"  ⏳ {a['que']}: " + (f"faltan {a['dia'] - hoy} días (día {a['dia']})" if a["dia"] > hoy else "YA ESTÁ AQUÍ")
                                        + (f" · {a['nota']}" if a.get("nota") else "") for _, a in xs]


Ci.VALIDADORES.append(avisos)
B.SECCIONES.insert(1, seccion)
