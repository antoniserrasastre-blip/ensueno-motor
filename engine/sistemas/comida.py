"""Comida: cada medianoche, la gente de los tuyos come de lo que hay en el lugar donde está (datos/alimentos.json:
las raciones de cada cosa, en qué orden se come y cuántas come cada uno). Si no llega, quien se queda sin comer suma
días de hambre (persona.hambre); al comer, se le pasa."""
NOMBRE = "comida"
LEE = ["personas", "objetos"]
ESCRIBE = ["objetos", "personas"]
PRODUCE = ["aviso:hambre"]
DATOS = ["alimentos"]


def cada_dia(s, dia):
    A = s.datos["alimentos"]
    raciones, orden, cada = A["raciones"], A.get("orden", list(A["raciones"])), A.get("por_persona", 1)
    por_lugar = {}
    for p in s.col.get("personas", {}).values():
        if p.get("tuyo"):
            por_lugar.setdefault(p["donde"], []).append(p)
    for lugar, gente in por_lugar.items():
        falta = len(gente) * cada
        for base in orden:
            o = s.col["objetos"].get(f"{base}@{lugar}")
            if not o or o["cantidad"] <= 0 or falta <= 0:
                continue
            come = min(o["cantidad"], falta / raciones[base])
            o["cantidad"] = round(o["cantidad"] - come, 2)
            falta = round(falta - come * raciones[base], 2)
        sin = -int(-falta // cada) if falta > 0 else 0          # cuántos se quedan sin comer
        for i, p in enumerate(sorted(gente, key=lambda x: x["nombre"])):
            if i < sin:
                p["hambre"] = p.get("hambre", 0) + 1
                s.inc.setdefault("hambre", set()).add(p["nombre"])
            else:
                p.pop("hambre", None)


def informe(s):
    if not s.inc.get("hambre"):
        return []
    return [f"🍲 Falta comida: {', '.join(sorted(s.inc['hambre']))} se han quedado sin comer"]
