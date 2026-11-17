"""La forja: el motor se construye jugando. Un jugador pide una mecánica («quiero que haya cría de caballos»), el
director la convierte en una ficha de sistema, otro agente la construye con su contrato y su test sobre una copia,
el motor la prueba y la acopla en caliente a la partida.

<partida>/forja/<id>/
  ficha.json        {id, nombre, que, pedido_por, turno, estado, encendido, lee, escribe, produce, datos,
                     como_se_nota, historial: [{cuando, estado, nota}], anunciado}
  sistema.py        el sistema, con el contrato de siempre (nucleo/sistemas.py)
  datos/*.json      sus datos (se suman a los del mundo mientras está encendido)
  test_sistema.py   su test: corre sobre una copia de la partida con el sistema encendido
  BRIEF.md          el encargo para quien lo construye

Estados: pedido → en_obra → probando → listo (o fallo). «encendido» solo cuando está listo. Si en un cierre falla o
toca lo que no declara, el cierre lo apaga, se rehace sin él y avisa."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import briefing as B, cierre as Ci
from .partida import Partida, escribir_json, leer_json
from .tipos import slug

ESTADOS = ("pedido", "en_obra", "probando", "listo", "fallo")
MARCA = "# TODO forja"       # mientras el andamio la lleve, no está construido
ENGINE = Path(__file__).resolve().parent.parent


def carpeta(partida):
    return partida.dir / "forja"


def fichas(partida):
    c = carpeta(partida)
    return [leer_json(f / "ficha.json") for f in sorted(c.iterdir()) if (f / "ficha.json").exists()] if c.exists() else []


def ficha(partida, fid):
    f = carpeta(partida) / fid / "ficha.json"
    if not f.exists():
        raise SystemExit(f"forja: no hay nada con id '{fid}'")
    return leer_json(f)


def guardar(partida, x, nota=None):
    if nota or not x.get("historial") or x["historial"][-1]["estado"] != x["estado"]:
        x.setdefault("historial", []).append({"cuando": time.strftime("%d-%m-%Y %H:%M"), "estado": x["estado"], "nota": nota or ""})
    escribir_json(carpeta(partida) / x["id"] / "ficha.json", x)


def pedir(partida, nombre, que, quien="jugador"):
    """El pedido: «quiero que haya X». Lo hace el jugador (panel) o el director (chat)."""
    if not str(nombre).strip() or not str(que).strip():
        raise SystemExit("forja: el pedido necesita un nombre y qué es")
    base = slug(nombre)[:40] or "pieza"
    fid, n = base, 2
    while (carpeta(partida) / fid).exists():
        fid, n = f"{base}_{n}", n + 1
    (carpeta(partida) / fid).mkdir(parents=True)
    x = {"id": fid, "nombre": str(nombre).strip(), "que": str(que).strip(), "pedido_por": quien,
         "turno": partida.estado()["turno"] + 1, "estado": "pedido", "encendido": False, "lee": [], "escribe": [],
         "produce": [], "datos": [], "como_se_nota": "", "anunciado": False}
    guardar(partida, x, "pedido")
    return x


def fichar(partida, fid, campos):
    """El director convierte el pedido en ficha de sistema: qué lee, qué toca, qué produce, qué datos, cómo se nota."""
    x = ficha(partida, fid)
    raras = set(campos) - {"nombre", "que", "lee", "escribe", "produce", "datos", "como_se_nota"}
    if raras:
        raise SystemExit(f"forja ficha: campos que no van: {', '.join(sorted(raras))}")
    x.update(campos)
    guardar(partida, x, "ficha")
    return x


def encargo(partida, fid):
    """Deja el andamio (sistema, datos, test) y el BRIEF para quien lo construye. Estado: en obra."""
    x = ficha(partida, fid)
    falta = [k for k in ("lee", "como_se_nota") if not x.get(k)]          # ESCRIBE puede ir vacío: solo avisa
    if falta:
        raise SystemExit(f"forja encargo: la ficha no está hecha (falta {', '.join(falta)}: «forja ficha {fid} '{{…}}'»)")
    d = carpeta(partida) / fid
    if not (d / "sistema.py").exists():
        ganchos = "def cada_dia(s, dia):\n    " + MARCA + ": lo que pasa cada día\n    pass\n\n\ndef informe(s):\n    return []\n"
        (d / "sistema.py").write_text(
            f'"""{x["nombre"]}: {x["que"]}\nCómo se nota en el juego: {x["como_se_nota"]}\n(La forja: pedido por {x["pedido_por"]} '
            f'en el turno {x["turno"]}.)"""\nNOMBRE = "{fid}"\nLEE = {json.dumps(x["lee"])}\nESCRIBE = {json.dumps(x["escribe"])}\n'
            f'PRODUCE = {json.dumps(x["produce"])}\nDATOS = {json.dumps(x["datos"])}\n\n\n{ganchos}', encoding="utf-8")
    (d / "datos").mkdir(exist_ok=True)
    for k in x["datos"]:
        if not (d / "datos" / f"{k}.json").exists() and k not in partida.mundo.datos:
            escribir_json(d / "datos" / f"{k}.json", {"_": f"Datos de {x['nombre']}: rellénalos."})
    if not (d / "test_sistema.py").exists():
        (d / "test_sistema.py").write_text(
            '"""Test de la forja: corre sobre una copia de la partida con este sistema encendido."""\nimport os\nimport sys\n'
            'import unittest\n\nsys.path.insert(0, os.environ["FORJA_ENGINE"])\nfrom nucleo import forja as F  # noqa: E402\n\n\n'
            'class Prueba(unittest.TestCase):\n    def test_un_dia(self):\n        p = F.copia_para_probar()\n'
            '        r = F.turno(p, {"tiempo": {"dias": 1}})\n        self.assertEqual(r["turno"], p.estado()["turno"])\n'
            f'        {MARCA}: comprueba lo que el sistema tiene que hacer\n\n\nif __name__ == "__main__":\n    unittest.main()\n',
            encoding="utf-8")
    brief = (f"# Encargo de la forja: {x['nombre']}\n\n**Qué es:** {x['que']}\n**Cómo se nota en el juego:** {x['como_se_nota']}\n\n"
             f"- Construye `{d / 'sistema.py'}` con su contrato: LEE {x['lee']}, ESCRIBE {x['escribe']}, PRODUCE {x['produce']}, "
             f"DATOS {x['datos']}. Ganchos: cada_tramo(s, horas, dia), cada_dia(s, dia), al_cerrar(s), informe(s) → avisos.\n"
             f"- **Solo puede tocar lo que declara en ESCRIBE**: si toca otra cosa o falla, el cierre lo apaga.\n"
             f"- Sus datos, en `{d / 'datos'}/`. La constitución del mundo manda (`motor -p {partida.dir} constitucion`).\n"
             f"- Escribe el test en `{d / 'test_sistema.py'}`. Usa `F.copia_para_probar()` y `F.turno(p, cambios)`, nunca la "
             f"partida de verdad. Quita las marcas «{MARCA}».\n"
             f"- Cuando esté: `python3 {ENGINE / 'motor.py'} -p {partida.dir} forja probar {fid}`. Si pasa, el director lo "
             f"acopla con `forja acoplar {fid}`.\n- Contrato completo y ejemplos: `engine/nucleo/sistemas.py` y `engine/sistemas/`.\n")
    (d / "BRIEF.md").write_text(brief, encoding="utf-8")
    x["estado"] = "en_obra"
    guardar(partida, x, "encargado")
    return brief


# ------------------------------------------------------------------ probar (lo usa también el test de cada pieza)

def copia_para_probar():
    """Dentro de un test de la forja: una copia de la partida con el sistema de la forja encendido."""
    origen, fid = Path(os.environ["FORJA_PARTIDA"]), os.environ["FORJA_ID"]
    destino = Path(tempfile.mkdtemp(prefix="forja_test_")) / origen.name
    shutil.copytree(origen, destino)
    info = leer_json(destino / "partida.json")              # el mundo va relativo a la partida: en la copia, absoluto
    info["mundo"] = str(Partida(origen).mundo.dir)
    escribir_json(destino / "partida.json", info)
    x = leer_json(destino / "forja" / fid / "ficha.json")
    x.update(estado="listo", encendido=True)
    escribir_json(destino / "forja" / fid / "ficha.json", x)
    return Partida(destino)


def turno(p, cambios, narracion=""):
    """Cierra un turno en una partida (de prueba) con este bloque de cambios."""
    f = Ci.plantilla(p)
    f.write_text(f"## Narración\n\n{narracion}\n\n```cambios\n"
                 + json.dumps({"titulo": "prueba", "evento": "prueba", **cambios}, ensure_ascii=False) + "\n```\n", encoding="utf-8")
    return Ci.cerrar(p, f)


def probar(partida, fid):
    """Contrato, sin marcas de andamio, su test y un día simulado sobre una copia. Devuelve (ok, nota)."""
    from . import sistemas as S
    x = ficha(partida, fid)
    d = carpeta(partida) / fid
    x["estado"] = "probando"
    guardar(partida, x)

    def mal(nota):
        x["estado"], x["encendido"] = "fallo", False
        guardar(partida, x, nota)
        return False, nota
    if not (d / "sistema.py").exists():
        return mal("no hay sistema.py (¿«forja encargo»?)")
    for f in ("sistema.py", "test_sistema.py"):
        if (d / f).exists() and MARCA in (d / f).read_text(encoding="utf-8"):
            return mal(f"{f} aún tiene marcas «{MARCA}»: no está construido")
    try:
        mod = S.cargar_forja(partida, d, x)
    except SystemExit as ex:
        return mal(f"contrato: {ex}")
    sobra = set(mod.ESCRIBE) - set(x["escribe"])
    if sobra:
        return mal(f"escribe más de lo que dice su ficha: {', '.join(sorted(sobra))}")
    env = {**os.environ, "FORJA_PARTIDA": str(partida.dir), "FORJA_ID": fid, "FORJA_ENGINE": str(ENGINE)}
    if (d / "test_sistema.py").exists():
        r = subprocess.run([sys.executable, str(d / "test_sistema.py")], capture_output=True, text=True, env=env, timeout=300)
        if r.returncode:
            lineas = [x for x in (r.stderr or r.stdout).strip().splitlines() if x.strip()]
            causa = next((x for x in reversed(lineas) if "Error" in x or "assert" in x.lower()), lineas[-1] if lineas else "?")
            return mal("su test falla: " + causa.strip()[:300])
    else:
        return mal("falta test_sistema.py")
    os.environ.update(FORJA_PARTIDA=str(partida.dir), FORJA_ID=fid)
    try:
        p = copia_para_probar()
        r = turno(p, {"tiempo": {"dias": 1}})
        if any(a.startswith("🔨❌") and fid in a for a in r["avisos"]):
            return mal("se apaga solo al cerrar un día: " + next(a for a in r["avisos"] if a.startswith("🔨❌")))
    except SystemExit as ex:
        return mal(f"un día simulado no cierra: {ex}")
    x["estado"] = "listo"
    guardar(partida, x, "probado: test y un día simulado")
    return True, "listo"


def encender(partida, fid, on=True):
    x = ficha(partida, fid)
    if on and x["estado"] != "listo":
        raise SystemExit(f"forja: «{x['nombre']}» no está lista (está {x['estado'].replace('_', ' ')})")
    x["encendido"] = bool(on)
    if on:
        x["anunciado"] = False
    guardar(partida, x, "encendido" if on else "apagado")
    return x


def fallo_en_cierre(partida, fid, nota, simular):
    """El cierre lo ha apagado por fallar: queda apuntado (si el cierre es de verdad)."""
    if simular:
        return
    x = ficha(partida, fid)
    x.update(estado="fallo", encendido=False)
    guardar(partida, x, f"falló en el cierre: {nota}")


def al_guardar(partida, e, res):
    for x in fichas(partida):
        if x.get("encendido") and not x.get("anunciado"):
            x["anunciado"] = True
            guardar(partida, x)


def seccion_briefing(partida, e):
    xs = fichas(partida)
    if not xs:
        return []
    out = []
    nuevos = [x for x in xs if x.get("encendido") and not x.get("anunciado")]
    if nuevos:
        out.append("--- 🔨 NUEVO EN LA PARTIDA (nárralo como algo que llega o se descubre)")
        out += [f"  🔨 Nuevo sistema: {x['nombre']} · {x['como_se_nota']}" for x in nuevos]
    cuenta = {}
    for x in xs:
        k = "encendido" if x.get("encendido") else x["estado"]
        cuenta[k] = cuenta.get(k, 0) + 1
    pedidos = [x for x in xs if x["estado"] == "pedido"]
    out.append("--- forja: " + " · ".join(f"{n} {k.replace('_', ' ')}" for k, n in cuenta.items())
               + (f" · por fichar: {', '.join(x['nombre'] for x in pedidos)}" if pedidos else ""))
    return out


Ci.AL_GUARDAR.append(al_guardar)
B.SECCIONES.append(seccion_briefing)
