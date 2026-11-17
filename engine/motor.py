#!/usr/bin/env python3
"""Motor de rol por turnos, para cualquier mundo. Claude dirige; el motor recuerda y comprueba.

  motor.py nueva <carpeta> --mundo <carpeta_mundo> [--nombre N]   crea una partida vacía de un mundo
  motor.py -p <partida> briefing                                  lo que el director lee cada turno
  motor.py -p <partida> plantilla                                 cronica/turno_NNN.md del turno siguiente
  motor.py -p <partida> tirar [--mod N] [--cd N] [--ventaja|--desventaja] [motivo]
           tirar --quien <persona> --hab <habilidad> | --atributo des   el modificador lo pone la ficha
  motor.py -p <partida> cerrar cronica/turno_NNN.md [--simular]
  motor.py -p <partida> validar
  motor.py -p <partida> sistemas                                  el contrato de cada sistema encendido
  motor.py -p <partida> decisiones [tema]                         las decisiones de mundo de la partida
  motor.py -p <partida> constitucion                              la constitución del mundo
  motor.py -p <partida> orden <tipo> '<json>'                     una orden como las del panel (trabajo, ir)
  motor.py -p <partida> ordenes                                   las órdenes y su estado
  motor.py -p <partida> forja                                     lo que hay en la forja y su estado
           forja pedir "<nombre>" "<qué es>"                       un pedido («quiero que haya…»)
           forja ficha <id> '{"lee": […], "escribe": […], "produce": […], "datos": […], "como_se_nota": "…"}'
           forja encargo <id>                                     andamio + BRIEF.md para quien lo construye
           forja probar <id> · forja acoplar <id> · forja apagar <id>
  motor.py escuchar --todas                                       una línea por cada mensaje del jugador en CUALQUIER mesa:
                                                                  «MESA <partida> #N Jugador: …» o «EVENTO <partida> empezar»
  motor.py decir <partida> "texto"   (o «-» para leerlo de stdin)  el director contesta en la mesa de esa partida
  motor.py mundo nuevo <id> --nombre "…" [--icono 🏝]           un mundo inventado, vacío, y su partida en construcción
  motor.py mundo validar <id>                                     qué falta para jugarlo (✅/⬜)
  motor.py mundo listo <id>                                       si está todo: abre su partida para la sesión cero
  motor.py exportar <carpeta>                                    una copia limpia para regalar (sin nada privado), con git
  motor.py servir [--puerto 8800] [--lan] [--arrancar] [--hq]     el panel: HQ en «/», cada partida en «/p/<id>/»
                                                                  (--hq: también por el túnel de hq.json, si lo hay)
                                                                  (--arrancar: si EnSueño no está en marcha, la arranca)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nucleo import briefing as B, cierre as Ci, dados as D, partida as P, sistemas as S, tipos as T  # noqa: E402
from nucleo import constitucion as K  # noqa: E402  (engancha la constitución: decidir, anacronismos, briefing)
from nucleo import ordenes as O  # noqa: E402  (engancha las órdenes del panel: «ordenes», «ordenes_no», briefing)
from nucleo import fichas as F  # noqa: E402  (la ficha 5e: tirar con --quien/--hab, «aprender», su validador)
from nucleo import amenazas, trueque  # noqa: E402,F401  (el reloj de las amenazas y la orden «trocar»)
from nucleo import mesa as Me  # noqa: E402  (las mesas: escuchar al jugador en todas las partidas, decir en una)
from nucleo import mundos as Mu  # noqa: E402  (mundos inventados: nuevo, validar, listo)
from nucleo import forja as Fo  # noqa: E402  (la forja: pedir, fichar, encargar, probar y acoplar sistemas jugando)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Motor de rol por turnos")
    ap.add_argument("-p", "--partida", help="carpeta de la partida")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("nueva")
    n.add_argument("carpeta")
    n.add_argument("--mundo", required=True)
    n.add_argument("--nombre")
    sub.add_parser("briefing")
    sub.add_parser("plantilla")
    t = sub.add_parser("tirar")
    t.add_argument("motivo", nargs="?", default="")
    t.add_argument("--mod", type=int, default=0)
    t.add_argument("--cd", type=int)
    t.add_argument("--quien")
    t.add_argument("--hab")
    t.add_argument("--atributo")
    g = t.add_mutually_exclusive_group()
    g.add_argument("--ventaja", action="store_true")
    g.add_argument("--desventaja", action="store_true")
    c = sub.add_parser("cerrar")
    c.add_argument("cronica")
    c.add_argument("--simular", action="store_true")
    sub.add_parser("validar")
    sub.add_parser("sistemas")
    d = sub.add_parser("decisiones")
    d.add_argument("tema", nargs="?", default="")
    sub.add_parser("constitucion")
    o = sub.add_parser("orden")
    o.add_argument("tipo")
    o.add_argument("datos")
    sub.add_parser("ordenes")
    fo = sub.add_parser("forja")
    fo.add_argument("accion", nargs="?", default="lista", choices=["lista", "pedir", "ficha", "encargo", "probar", "acoplar", "apagar"])
    fo.add_argument("args", nargs="*")
    ex = sub.add_parser("exportar")
    ex.add_argument("carpeta")
    es = sub.add_parser("escuchar")
    es.add_argument("--todas", action="store_true", required=True)
    di = sub.add_parser("decir")
    di.add_argument("partida_id")
    di.add_argument("texto")
    mu = sub.add_parser("mundo")
    mu.add_argument("accion", choices=["nuevo", "validar", "listo"])
    mu.add_argument("id")
    mu.add_argument("--nombre")
    mu.add_argument("--icono")
    v = sub.add_parser("servir")
    v.add_argument("--puerto", type=int, default=8800)
    v.add_argument("--lan", action="store_true")
    v.add_argument("--arrancar", action="store_true")
    v.add_argument("--hq", action="store_true", help="también por el túnel de hq.json («tunel»), si este HQ lo tiene")
    a = ap.parse_args(argv)
    if a.cmd == "servir":
        import servidor
        servidor.servir(a.puerto, a.lan, a.arrancar, a.hq)
        return
    raiz = Path(__file__).resolve().parent.parent
    if a.cmd == "exportar":
        from nucleo import exportar
        d = exportar.exportar(raiz, a.carpeta)
        print(f"Copia limpia en {d}: abre Claude Code allí y dile «Arranca el juego».")
        return
    if a.cmd == "escuchar":
        Me.escuchar(raiz, lambda s: print(s, flush=True))
        return
    if a.cmd == "decir":
        texto = (sys.stdin.read() if a.texto == "-" else a.texto).strip()
        if not texto:
            raise SystemExit("Nada que decir.")
        f = Me.mesas(raiz).get(a.partida_id)
        if not f:
            raise SystemExit(f"decir: no hay partida '{a.partida_id}' (hay: {', '.join(Me.mesas(raiz))})")
        m = Me.escribir(f, "director", texto=texto)
        print(f"{a.partida_id}: mesa #{m['id']} ({len(texto)} car.)")
        return
    if a.cmd == "mundo":
        raiz = Path(__file__).resolve().parent.parent
        if a.accion == "nuevo":
            d, p = Mu.crear(raiz, a.id, a.nombre or a.id.replace("_", " ").capitalize(), a.icono)
            print(f"Mundo nuevo en {d} y su partida en {p.dir} (en construcción).\n" + Mu.texto_validar(Mu.validar(d)))
        elif a.accion == "validar":
            ap = Mu.validar(raiz / "mundos" / a.id)
            print(Mu.texto_validar(ap))
            print("→ todo listo: «mundo listo " + a.id + "»" if all(x["ok"] for x in ap) else "→ aún no se puede jugar")
        else:
            print("Listo para la sesión cero: " + (", ".join(Mu.listo(raiz, a.id)) or "(ninguna partida en construcción)"))
        return
    if a.cmd == "nueva":
        p = P.nueva(a.carpeta, a.mundo, a.nombre)
        print(f"Partida nueva en {p.dir} (mundo {p.mundo.id}).")
        return
    if not a.partida:
        raise SystemExit("Falta -p <carpeta de la partida>")
    p = P.Partida(a.partida)
    if a.cmd == "briefing":
        print(B.texto(p))
    elif a.cmd == "plantilla":
        print(Ci.plantilla(p))
    elif a.cmd == "tirar":
        mod, motivo = a.mod, a.motivo
        if a.quien:
            m, quien = F.mod_de(p.estado(), p.mundo, a.quien, a.hab, a.atributo)
            mod, motivo = mod + m, f"{quien}" + (f" · {a.motivo}" if a.motivo else "")
        elif a.hab or a.atributo:
            raise SystemExit("tirar: --hab y --atributo van con --quien")
        print(D.texto(D.tirar(p, mod, a.cd, a.ventaja, a.desventaja, motivo)))
    elif a.cmd == "cerrar":
        r = Ci.cerrar(p, a.cronica, a.simular)
        print(f"Turno {r['turno']} {'(simulado: no se guarda nada)' if a.simular else 'cerrado'} · {r['reloj']}")
        for x in r["creados"]:
            print("  nuevo:", x)
        for x in r["avisos"]:
            print("  aviso:", x)
        for x in r["decisiones"]:
            print("  decisión:", K.texto_decision(x))
    elif a.cmd == "validar":
        err = T.validar(p.estado(), p.mundo)
        print("\n".join(f"ERROR: {x}" for x in err) or "ok")
        if err:
            raise SystemExit(1)
    elif a.cmd == "decisiones":
        print("\n".join(K.texto_decision(x) for x in K.buscar(p.estado(), a.tema)) or "ninguna")
    elif a.cmd == "constitucion":
        print(p.mundo.constitucion or "(este mundo no tiene constitución)")
    elif a.cmd == "orden":
        try:
            datos = json.loads(a.datos)
        except json.JSONDecodeError as ex:
            raise SystemExit(f"orden: los datos no son JSON ({ex})")
        x = O.nueva(p, a.tipo, datos)
        print(f"#{x['id']} {x['texto']} · {x['estado'].replace('_', ' ')}")
    elif a.cmd == "ordenes":
        print("\n".join(f"#{x['id']} [{x['estado']}] {x['texto']}" + (f" · {x['motivo']}" if x.get("motivo") else "")
                        for x in O.lista(p)) or "ninguna")
    elif a.cmd == "forja":
        x = a.args
        if a.accion == "lista":
            print("\n".join(f"{f['id']} [{'encendido' if f.get('encendido') else f['estado']}] {f['nombre']} · {f['que']}"
                            for f in Fo.fichas(p)) or "la forja está vacía")
        elif a.accion == "pedir":
            if len(x) != 2:
                raise SystemExit('forja pedir "<nombre>" "<qué es>"')
            f = Fo.pedir(p, x[0], x[1], "director")
            print(f"Pedido: {f['id']} · ahora la ficha: forja ficha {f['id']} '{{\"lee\": [...], ...}}'")
        elif a.accion == "ficha":
            if len(x) != 2:
                raise SystemExit("forja ficha <id> '<json>'")
            try:
                campos = json.loads(x[1])
            except json.JSONDecodeError as ex:
                raise SystemExit(f"forja ficha: no es JSON ({ex})")
            print(json.dumps(Fo.fichar(p, x[0], campos), ensure_ascii=False, indent=1))
        elif not x:
            raise SystemExit(f"forja {a.accion} <id>")
        elif a.accion == "encargo":
            print(Fo.encargo(p, x[0]))
        elif a.accion == "probar":
            ok, nota = Fo.probar(p, x[0])
            print(("✓ " if ok else "✗ ") + nota)
            if not ok:
                raise SystemExit(1)
        else:
            f = Fo.encender(p, x[0], a.accion == "acoplar")
            print(f"{f['nombre']}: {'encendido (el briefing lo anuncia)' if f['encendido'] else 'apagado'}")
    elif a.cmd == "sistemas":
        print(json.dumps(S.contratos(p.mundo), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
