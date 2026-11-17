"""La constitución del mundo y lo que la hace cumplir.

- El briefing la pone siempre arriba, entera (es corta: 15–20 líneas).
- anacronismos.json del mundo:
    {"bloquea": [{"que": "pólvora", "palabras": ["pólvora", "cañón"]}],          en la narración o el bloque: no cierra
     "avisa":   [{"que": "denario", "palabras": ["denario"], "de": "Roma"}]}      en el bloque (lo que entra en el
                                                                                  estado): «¿lo tienes?»
  Lo que una decisión permite («permite»: [que]) deja de bloquear o avisar en esa partida.
- catalogo.json del mundo: {"objetos": [nombres], "oficios": […], …}. Un tipo con "catalogo": "objetos" (y
  "clave_catalogo": "nombre") avisa al crear algo que no está: «¿esto existe aquí?». Con "nuevo_en_mundo": true se
  acepta y queda como decisión.
- «decidir» en el bloque: {"que", "porque", "permite"?: [que…]} o una lista. Se escribe en
  <partida>/decisiones/DD-MM-YYYY-titulo.md y en el estado; el briefing las recuerda."""
import re
import time
import unicodedata
from . import briefing as B, cambios as C, cierre as Ci, tipos as T


def normal(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def patron(palabras):
    """Palabras (o frases) como palabras enteras, con plural: «cañón» casa con «cañones»."""
    alts = [re.escape(normal(p)).replace(r"\ ", r"\s+") + r"(?:e?s)?" for p in palabras]
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b")


def textos(x):
    """Todos los textos de un valor JSON (las claves no: son del contrato)."""
    if isinstance(x, dict):
        return [t for v in x.values() for t in textos(v)]
    if isinstance(x, list):
        return [t for v in x for t in textos(v)]
    return [str(x)] if isinstance(x, str) else []


def permitidos(e):
    return {normal(p) for d in e.get("decisiones", []) for p in d.get("permite", [])}


def validar(e, mundo, narr, c):
    """Validador del cierre: anacronismos y catálogo. Devuelve (errores, avisos)."""
    A = mundo.datos.get("anacronismos") or {}
    ok = permitidos(e)
    bloque = normal(" ".join(textos({k: v for k, v in c.items() if k != "decidir"})))
    todo = normal(narr) + "\n" + bloque
    errores, avisos = [], []
    for x in A.get("bloquea", []):
        if normal(x["que"]) in ok:
            continue
        m = patron(x["palabras"]).search(todo)
        if m:
            errores.append(f"anacronismo: «{m.group(0)}» ({x['que']}) no existe en este mundo. Quítalo, o si de verdad "
                           f"llega, usa «decidir» con \"permite\": [\"{x['que']}\"]")
    for x in A.get("avisa", []):
        if normal(x["que"]) in ok:
            continue
        m = patron(x["palabras"]).search(bloque)
        if m:
            avisos.append(f"⚠️ «{m.group(0)}» es {('de ' + x['de']) if x.get('de') else 'de fuera'}: ¿lo tienes? Si llega "
                          f"antes (comprado, enseñado, inventado), «decidir» con \"permite\": [\"{x['que']}\"]")
    cat = mundo.datos.get("catalogo") or {}
    for x in c.get("crear", []):
        t = mundo.tipos.get(x.get("tipo"), {})
        lista = cat.get(t.get("catalogo")) if t.get("catalogo") else None
        if lista is None:
            continue
        v = x.get(t.get("clave_catalogo", "nombre"), "")
        if normal(v) not in {normal(i) for i in lista} and not x.get("nuevo_en_mundo"):
            avisos.append(f"❓ {x['tipo']} «{v}»: no está en el catálogo del mundo. ¿Existe aquí? Si sí, "
                          f"\"nuevo_en_mundo\": true")
    return errores, avisos


def decidir(e, valor, mundo, res):
    """La clave «decidir» del bloque: las decisiones de mundo de esta partida."""
    for d in valor if isinstance(valor, list) else [valor]:
        if not isinstance(d, dict) or not str(d.get("que", "")).strip() or not str(d.get("porque", "")).strip():
            raise SystemExit('decidir: {"que": "…", "porque": "…", "permite"?: [lo que deja de ser anacronismo]}')
        d = {"que": d["que"].strip(), "porque": d["porque"].strip(), "permite": list(d.get("permite", [])),
             "turno": e["turno"] + 1, "fecha": time.strftime("%d-%m-%Y")}
        d["id"] = f"{d['fecha']}-{T.slug(d['que'])[:50]}"
        e.setdefault("decisiones", []).append(d)
        res.setdefault("decisiones", []).append(d)


def nuevo_en_mundo(e, c, mundo, res):
    """Lo creado con "nuevo_en_mundo": true también queda como decisión, para que se recuerde."""
    nuevos = [{"que": f"Existe {x.get('tipo')} «{x.get('nombre', '?')}» en esta partida",
               "porque": x.get("porque") or "lo trae la partida (nuevo_en_mundo)"} for x in c.get("crear", []) if x.get("nuevo_en_mundo")]
    if nuevos:
        decidir(e, nuevos, mundo, res)


def escribir(partida, e, res):
    carpeta = partida.dir / "decisiones"
    for d in res.get("decisiones", []):
        carpeta.mkdir(exist_ok=True)
        (carpeta / f"{d['id']}.md").write_text(
            f"# {d['que']}\n\n- **Turno:** {d['turno']} · **Fecha:** {d['fecha']}\n- **Por qué:** {d['porque']}\n"
            + (f"- **Permite:** {', '.join(d['permite'])}\n" if d["permite"] else ""), encoding="utf-8")


def buscar(e, tema=""):
    ds = e.get("decisiones", [])
    if tema:
        p = normal(tema)
        ds = [d for d in ds if p in normal(d["que"] + " " + d["porque"] + " " + " ".join(d["permite"]))]
    return ds


def texto_decision(d):
    return f"T{d['turno']} · {d['que']}" + (f" (permite: {', '.join(d['permite'])})" if d["permite"] else "")


def seccion_briefing(partida, e):
    out = []
    if partida.mundo.constitucion.strip():
        out += ["--- CONSTITUCIÓN DEL MUNDO (manda sobre todo; lo que no está aquí, no existe)",
                partida.mundo.constitucion.rstrip()]
    ds = e.get("decisiones", [])
    if ds:
        out.append(f"--- decisiones de esta partida ({len(ds)}; las últimas · `motor decisiones <tema>` para buscar)")
        out += [f"  {texto_decision(d)}" for d in ds[-8:]]
    return out


# enganches: clave del bloque, validador del cierre y sección del briefing
C.registrar("decidir", decidir)
C.SIEMPRE.append(nuevo_en_mundo)
Ci.VALIDADORES.append(validar)
Ci.AL_GUARDAR.append(escribir)
B.SECCIONES.insert(0, seccion_briefing)
