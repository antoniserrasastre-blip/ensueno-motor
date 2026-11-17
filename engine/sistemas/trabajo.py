"""Trabajo: la tabla de trabajos produce. Cada día, cada persona de los tuyos hace el trabajo con la prioridad más
alta (1 antes que 2) que pueda hacer: que no le falte lo que consume, allí donde está. Lo que da va a los objetos de
ese lugar («base@lugar»). Con competencia en la habilidad del trabajo rinde un 25 % más; con mal tiempo, el trabajo
al aire libre rinde menos (reloj.clima.rinde).

datos/produccion.json: {"trabajo": {"da": obj, "cantidad": n, "consume"?: {obj: n}, "habilidad"?: id,
                                    "aire_libre"?: true}}. Un trabajo sin «da» (vigilar, curar) no produce."""
NOMBRE = "trabajo"
LEE = ["personas", "objetos", "reloj", "lugares"]
ESCRIBE = ["objetos"]
PRODUCE = ["aviso:produccion", "aviso:falta"]
DATOS = ["produccion", "catalogo"]


def hay(s, base, lugar):
    o = s.col["objetos"].get(f"{base}@{lugar}")
    return o["cantidad"] if o else 0


def poner(s, base, q, lugar):
    oid = f"{base}@{lugar}"
    o = s.col["objetos"].get(oid)
    if not o:
        nombres = {n.lower().replace(" ", "_"): n for n in s.datos["catalogo"].get("objetos", [])}
        o = s.col["objetos"][oid] = {"nombre": nombres.get(base, base.replace("_", " ").capitalize()), "cantidad": 0,
                                     "donde": lugar, "base": base}
    o["cantidad"] = round(o["cantidad"] + q, 2)


def cada_dia(s, dia):
    P, rinde_dia = s.datos["produccion"], (s.e["reloj"].get("clima") or {}).get("rinde", 1)
    hecho, faltas = s.inc.setdefault("producido", {}), s.inc.setdefault("faltas", {})
    for pid, p in s.col.get("personas", {}).items():
        if not p.get("tuyo") or not p.get("trabajos") or p.get("edad", 99) < 10 or p["donde"] not in s.col.get("lugares", {}):
            continue
        lugar = p["donde"]
        for t, _ in sorted(p["trabajos"].items(), key=lambda kv: kv[1]):
            r = P.get(t)
            if r is None:
                continue
            falta = [k for k, n in (r.get("consume") or {}).items() if hay(s, k, lugar) < n]
            if falta:
                faltas[(p["nombre"], t)] = falta
                continue
            for k, n in (r.get("consume") or {}).items():
                poner(s, k, -n, lugar)
            if r.get("da"):
                comp = r.get("habilidad") in (p.get("ficha") or {}).get("competencias", [])
                q = round(r["cantidad"] * (1.25 if comp else 1) * (rinde_dia if r.get("aire_libre") else 1), 2)
                poner(s, r["da"], q, lugar)
                hecho[r["da"]] = round(hecho.get(r["da"], 0) + q, 2)
            break


def informe(s):
    av = []
    if s.inc.get("producido"):
        av.append("🧺 Producido: " + " · ".join(f"+{q:g} {k.replace('_', ' ')}" for k, q in s.inc["producido"].items()))
    for (quien, t), falta in list(s.inc.get("faltas", {}).items())[:5]:
        av.append(f"⚠️ {quien} no pudo {t}: falta {', '.join(falta)}")
    return av
