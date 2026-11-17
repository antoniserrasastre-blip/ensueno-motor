"""Tests de la forja: pedir, fichar, encargar, construir, probar, acoplar en caliente, y la red de seguridad (una pieza
que falla o toca lo que no declara se apaga sola sin romper la partida)."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
from nucleo import briefing as B, cierre as Ci, forja as F, partida as P  # noqa: E402

MUNDO = ENGINE.parent / "mundos" / "baleares_123"
CABALLOS = '''"""Cría de caballos: las yeguas paren potros en primavera."""
NOMBRE = "cria_caballos"
LEE = ["objetos", "reloj"]
ESCRIBE = ["objetos"]
PRODUCE = ["aviso:potros"]
DATOS = ["caballos"]


def cada_dia(s, dia):
    for oid, o in list(s.col["objetos"].items()):
        if o.get("base") == "yeguas":
            potros = s.col["objetos"].setdefault(oid.replace("yeguas", "potros"), {"nombre": "Potros", "cantidad": 0,
                                                                                    "donde": o["donde"], "base": "potros"})
            potros["cantidad"] = round(potros["cantidad"] + o["cantidad"] * s.datos["caballos"]["potros_por_yegua_dia"], 2)
            s.inc["potros"] = True


def informe(s):
    return ["🐴 Han nacido potros"] if s.inc.get("potros") else []
'''
TEST = '''import os, sys, unittest
sys.path.insert(0, os.environ["FORJA_ENGINE"])
from nucleo import forja as F


class Prueba(unittest.TestCase):
    def test_paren(self):
        p = F.copia_para_probar()
        e = p.estado()
        e["colecciones"]["objetos"]["yeguas@ses_paisses"] = {"nombre": "Yeguas", "cantidad": 10, "donde": "ses_paisses", "base": "yeguas"}
        p.guardar(e)
        F.turno(p, {"tiempo": {"dias": 2}})
        self.assertGreater(p.estado()["colecciones"]["objetos"]["potros@ses_paisses"]["cantidad"], 0)


if __name__ == "__main__":
    unittest.main()
'''


class Forja(unittest.TestCase):
    def setUp(self):
        # en una carpeta honda: la copia de prueba va a otro sitio y el mundo (relativo) tiene que seguir encontrándose
        self.tmp = Path(tempfile.mkdtemp(prefix="engine_forja_")) / "a" / "b"
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.p = P.nueva(self.tmp / "p", MUNDO)
        e = self.p.estado()
        e["colecciones"]["objetos"]["yeguas@ses_paisses"] = {"nombre": "Yeguas", "cantidad": 4, "donde": "ses_paisses", "base": "yeguas"}
        self.p.guardar(e)

    def construir(self, codigo=CABALLOS, test=TEST):
        f = F.pedir(self.p, "Cría de caballos", "que las yeguas del poblado den potros", "jugador")
        F.fichar(self.p, f["id"], {"lee": ["objetos", "reloj"], "escribe": ["objetos"], "produce": ["aviso:potros"],
                                   "datos": ["caballos"], "como_se_nota": "salen potros en «Lo que hay»"})
        brief = F.encargo(self.p, f["id"])
        self.assertIn("Solo puede tocar lo que declara", brief)
        d = self.p.dir / "forja" / f["id"]
        (d / "sistema.py").write_text(codigo)
        (d / "test_sistema.py").write_text(test)
        (d / "datos" / "caballos.json").write_text('{"potros_por_yegua_dia": 0.05}')
        return f["id"]

    def turno(self, cambios=None):
        f = Ci.plantilla(self.p)
        f.write_text("## Narración\n\n```cambios\n" + json.dumps({"titulo": "x", "evento": "x", **(cambios or {"tiempo": {"dias": 1}})}) + "\n```\n")
        return Ci.cerrar(self.p, f)

    def test_de_pedido_a_partida_sin_pararla(self):
        fid = self.construir()
        self.assertEqual(F.ficha(self.p, fid)["estado"], "en_obra")
        ok, nota = F.probar(self.p, fid)
        self.assertTrue(ok, nota)
        self.assertEqual(F.ficha(self.p, fid)["estado"], "listo")
        self.turno()                                                            # listo pero apagado: no hace nada
        self.assertNotIn("potros@ses_paisses", self.p.estado()["colecciones"]["objetos"])
        F.encender(self.p, fid)
        self.assertIn("🔨 Nuevo sistema: Cría de caballos", B.texto(self.p))
        r = self.turno()
        self.assertIn("🐴 Han nacido potros", r["avisos"])
        self.assertAlmostEqual(self.p.estado()["colecciones"]["objetos"]["potros@ses_paisses"]["cantidad"], 0.2)
        self.assertNotIn("🔨 Nuevo sistema", B.texto(self.p))                  # anunciado una vez
        F.encender(self.p, fid, False)
        self.turno()
        self.assertAlmostEqual(self.p.estado()["colecciones"]["objetos"]["potros@ses_paisses"]["cantidad"], 0.2)

    def test_el_andamio_sin_construir_no_pasa(self):
        f = F.pedir(self.p, "Oráculo", "un oráculo en la cueva")
        with self.assertRaises(SystemExit):
            F.encargo(self.p, f["id"])                                          # sin ficha no hay encargo
        F.fichar(self.p, f["id"], {"lee": ["personas"], "escribe": [], "como_se_nota": "el oráculo habla"})
        F.encargo(self.p, f["id"])
        ok, nota = F.probar(self.p, f["id"])
        self.assertFalse(ok)
        self.assertIn("marcas", nota)
        with self.assertRaises(SystemExit):
            F.encender(self.p, f["id"])

    def test_escribir_mas_de_lo_fichado_no_pasa(self):
        fid = self.construir(CABALLOS.replace('ESCRIBE = ["objetos"]', 'ESCRIBE = ["objetos", "personas"]'))
        ok, nota = F.probar(self.p, fid)
        self.assertFalse(ok)
        self.assertIn("escribe más de lo que dice su ficha", nota)

    def test_su_test_tiene_que_pasar(self):
        fid = self.construir(test=TEST.replace("assertGreater", "assertLess"))
        ok, nota = F.probar(self.p, fid)
        self.assertFalse(ok)
        self.assertIn("su test falla", nota)

    def test_si_falla_en_el_cierre_se_apaga_solo_y_la_partida_sigue(self):
        fid = self.construir()
        self.assertTrue(F.probar(self.p, fid)[0])
        F.encender(self.p, fid)
        d = self.p.dir / "forja" / fid
        for roto in (CABALLOS.replace('s.inc["potros"] = True', 'raise ValueError("yegua coja")'),
                     CABALLOS.replace('s.inc["potros"] = True', 's.col["personas"]["x"] = {"nombre": "x", "donde": "ses_paisses"}')):
            x = F.ficha(self.p, fid)
            x.update(estado="listo", encendido=True)
            F.guardar(self.p, x)
            (d / "sistema.py").write_text(roto)
            turno0 = self.p.estado()["turno"]
            r = self.turno()
            self.assertEqual(self.p.estado()["turno"], turno0 + 1)              # la partida sigue
            self.assertTrue(r["avisos"][0].startswith(f"🔨❌ «{fid}»"), r["avisos"])
            x = F.ficha(self.p, fid)
            self.assertEqual((x["estado"], x["encendido"]), ("fallo", False))
        self.assertIn("ESCRIBE", r["avisos"][0])

    def test_por_la_linea_de_ordenes(self):
        import subprocess
        m = lambda *a: subprocess.run([sys.executable, str(ENGINE / "motor.py"), "-p", str(self.p.dir), "forja", *a], capture_output=True, text=True)
        r = m("pedir", "La religión", "los santuarios y sus fiestas")
        self.assertIn("Pedido: la_religion", r.stdout)
        self.assertIn("[pedido] La religión", m().stdout)
        self.assertIn("no está hecha", m("encargo", "la_religion").stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
