"""Clima: cada día tiene su tiempo, sorteado según la estación (datos/clima.json del mundo). El sorteo es fijo por
mundo y día: rehacer un turno da el mismo tiempo. Se guarda en el reloj: reloj.clima = {dia, tiempo, icono, efecto,
rinde} y reloj.estacion. «rinde» (0–1) es lo que rinde el trabajo al aire libre ese día (lo lee el sistema trabajo)."""
import random

NOMBRE = "clima"
LEE = ["reloj"]
ESCRIBE = ["reloj"]
PRODUCE = ["aviso:clima"]
DATOS = ["clima"]


def estacion(datos, dia):
    """La estación del día: el año del mundo empieza en datos.empieza y cada estación dura datos.dias_estacion."""
    orden = list(datos["estaciones"])
    i = orden.index(datos.get("empieza", orden[0]))
    return orden[(i + (dia - 1) // datos.get("dias_estacion", 91)) % len(orden)]


def sortear(s, dia):
    d = s.datos["clima"]
    est = estacion(d, dia)
    pesos = d["estaciones"][est]
    tiempo = random.Random(f"clima-{s.mundo.id}-{dia}").choices(list(pesos), weights=list(pesos.values()))[0]
    s.e["reloj"]["estacion"] = est
    s.e["reloj"]["clima"] = {"dia": dia, "tiempo": tiempo, **d["tiempos"][tiempo]}
    s.inc.setdefault("clima", []).append(tiempo)


def cada_dia(s, dia):
    sortear(s, dia)


def al_cerrar(s):
    if (s.e["reloj"].get("clima") or {}).get("dia") != s.e["reloj"]["dia"]:
        sortear(s, s.e["reloj"]["dia"])


def informe(s):
    c = s.e["reloj"].get("clima")
    if not c or not s.inc.get("clima"):
        return []
    malos = [t for t in s.inc["clima"] if s.datos["clima"]["tiempos"][t].get("rinde", 1) < 0.8]
    extra = f" ({len(malos)} de {len(s.inc['clima'])} días malos para el campo)" if len(s.inc["clima"]) > 1 and malos else ""
    return [f"{c['icono']} Hoy, día {c['dia']}: {c['efecto']}{extra}"]
