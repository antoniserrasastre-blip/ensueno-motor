"""Tests del trueque con Ebusus y del reloj de las naves de Roma (mundo Baleares)."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
from nucleo import amenazas, briefing as B, cierre as Ci, ordenes as O, partida as P, trueque as Tq  # noqa: E402,F401

MUNDO = ENGINE.parent / "mundos" / "baleares_123"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="engine_tq_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.p = P.nueva(self.tmp / "p", MUNDO)
        e = self.p.estado()
        e["colecciones"]["personas"]["arro"] = {"nombre": "Arro", "donde": "ses_paisses", "tuyo": True}
        for k, n in {"lana": 30, "queso": 10, "leche": 40}.items():
            e["colecciones"]["objetos"][f"{k}@ses_paisses"] = {"nombre": k, "cantidad": n, "donde": "ses_paisses", "base": k}
        self.p.guardar(e)

    def cerrar(self, c):
        f = Ci.plantilla(self.p)
        f.write_text("## Narración\n\n```cambios\n" + json.dumps({"titulo": "x", "evento": "x", **c}) + "\n```\n")
        return Ci.cerrar(self.p, f)

    def obj(self, oid):
        return self.p.estado()["colecciones"]["objetos"].get(oid, {}).get("cantidad", 0)


class Trueque(Base):
    def test_la_balanza(self):
        b = Tq.balanza(self.p.mundo, "ebusus", {"lana": 20}, {"vino": 5})
        self.assertEqual((b["das"], b["pides"], b["acepta"]), (52.0, 46.0, True))           # 20×2×1.3 · 5×8×1.15
        self.assertFalse(Tq.balanza(self.p.mundo, "ebusus", {"lana": 5}, {"vino": 5})["acepta"])

    def test_un_trueque_con_ebusus(self):
        d = {"persona": "arro", "mercado": "ebusus", "desde": "ses_paisses", "da": {"lana": 20}, "pide": {"vino": 5}}
        o = O.nueva(self.p, "trocar", d)
        self.assertEqual(o["estado"], "para_narrar")
        self.assertEqual(self.obj("lana@ses_paisses"), 30)                                  # aún no
        self.cerrar({"ordenes": [o["id"]]})
        self.assertEqual((self.obj("lana@ses_paisses"), self.obj("vino@ses_paisses")), (10, 5))
        self.assertEqual(self.p.estado()["colecciones"]["objetos"]["vino@ses_paisses"]["nombre"], "Vino")

    def test_lo_que_no_vale(self):
        casos = [({"da": {"lana": 50}, "pide": {"vino": 1}}, "no tienes 50 lana"),
                 ({"da": {"lana": 5}, "pide": {"vino": 5}}, "no acepta"),
                 ({"da": {"lana": 30}, "pide": {"oro": 1}}, "sin valor"),
                 ({"da": {"lana": 30}, "pide": {"vino": 999}}, "no tiene 999 vino"),
                 ({"mercado": "roma", "da": {"lana": 1}, "pide": {"vino": 1}}, "no hay mercado")]
        for extra, msg in casos:
            d = {"persona": "arro", "mercado": "ebusus", "desde": "ses_paisses", **extra}
            with self.assertRaises(SystemExit) as ctx:
                O.nueva(self.p, "trocar", d)
            self.assertIn(msg, str(ctx.exception))

    def test_si_al_narrar_ya_no_hay_lo_que_se_daba_no_cierra(self):
        o = O.nueva(self.p, "trocar", {"persona": "arro", "mercado": "ebusus", "desde": "ses_paisses",
                                       "da": {"lana": 20}, "pide": {"vino": 5}})
        e = self.p.estado()
        e["colecciones"]["objetos"]["lana@ses_paisses"]["cantidad"] = 3
        self.p.guardar(e)
        with self.assertRaises(SystemExit) as ctx:
            self.cerrar({"ordenes": [o["id"]]})
        self.assertIn("ya no vale", str(ctx.exception))


class NavesDeRoma(Base):
    def test_el_reloj_avisa_al_cruzar_y_el_director_lo_mueve(self):
        self.assertIn("Las naves de Roma: faltan 119 días", B.texto(self.p))
        r = self.cerrar({"tiempo": {"dias": 95}})                                          # día 96: faltan 24
        self.assertTrue(any("faltan 24 días" in a for a in r["avisos"]), r["avisos"])
        r = self.cerrar({"tiempo": {"dias": 1}})
        self.assertFalse(any("naves" in a for a in r["avisos"]))                           # mismo umbral: no repite
        self.cerrar({"cambiar": {"amenaza:naves_roma": {"dia": 200}}})                     # los honderos lo retrasan
        self.assertIn("faltan 103 días", B.texto(self.p))
        r = self.cerrar({"tiempo": {"dias": 110}})
        self.assertTrue(any("ya está aquí" in a for a in r["avisos"]))
        self.cerrar({"cambiar": {"amenaza:naves_roma": {"llego": True}}})
        self.assertNotIn("Las naves de Roma", B.texto(self.p))


if __name__ == "__main__":
    unittest.main(verbosity=1)
