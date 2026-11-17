"""Cosecha (de prueba): cada medianoche el campo da trigo en el poblado."""
NOMBRE = "cosecha"
LEE = ["reloj", "objetos"]
ESCRIBE = ["objetos"]
PRODUCE = ["aviso:cosecha"]
DATOS = ["cosecha"]


def cada_dia(s, dia):
    s.col["objetos"]["trigo"]["cantidad"] += s.datos["cosecha"]["por_dia"]
    s.inc["dias"] = s.inc.get("dias", 0) + 1


def informe(s):
    return [f"🌾 {s.inc['dias']} días de cosecha"] if s.inc.get("dias") else []
