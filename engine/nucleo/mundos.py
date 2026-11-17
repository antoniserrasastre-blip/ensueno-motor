"""Mundos inventados: se crean vacíos, se rellenan dictando (el jugador dicta el lore y el director lo escribe) y
solo se juegan cuando están completos.

- crear(): mundos/<id>/ desde una plantilla mínima, con la constitución en BORRADOR (apartados con «⬜» por rellenar),
  catálogo, tipos, datos y lugares vacíos, y una partida partidas/<id>_1 «en construcción».
- validar(): lo que falta, apartado por apartado (✅/⬜). Mientras falte algo, la partida no cierra turnos.
- listo(): cuando todo está en ✅, el mundo pasa a «listo» y la partida se rehace con sus lugares de inicio, lista para
  la sesión cero.
El mapa es opcional: un mundo inventado puede no tener terreno."""
import json
import re
from pathlib import Path

from . import briefing as B
from .partida import Mundo, Partida, escribir_json, leer_json, nueva
from .tipos import slug

# apartados de la constitución: (clave al principio de línea, qué es, qué preguntar)
APARTADOS = [
    ("ÉPOCA", "Época y lugar", "¿cuándo y dónde? (año o era, la tierra, quién manda)"),
    ("QUIÉN", "Quién eres", "¿quién es el jugador y de dónde viene?"),
    ("SOCIEDAD", "Sociedad", "¿cómo vive la gente? (familias, poblados, oficios, jerarquía)"),
    ("TECNOLOGÍA", "Tecnología", "¿qué saben hacer y con qué? (materiales, herramientas, armas)"),
    ("NO EXISTE", "Lo que no existe", "¿qué NO hay en este mundo? (lista: lo que el cierre no dejará pasar)"),
    ("DE FUERA", "Lo de fuera", "¿qué hay más allá y qué puede llegar? (amenazas, oportunidades)"),
    ("MONEDA", "Moneda o trueque", "¿cómo se paga? (moneda, trueque, valores)"),
    ("TONO", "Tono", "¿cómo se cuenta? (duro, mítico, cómico…)"),
    ("MARCO", "Marco del sueño", "¿con el marco de Voss (el Soñador entra desde fuera) o mundo puro? (sí/no)"),
]
MIN_LUGARES, MIN_OBJETOS, MIN_HABILIDADES = 3, 5, 3
HUECO = "⬜"
PLANTILLA = Path(__file__).resolve().parent.parent / "plantillas" / "mundo"


def constitucion_borrador(nombre):
    lineas = [f"# {nombre} — constitución (BORRADOR: se rellena dictando; «{HUECO}» es lo que falta)", ""]
    for clave, _, pregunta in APARTADOS:
        lineas.append(f"{clave:<11} {HUECO} {pregunta}")
    return "\n".join(lineas) + "\n"


def crear(raiz, mid, nombre, icono=None):
    """El mundo vacío y su partida «en construcción». Devuelve (mundo_dir, partida)."""
    mid = slug(mid)[:40]
    if not mid:
        raise SystemExit("mundo nuevo: hace falta un id (letras y números)")
    d = Path(raiz) / "mundos" / mid
    if d.exists():
        raise SystemExit(f"mundo nuevo: ya existe el mundo '{mid}'")
    (d / "tipos").mkdir(parents=True)
    (d / "datos").mkdir()
    for f in (PLANTILLA / "tipos").glob("*.json"):
        (d / "tipos" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    escribir_json(d / "mundo.json", {"id": mid, "nombre": nombre, "subtitulo": "Mundo en construcción", "estado": "construccion",
                                     "icono": icono or "", "inventado": True, "reloj": {"dia": 1, "hora": 8},
                                     "jugador": "", "fecha_inicio": ""})
    (d / "constitucion.md").write_text(constitucion_borrador(nombre), encoding="utf-8")
    escribir_json(d / "sistemas.json", {"_": "Sistemas del mundo, en el orden en que corren (engine/sistemas/). Se encienden cuando haga falta."})
    escribir_json(d / "inicio.json", {"lugares": {}})
    escribir_json(d / "datos" / "catalogo.json", {"_": "Lo que hay en este mundo: objetos, oficios y habilidades.", "objetos": [], "oficios": [], "habilidades": []})
    escribir_json(d / "datos" / "habilidades.json", {"_": "Habilidades y su atributo (fue, des, con, int, sab, car).", "habilidades": []})
    escribir_json(d / "datos" / "anacronismos.json", {"_": "bloquea: lo que no existe (no deja cerrar); avisa: lo que es de fuera.", "bloquea": [], "avisa": []})
    escribir_json(d / "datos" / "trabajos.json", {"_": "La tabla de trabajos.", "trabajos": []})
    p = nueva(Path(raiz) / "partidas" / f"{mid}_1", d, nombre)
    info = leer_json(p.dir / "partida.json")
    info["construccion"] = True
    escribir_json(p.dir / "partida.json", info)
    return d, Partida(p.dir)


def apartados_constitucion(texto):
    """{clave: valor} de la constitución: el texto tras la clave hasta el siguiente apartado."""
    claves = [c for c, _, _ in APARTADOS]
    out, actual = {}, None
    for linea in texto.splitlines():
        m = re.match(r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]+?)\s{2,}(.*)$", linea) or re.match(r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]+?)\s+(.*)$", linea)
        clave = next((c for c in claves if m and m.group(1).strip().startswith(c)), None)
        if clave:
            actual = clave
            out[clave] = m.group(2).strip()
        elif actual and linea.startswith(" "):
            out[actual] += " " + linea.strip()
    return out


def validar(mundo_dir):
    """Lo que falta para jugar: [{id, nombre, ok, falta}] (el mapa es opcional: ok siempre, con nota)."""
    w = Mundo(mundo_dir)
    ap = apartados_constitucion(w.constitucion)
    out = []
    for clave, nombre, pregunta in APARTADOS:
        v = ap.get(clave, "")
        out.append({"id": clave.lower().replace(" ", "_"), "nombre": nombre, "ok": bool(v) and HUECO not in v,
                    "falta": "" if v and HUECO not in v else pregunta})
    lugares = leer_json(w.dir / "inicio.json", {}).get("lugares", {})
    out.append({"id": "lugares", "nombre": "Lugares de inicio", "ok": len(lugares) >= MIN_LUGARES,
                "falta": "" if len(lugares) >= MIN_LUGARES else f"hay {len(lugares)}; hacen falta {MIN_LUGARES} (inicio.json)"})
    cat = w.datos.get("catalogo") or {}
    objs = len(cat.get("objetos", []))
    out.append({"id": "catalogo", "nombre": "Catálogo", "ok": objs >= MIN_OBJETOS,
                "falta": "" if objs >= MIN_OBJETOS else f"{objs} objetos; hacen falta {MIN_OBJETOS} (datos/catalogo.json)"})
    habs = len((w.datos.get("habilidades") or {}).get("habilidades", []))
    out.append({"id": "habilidades", "nombre": "Habilidades", "ok": habs >= MIN_HABILIDADES,
                "falta": "" if habs >= MIN_HABILIDADES else f"{habs}; hacen falta {MIN_HABILIDADES} (datos/habilidades.json, con su atributo)"})
    bloq = len((w.datos.get("anacronismos") or {}).get("bloquea", []))
    out.append({"id": "anacronismos", "nombre": "Lo que el cierre no deja pasar", "ok": bloq >= 1,
                "falta": "" if bloq else "pasa «NO EXISTE» a datos/anacronismos.json (bloquea)"})
    tiene_mapa = (w.dir / "mapas" / "mapas.json").exists()
    out.append({"id": "mapa", "nombre": "Mapa (opcional)", "ok": True, "opcional": True,
                "falta": "" if tiene_mapa else "sin mapa: se juega igual"})
    return out


def limpio(v):
    """Sin las marcas de quién lo dijo («[jugador]», «[propuesta]»…)."""
    return re.sub(r"\s*\[[^\]]*\]", "", v).strip()


def corto(v, n):
    """La primera frase, y si no cabe, cortada por palabra entera con «…»."""
    v = v.split(". ")[0].rstrip(".")
    if len(v) <= n:
        return v
    return v[:n - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def en_construccion(partida):
    return bool(partida.info.get("construccion"))


def listo(raiz, mid):
    """Si todo está en ✅: el mundo pasa a «listo» y su partida (aún en el turno 0) se rehace con los lugares de
    inicio, lista para la sesión cero."""
    d = Path(raiz) / "mundos" / mid
    falta = [a for a in validar(d) if not a["ok"]]
    if falta:
        raise SystemExit("mundo listo: aún falta " + "; ".join(f"{a['nombre']} ({a['falta']})" for a in falta))
    info = leer_json(d / "mundo.json")
    ap = {k: limpio(v) for k, v in apartados_constitucion((d / "constitucion.md").read_text(encoding="utf-8")).items()}
    info.update(estado="listo", subtitulo=info.get("subtitulo") if info.get("subtitulo") != "Mundo en construcción" else corto(ap["ÉPOCA"], 60),
                jugador=info.get("jugador") or corto(ap["QUIÉN"], 120), fecha_inicio=info.get("fecha_inicio") or corto(ap["ÉPOCA"], 80),
                marco_sueno=ap["MARCO"].strip().lower().startswith(("sí", "si")))
    escribir_json(d / "mundo.json", info)
    texto = (d / "constitucion.md").read_text(encoding="utf-8")
    (d / "constitucion.md").write_text(re.sub(r"\(BORRADOR[^)]*\)", "", texto, count=1).replace(" — constitución ", " — constitución"), encoding="utf-8")
    hechas = []
    for pd in sorted((Path(raiz) / "partidas").glob(f"{mid}_*")):
        p = Partida(pd)
        if not en_construccion(p) or p.estado()["turno"] != 0:
            continue
        e = p.estado()
        ini = leer_json(d / "inicio.json", {})
        for col, xs in ini.items():
            e["colecciones"].setdefault(col, {}).update(xs)
        p.guardar(e)
        p.info.pop("construccion", None)
        escribir_json(pd / "partida.json", p.info)
        hechas.append(pd.name)
    return hechas


def texto_validar(apartados):
    return "\n".join(f"{'✅' if a['ok'] else '⬜'} {a['nombre']}" + (f" — {a['falta']}" if a["falta"] else "") for a in apartados)


def seccion_briefing(partida, e):
    if not en_construccion(partida):
        return []
    ap = validar(partida.mundo.dir)
    return [f"--- MUNDO EN CONSTRUCCIÓN: aún no se juega. El jugador dicta el lore y tú lo escribes (DIRECTOR.md, «Crear un "
            f"mundo dictado»). Cuando todo esté en ✅: «motor mundo listo {partida.mundo.id}»"] + \
        [f"  {'✅' if a['ok'] else '⬜'} {a['nombre']}" + (f" — {a['falta']}" if a["falta"] else "") for a in ap]


B.SECCIONES.insert(0, seccion_briefing)
