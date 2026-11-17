"""El bloque de cambios de un turno: lo único con lo que el director cambia el mundo. Es un contrato cerrado:
una clave que no está aquí (o que no ha registrado una fase del motor) no se acepta.

{"titulo": "…", "evento": "una línea de lo que pasó",          obligatorios
 "tiempo": {"horas": 6} | {"dias": 2},                        cuánto pasa dentro (corren los sistemas)
 "crear": [{"tipo": "persona", "nombre": "…", …}],             sin id, se lo pone el motor (tipos.py)
 "cambiar": {"persona:id": {"campo": valor | null}},          valores absolutos; null borra el campo
 "quitar": ["persona:id"],                                    se archiva en archivo.jsonl
 "tiradas": [3, 4]}                                           las de dados.jsonl en las que se apoya el turno"""
import copy
from . import tipos as T

OBLIGATORIAS = ("titulo", "evento")
CLAVES = {"titulo", "evento", "tiempo", "crear", "cambiar", "quitar", "tiradas"}
EXTRA = {}           # clave → fn(e, valor, mundo, res): las fases siguientes añaden las suyas (decidir, órdenes…)
SIEMPRE = []         # fn(e, c, mundo, res): corren con cualquier bloque, después de las claves


def registrar(clave, fn):
    CLAVES.add(clave)
    EXTRA[clave] = fn


def ref(mundo, e, texto):
    """«persona:joan» → (tipo, colección, id); para por un tipo o un id que no existen."""
    tipo, _, xid = texto.partition(":")
    if tipo not in mundo.tipos:
        raise SystemExit(f"'{texto}': no hay tipo '{tipo}' (hay: {', '.join(mundo.tipos)})")
    col = mundo.tipos[tipo]["coleccion"]
    if xid not in e["colecciones"].get(col, {}):
        raise SystemExit(f"'{texto}': no existe")
    return tipo, col, xid


def horas_de(t):
    if not isinstance(t, dict) or set(t) - {"horas", "dias"}:
        raise SystemExit('tiempo: {"horas": n} o {"dias": n}')
    return t.get("horas", 0) + 24 * t.get("dias", 0)


def aplicar(e, c, mundo, partida=None):
    """Aplica lo que el bloque dice directamente (sin pasar el tiempo). Devuelve lo que hace falta luego:
    {"horas", "quitados", "creados"}. Para con un mensaje claro si algo no cuadra."""
    if not isinstance(c, dict):
        raise SystemExit("El bloque de cambios tiene que ser un objeto JSON")
    raras = set(c) - CLAVES
    if raras:
        raise SystemExit(f"Claves que el motor no conoce: {', '.join(sorted(raras))} (vale: {', '.join(sorted(CLAVES))})")
    for k in OBLIGATORIAS:
        if not str(c.get(k, "")).strip():
            raise SystemExit(f"Falta '{k}' en el bloque de cambios")
    res = {"horas": horas_de(c["tiempo"]) if "tiempo" in c else 0, "quitados": [], "creados": [], "partida": partida}
    cols = e["colecciones"]
    for x in c.get("crear", []):
        x = copy.deepcopy(x)
        tipo = x.pop("tipo", None)
        if tipo not in mundo.tipos:
            raise SystemExit(f"crear: tipo '{tipo}' no existe (hay: {', '.join(mundo.tipos)})")
        t = mundo.tipos[tipo]
        col = cols.setdefault(t["coleccion"], {})
        xid = x.pop("id", None) or T.nuevo_id(t, x, col)
        if xid in col:
            raise SystemExit(f"crear: ya existe {tipo}:{xid} (para cambiarlo, «cambiar»)")
        col[xid] = {**copy.deepcopy(t.get("defecto", {})), **x, "desde": e["turno"] + 1}
        res["creados"].append(f"{tipo}:{xid}")
    for r, campos in c.get("cambiar", {}).items():
        _, col, xid = ref(mundo, e, r)
        for k, v in campos.items():
            if v is None:
                cols[col][xid].pop(k, None)
            else:
                cols[col][xid][k] = v
    for r in c.get("quitar", []):
        tipo, col, xid = ref(mundo, e, r)
        res["quitados"].append({"tipo": tipo, "id": xid, "turno": e["turno"] + 1, "era": cols[col].pop(xid)})
    for k, fn in EXTRA.items():
        if k in c:
            fn(e, c[k], mundo, res)
    for fn in SIEMPRE:
        fn(e, c, mundo, res)
    return res
