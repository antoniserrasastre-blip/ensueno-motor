"""Los tipos del mundo (tipos/<tipo>.json): en qué colección viven, qué campos son obligatorios, sus valores
por defecto, a qué apunta cada campo y cómo se hace su id.

{"coleccion": "personas", "obligatorios": ["nombre", "donde"], "defecto": {"animo": 0},
 "refs": {"donde": "lugar", "amigos": "persona[]"}, "id": "nombre"}

refs: campo → tipo al que apunta («lugar[]», una lista). Una referencia rota no deja cerrar."""
import re
import unicodedata


def slug(texto):
    """«Ses Païsses» → ses_paisses: minúsculas, sin acentos, palabras con _."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def nuevo_id(tipo, campos, coleccion):
    base = slug(campos.get(tipo.get("id", "nombre"), "") or campos.get("nombre", ""))
    if not base:
        raise SystemExit(f"crear: hace falta '{tipo.get('id', 'nombre')}' para el id")
    if base not in coleccion:
        return base
    n = 2
    while f"{base}_{n}" in coleccion:
        n += 1
    return f"{base}_{n}"


def validar(e, mundo):
    """Errores del estado frente a los tipos: obligatorios que faltan y referencias rotas."""
    errores = []
    cols = e["colecciones"]
    for tid, t in mundo.tipos.items():
        for xid, x in cols.get(t["coleccion"], {}).items():
            for campo in t.get("obligatorios", []):
                if x.get(campo) in (None, ""):
                    errores.append(f"{tid} '{xid}': falta '{campo}'")
            for campo, destino in t.get("refs", {}).items():
                lista = destino.endswith("[]")
                dt = mundo.tipos.get(destino.rstrip("[]"))
                if not dt:
                    errores.append(f"tipo {tid}: '{campo}' apunta a un tipo que no existe ({destino})")
                    continue
                valores = x.get(campo) or []
                for v in (valores if lista else [valores] if valores else []):
                    if v not in cols.get(dt["coleccion"], {}) and v not in t.get("refs_libres", {}).get(campo, []):
                        errores.append(f"{tid} '{xid}': {campo} → '{v}' no existe")
    return errores
