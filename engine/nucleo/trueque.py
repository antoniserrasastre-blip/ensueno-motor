"""Trueque, al modo del comercio de Mount & Blade pero sin moneda: cosa por cosa, con valores relativos
(datos/trueque.json del mundo) y lo que cada mercado quiere y ofrece.

datos/trueque.json:
  {"valores": {"oveja": 10, "sal": 2, …},                    lo que vale cada cosa (en «ovejas», o la unidad que sea)
   "mercados": {"ebusus": {"margen": 0.15,                   lo que se queda el mercader
                           "quiere": {"lana": 1.3, …},       lo que paga mejor (×) — lo demás, a su valor
                           "ofrece": {"vino": 50, …}}}}      lo que tiene para dar y cuánto
- La orden «trocar» {persona, mercado, desde, da: {obj: n}, pide: {obj: n}} se valida al momento (que haya lo que
  se da en «desde», que el mercado tenga lo que se pide, que la balanza llegue) y queda PARA NARRAR: el director
  cuenta el viaje y el regateo (puede tirar «trocar») y la aplica con «ordenes».
- balanza(): lo que el panel enseña antes de proponer: valor de lo que das, de lo que pides y si el mercader acepta."""
from . import ordenes as O


def datos(mundo):
    return mundo.datos.get("trueque") or {}


def base(oid):
    return oid.split("@")[0]


def balanza(mundo, mercado, da, pide):
    """{"das", "pides", "acepta", "falta"}: lo que vale cada lado para ese mercader."""
    T = datos(mundo)
    m = T["mercados"][mercado]
    val = T["valores"]
    das = sum(n * val.get(k, 0) * m.get("quiere", {}).get(k, 1) for k, n in da.items())
    pides = sum(n * val.get(k, 0) for k, n in pide.items()) * (1 + m.get("margen", 0))
    return {"das": round(das, 2), "pides": round(pides, 2), "acepta": das >= pides and das > 0,
            "falta": round(max(0, pides - das), 2)}


@O.tipo("trocar", narrar=True)
class Trocar:
    def validar(self, e, mundo, d):
        T, col = datos(mundo), e["colecciones"]
        if not T:
            return ["en este mundo no hay trueque"]
        err = []
        p = O.persona(e, d.get("persona"))
        if not p:
            err.append(f"no existe la persona '{d.get('persona')}'")
        elif not p.get("tuyo"):
            err.append(f"{p['nombre']} no es de los tuyos")
        m = T["mercados"].get(d.get("mercado"))
        if not m:
            return err + [f"no hay mercado en '{d.get('mercado')}'"]
        da, pide, desde = d.get("da") or {}, d.get("pide") or {}, d.get("desde")
        if not da or not pide:
            err.append("hay que dar algo y pedir algo")
        if desde not in col.get("lugares", {}):
            err.append(f"no existe el lugar '{desde}'")
        sin_valor = [k for k in list(da) + list(pide) if k not in T["valores"]]
        if sin_valor:
            err.append(f"sin valor de trueque: {', '.join(sin_valor)}")
        for k, n in da.items():
            hay = col.get("objetos", {}).get(f"{k}@{desde}", {}).get("cantidad", 0)
            if not (isinstance(n, (int, float)) and 0 < n <= hay):
                err.append(f"no tienes {n} {k} en {desde} (hay {hay:g})")
        for k, n in pide.items():
            if not (isinstance(n, (int, float)) and 0 < n <= m.get("ofrece", {}).get(k, 0)):
                err.append(f"el mercado no tiene {n} {k}")
        if not err and not balanza(mundo, d["mercado"], da, pide)["acepta"]:
            b = balanza(mundo, d["mercado"], da, pide)
            err.append(f"el mercader no acepta: das {b['das']:g} y pides {b['pides']:g} (con su parte)")
        return err

    def aplicar(self, e, mundo, d):
        col, desde = e["colecciones"], d["desde"]
        objs = col.setdefault("objetos", {})
        nombres = {n.lower().replace(" ", "_"): n for n in (mundo.datos.get("catalogo") or {}).get("objetos", [])}
        for k, n in d["da"].items():
            objs[f"{k}@{desde}"]["cantidad"] = round(objs[f"{k}@{desde}"]["cantidad"] - n, 2)
        for k, n in d["pide"].items():
            o = objs.setdefault(f"{k}@{desde}", {"nombre": nombres.get(k, k.replace("_", " ").capitalize()), "cantidad": 0,
                                                 "donde": desde, "base": k})
            o["cantidad"] = round(o["cantidad"] + n, 2)

    def texto(self, e, d):
        lista = lambda x: ", ".join(f"{n:g} {k.replace('_', ' ')}" for k, n in x.items())
        quien = O.persona(e, d["persona"])["nombre"]
        mercado = e["colecciones"]["lugares"].get(d["mercado"], {}).get("nombre", d["mercado"])
        return f"{quien} lleva a {mercado} {lista(d['da'])} y pide {lista(d['pide'])}"
