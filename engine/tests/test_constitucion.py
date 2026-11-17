"""Tests de la constitución: anacronismos, catálogo, decidir y briefing (sobre el mundo de prueba)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_nucleo import Base  # noqa: E402
from nucleo import briefing as B, constitucion as K  # noqa: E402,F401


class Anacronismos(Base):
    def test_lo_que_no_existe_no_cierra_ni_en_la_narracion(self):
        for narr, c in [("Abi oye un cañonazo y huele a pólvora.", {}),
                        ("", {"crear": [{"tipo": "objeto", "nombre": "Cañones", "cantidad": 2, "donde": "poblado"}]})]:
            with self.assertRaises(SystemExit) as ctx:
                self.turno(c, narr)
            self.assertIn("anacronismo", str(ctx.exception))
        self.assertEqual(self.p.estado()["turno"], 0)

    def test_decidir_lo_permite_y_queda_escrito(self):
        r = self.turno({"decidir": {"que": "Llega la pólvora de un náufrago", "porque": "lo pide la historia",
                                    "permite": ["pólvora"]}}, "Abi encuentra un barril de pólvora.")
        self.assertEqual(len(r["decisiones"]), 1)
        f = list((self.p.dir / "decisiones").glob("*.md"))
        self.assertEqual(len(f), 1)
        self.assertIn("lo pide la historia", f[0].read_text())
        self.turno({}, "Y luego un cañón.")                    # desde entonces, ya no para
        self.assertIn("pólvora", self.motor("decisiones", "náufrago").stdout)

    def test_lo_de_fuera_avisa_solo_si_entra_en_el_estado(self):
        r = self.turno({}, "En la ciudad pagan con moneda.")
        self.assertFalse(any("moneda" in a for a in r["avisos"]))
        r = self.turno({"crear": [{"tipo": "objeto", "nombre": "Moneda", "cantidad": 3, "donde": "poblado",
                                   "nuevo_en_mundo": True}]})
        self.assertTrue(any("«moneda» es de la ciudad: ¿lo tienes?" in a for a in r["avisos"]), r["avisos"])

    def test_palabras_enteras(self):
        self.turno({}, "Abi canta una canción.")              # «cañón» no casa dentro de «canción»


class Catalogo(Base):
    def test_lo_que_no_esta_en_el_catalogo_pregunta(self):
        r = self.turno({"crear": [{"tipo": "objeto", "nombre": "Telescopio", "cantidad": 1, "donde": "poblado"}]})
        self.assertTrue(any("no está en el catálogo" in a for a in r["avisos"]))
        r = self.turno({"crear": [{"tipo": "objeto", "nombre": "Honda", "cantidad": 3, "donde": "poblado"}]})
        self.assertFalse(any("catálogo" in a for a in r["avisos"]))

    def test_nuevo_en_mundo_se_acepta_y_queda_como_decision(self):
        r = self.turno({"crear": [{"tipo": "objeto", "nombre": "Rueda de alfarero", "cantidad": 1, "donde": "poblado",
                                   "nuevo_en_mundo": True, "porque": "la enseña un mercader de Ebusus"}]})
        self.assertFalse(any("catálogo" in a for a in r["avisos"]))
        self.assertIn("Rueda de alfarero", self.p.estado()["decisiones"][0]["que"])

    def test_decidir_mal_formado(self):
        with self.assertRaises(SystemExit):
            self.turno({"decidir": {"que": "algo"}})


class Briefing(Base):
    def test_la_constitucion_va_arriba_y_las_decisiones_debajo(self):
        self.turno({"decidir": {"que": "El río no se cruza en invierno", "porque": "crecidas"}})
        b = self.motor("briefing").stdout
        self.assertLess(b.index("CONSTITUCIÓN"), b.index("hay:"))
        self.assertIn("NO EXISTE   pólvora", b)
        self.assertIn("T1 · El río no se cruza en invierno", b)
        self.assertIn("ÉPOCA", self.motor("constitucion").stdout)


class SinImportarNada(Base):
    def test_el_cierre_trae_sus_validadores_aunque_solo_se_importe_el_cierre(self):
        """Un proceso nuevo que solo importa el cierre: el anacronismo tiene que parar igual (antes dependía del orden
        en que se importaban los tests)."""
        import subprocess
        f = self.p.cronica / "turno_001.md"
        f.write_text('## Narración\n\nHuele a pólvora.\n\n```cambios\n{"titulo": "x", "evento": "x"}\n```\n', encoding="utf-8")
        codigo = ("import sys; sys.path.insert(0, sys.argv[1]); from nucleo import cierre, partida\n"
                  "try:\n    cierre.cerrar(partida.Partida(sys.argv[2]), sys.argv[3])\n    print('CERRÓ')\n"
                  "except SystemExit as ex:\n    print('PARADO', ex)")
        r = subprocess.run([sys.executable, "-c", codigo, str(Path(__file__).resolve().parents[1]), str(self.p.dir), str(f)],
                           capture_output=True, text=True)
        self.assertIn("PARADO", r.stdout, r.stdout + r.stderr)
        self.assertIn("anacronismo", r.stdout)


class MundoBaleares(unittest.TestCase):
    """El mundo de verdad: arranca, valida y su constitución hace su trabajo."""
    def setUp(self):
        import shutil, tempfile
        from nucleo import partida as P
        self.tmp = Path(tempfile.mkdtemp(prefix="engine_baleares_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.p = P.nueva(self.tmp / "p", Path(__file__).resolve().parents[2] / "mundos" / "baleares_123")

    def cerrar(self, c, narr=""):
        import json
        from nucleo import cierre as Ci
        f = Ci.plantilla(self.p)
        f.write_text(f"## Narración\n\n{narr}\n\n```cambios\n{json.dumps({'titulo': 'x', 'evento': 'x', **c})}\n```\n")
        return Ci.cerrar(self.p, f)

    def test_arranca_y_valida(self):
        from nucleo import tipos as T
        self.assertEqual(T.validar(self.p.estado(), self.p.mundo), [])
        self.assertIn("NO EXISTE", self.p.mundo.constitucion)

    def test_frases_normales_no_paran(self):
        r = self.cerrar({}, "En torno al fuego, cada uno hace su papel; el cielo se pone naranja y llegan noticias de "
                            "Roma: legionarios, un cónsul y monedas de plata.")
        self.assertEqual(r["turno"], 1)

    def test_lo_de_roma_avisa_y_la_polvora_para(self):
        r = self.cerrar({"crear": [{"tipo": "objeto", "nombre": "Denarios", "cantidad": 5, "donde": "ses_paisses",
                                    "nuevo_en_mundo": True}]})
        self.assertTrue(any("«denarios» es de fuera" in a for a in r["avisos"]), r["avisos"])
        with self.assertRaises(SystemExit):
            self.cerrar({}, "Huele a pólvora.")


if __name__ == "__main__":
    unittest.main(verbosity=1)
