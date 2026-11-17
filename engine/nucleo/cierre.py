"""Cerrar un turno: la crónica (cronica/turno_NNN.md, con su «## Narración» y su bloque ```cambios```) se
aplica sobre una copia del estado, pasa el tiempo con los sistemas, se valida y, solo si todo cuadra, se guarda:
estado, timeline, mesa y archivo. Con simular no se escribe nada."""
import copy
import json
import re
from pathlib import Path
from . import cambios as C, reloj as R, sistemas as S, tipos as T

VALIDADORES = []     # fn(e, mundo, txt, c) → (errores, avisos): las fases siguientes añaden los suyos
AL_GUARDAR = []      # fn(partida, e, res): lo que se escribe aparte cuando el turno cierra de verdad


def leer(f):
    f = Path(f)
    if not f.exists():
        raise SystemExit(f"No existe el archivo: {f}")
    txt = f.read_text(encoding="utf-8")
    m = re.search(r"```cambios\s*\n(.*?)\n```", txt, re.S)
    if not m:
        raise SystemExit("La crónica no tiene bloque ```cambios```")
    try:
        c = json.loads(m.group(1))
    except json.JSONDecodeError as ex:
        raise SystemExit(f"El bloque de cambios no es JSON válido: {ex}")
    narr = txt.split("## Narración", 1)[1].split("```cambios", 1)[0].strip() if "## Narración" in txt else ""
    n = re.search(r"turno_(\d+)\.md$", f.name)
    return txt, narr, c, int(n.group(1)) if n else None


def cerrar(partida, archivo, simular=False):
    """Devuelve {"turno", "avisos", "texto"}. Para (SystemExit) si el turno no cuadra; entonces no se guarda nada.
    Si un sistema de la forja falla, se apaga y el cierre se rehace sin él (con un aviso «🔨❌»)."""
    from . import enganches
    enganches.cargar()                     # todos los validadores y claves, se haya importado lo que se haya importado
    apagados = {}
    while True:
        try:
            r = cerrar_una_vez(partida, archivo, simular, apagados)
        except S.ForjaFallo as f:
            if f.fid in apagados:
                raise SystemExit(f"forja {f.fid}: sigue fallando ({f.nota})")
            apagados[f.fid] = f.nota
            from . import forja
            forja.fallo_en_cierre(partida, f.fid, f.nota, simular)
            continue
        return r


def cerrar_una_vez(partida, archivo, simular, apagados):
    if partida.info.get("construccion"):
        raise SystemExit(f"El mundo de esta partida aún está en construcción: «motor mundo validar {partida.mundo.id}» dice "
                         f"qué falta, y «motor mundo listo {partida.mundo.id}» la abre para la sesión cero")
    txt, narr, c, n = leer(archivo)
    e0 = partida.estado()
    if n is not None and n != e0["turno"] + 1:
        raise SystemExit(f"Este archivo es el turno {n}, pero toca el {e0['turno'] + 1}")
    e, mundo = copy.deepcopy(e0), partida.mundo
    res = C.aplicar(e, c, mundo, partida)
    hechas = {t["n"] for t in leer_dados(partida)}
    malas = [t for t in c.get("tiradas", []) if t not in hechas]
    if malas:
        raise SystemExit(f"tiradas: {malas} no están en dados.jsonl (usa `motor tirar`)")
    sis = S.cargar(mundo, partida, excluir=apagados)
    ses = S.Sesion(e, mundo)
    R.avanzar(ses, res["horas"], sis)
    for s in sis:
        S.correr(s, "al_cerrar", ses)
    avisos = []
    for s in sis:
        avisos += S.correr(s, "informe", ses) or []
    errores = T.validar(e, mundo)
    for v in VALIDADORES:
        er, av = v(e, mundo, narr, c)
        errores += er
        avisos += av
    if errores:
        raise SystemExit("No cierra:\n" + "\n".join(f"  ERROR: {x}" for x in errores))
    avisos = [f"🔨❌ «{fid}» de la forja ha fallado y se ha apagado: {nota}" for fid, nota in apagados.items()] + avisos
    e["turno"] += 1
    e["avisos"] = avisos
    e["timeline"].append({"turno": e["turno"], "titulo": c["titulo"], "evento": c["evento"], "dia": e["reloj"]["dia"],
                          "hora": e["reloj"]["hora"], "tiradas": c.get("tiradas", []), "avisos": avisos})
    if not simular:
        partida.guardar(e)
        from . import mesa
        mesa.escribir(partida.dir / "mesa.jsonl", "motor", tipo="turno", turno=e["turno"], titulo=c["titulo"], avisos=avisos)
        for q in res["quitados"]:
            partida.anotar("archivo.jsonl", q)
        for fn in AL_GUARDAR:
            fn(partida, e, res)
    return {"turno": e["turno"], "avisos": avisos, "reloj": R.texto(e["reloj"]), "creados": res["creados"],
            "decisiones": res.get("decisiones", [])}


def leer_dados(partida):
    f = partida.dir / "dados.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []


def plantilla(partida):
    """Escribe cronica/turno_NNN.md (el siguiente) con su esqueleto, si no existe. Devuelve su ruta."""
    n = partida.estado()["turno"] + 1
    f = partida.cronica / f"turno_{n:03d}.md"
    if not f.exists():
        f.write_text(f"# Turno {n}\n\n## Narración\n\n\n```cambios\n"
                     + json.dumps({"titulo": "", "evento": "", "tiempo": {"horas": 1}}, ensure_ascii=False) + "\n```\n",
                     encoding="utf-8")
    return f
