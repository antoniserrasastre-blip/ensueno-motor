"""Tests de los sistemas portados (clima, trabajo, comida, ánimo) sobre el mundo de verdad, Baleares 123."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
from nucleo import cierre as Ci, partida as P, sistemas as S  # noqa: E402

MUNDO = ENGINE.parent / "mundos" / "baleares_123"
DIEZ = {k: 10 for k in ("fue", "des", "con", "int", "sab", "car")}


class Baleares(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="engine_sis_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.p = P.nueva(self.tmp / "p", MUNDO)

    def gente(self, personas, objetos=None):
        e = self.p.estado()
        e["colecciones"]["personas"].update(personas)
        for oid, (q, lugar) in (objetos or {}).items():
            e["colecciones"]["objetos"][f"{oid}@{lugar}"] = {"nombre": oid, "cantidad": q, "donde": lugar, "base": oid}
        self.p.guardar(e)

    def pasar(self, **tiempo):
        f = Ci.plantilla(self.p)
        f.write_text("## Narración\n\n```cambios\n" + json.dumps({"titulo": "x", "evento": "x", "tiempo": tiempo}) + "\n```\n")
        return Ci.cerrar(self.p, f)

    def obj(self, oid):
        return self.p.estado()["colecciones"]["objetos"].get(oid, {}).get("cantidad", 0)

    def test_contratos(self):
        sis = {s.NOMBRE: s for s in S.cargar(self.p.mundo)}
        self.assertEqual(list(sis), ["clima", "trabajo", "comida", "animo"])

    def test_el_clima_es_fijo_por_dia_y_sigue_la_estacion(self):
        self.pasar(dias=3)
        c1 = self.p.estado()["reloj"]["clima"]
        p2 = P.nueva(self.tmp / "p2", MUNDO)
        f = Ci.plantilla(p2)
        f.write_text('## Narración\n\n```cambios\n{"titulo": "x", "evento": "x", "tiempo": {"dias": 3}}\n```\n')
        Ci.cerrar(p2, f)
        self.assertEqual(p2.estado()["reloj"]["clima"], c1)
        self.assertEqual(self.p.estado()["reloj"]["estacion"], "primavera")
        self.pasar(dias=95)
        self.assertEqual(self.p.estado()["reloj"]["estacion"], "verano")

    def test_la_tabla_produce_por_prioridad_y_si_falta_pasa_a_la_siguiente(self):
        # sin trigo, Bec no puede moler (prioridad 1) y labra (prioridad 2)
        self.gente({"bec": {"nombre": "Bec", "donde": "ses_paisses", "tuyo": True, "trabajos": {"moler": 1, "labrar": 2}},
                    "ama": {"nombre": "Ama", "donde": "ses_paisses", "tuyo": True, "trabajos": {"vigilar": 1}}},
                   {"queso": (50, "ses_paisses")})
        r = self.pasar(dias=1)
        self.assertTrue(any("Bec no pudo moler: falta trigo" in a for a in r["avisos"]))
        self.assertGreater(self.obj("trigo@ses_paisses"), 0)
        self.assertEqual(self.obj("pan@ses_paisses"), 0)

    def test_con_competencia_rinde_mas(self):
        f = {"atributos": DIEZ, "competencias": ["pesca"]}
        self.gente({"a": {"nombre": "A", "donde": "ses_paisses", "tuyo": True, "trabajos": {"pescar": 1}, "ficha": f},
                    "b": {"nombre": "B", "donde": "capocorb_vell", "tuyo": True, "trabajos": {"pescar": 1}}},
                   {"leche": (50, "ses_paisses")})
        self.gente({}, {"leche": (50, "capocorb_vell")})                # se come la leche antes que el pescado
        self.pasar(dias=1)
        rinde = self.p.estado()["reloj"]["clima"]["rinde"]
        self.assertAlmostEqual(self.obj("pescado@ses_paisses"), round(3 * 1.25 * rinde, 2))
        self.assertAlmostEqual(self.obj("pescado@capocorb_vell"), round(3 * rinde, 2))

    def test_sin_comida_hay_hambre_y_baja_el_animo(self):
        self.gente({"bec": {"nombre": "Bec", "donde": "ses_paisses", "tuyo": True}})
        r = self.pasar(dias=3)
        bec = self.p.estado()["colecciones"]["personas"]["bec"]
        self.assertEqual(bec["hambre"], 3)
        self.assertTrue(any("Falta comida" in a for a in r["avisos"]))
        self.assertIn("tiene hambre", [m[0] for m in bec["animo_motivos"]])
        self.assertLessEqual(bec["animo"], 2 - 6 + 1)                               # base 2, hambre −6, el tiempo ±1
        self.gente({}, {"queso": (10, "ses_paisses")})
        self.pasar(dias=1)
        self.assertNotIn("hambre", self.p.estado()["colecciones"]["personas"]["bec"])

    def test_los_que_no_son_tuyos_ni_comen_ni_trabajan(self):
        self.gente({"mercader": {"nombre": "Bodmilqart", "donde": "ses_paisses", "trabajos": {"pescar": 1}}})
        self.pasar(dias=2)
        self.assertEqual(self.obj("pescado@ses_paisses"), 0)
        self.assertNotIn("hambre", self.p.estado()["colecciones"]["personas"]["mercader"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
