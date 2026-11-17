"""Tests de la ficha 5e: modificadores, tiradas con la ficha, aprender y el validador."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_nucleo import Base  # noqa: E402
from nucleo import fichas as F, ordenes as O  # noqa: E402


class Ficha(Base):
    def test_modificadores_del_srd(self):
        self.assertEqual([F.mod(v) for v in (1, 8, 9, 10, 11, 15, 20)], [-5, -1, -1, 0, 0, 2, 5])
        self.assertEqual([F.competencia(n) for n in (1, 4, 5, 9, 13, 17, 20)], [2, 2, 3, 4, 5, 6, 6])

    def test_la_tirada_la_pone_la_ficha(self):
        e = self.p.estado()
        self.assertEqual(F.mod_de(e, self.p.mundo, "abi", "honda")[0], 2 + 3)       # DES 15 y competente (nivel 5)
        self.assertEqual(F.mod_de(e, self.p.mundo, "abi", "pastoreo")[0], 1)        # SAB 13, no competente
        self.assertEqual(F.mod_de(e, self.p.mundo, "abi", atributo="car")[0], -1)
        r = self.motor("tirar", "--quien", "abi", "--hab", "honda", "--cd", "12", "al cuervo")
        self.assertRegex(r.stdout, r"\+5 = \d+ vs CD 12")
        self.assertIn("Abi · Honda (Destreza +2, competencia +3) · al cuervo", r.stdout)
        for args, msg in [(["--quien", "nadie", "--hab", "honda"], "no existe la persona"),
                          (["--quien", "forastero", "--hab", "honda"], "no tiene ficha"),
                          (["--quien", "abi", "--hab", "volar"], "no existe en este mundo"),
                          (["--hab", "honda"], "van con --quien")]:
            self.assertIn(msg, self.motor("tirar", *args, ok=False).stderr)

    def test_aprender_gasta_un_punto(self):
        o = O.nueva(self.p, "aprender", {"persona": "abi", "habilidad": "pastoreo"})
        self.assertEqual(o["estado"], "aplicada")
        f = self.p.estado()["colecciones"]["personas"]["abi"]["ficha"]
        self.assertEqual((f["competencias"], f["puntos"]), (["honda", "pastoreo"], 0))
        with self.assertRaises(SystemExit) as ctx:
            O.nueva(self.p, "aprender", {"persona": "abi", "habilidad": "pastoreo"})
        self.assertIn("no tiene puntos", str(ctx.exception))

    def test_una_ficha_mal_hecha_no_cierra(self):
        for ficha in [{"atributos": {"fue": 10}}, {"atributos": {k: 10 for k in F.ATRIBUTOS}, "competencias": ["volar"]},
                      {"atributos": {k: 10 for k in F.ATRIBUTOS}, "pg": {"max": 5, "actual": 9}}]:
            with self.assertRaises(SystemExit) as ctx:
                self.turno({"cambiar": {"persona:abi": {"ficha": ficha}}})
            self.assertIn("ficha de abi", str(ctx.exception))
        self.turno({"cambiar": {"persona:abi": {"ficha": {"atributos": {k: 12 for k in F.ATRIBUTOS}, "nivel": 2}}}})


if __name__ == "__main__":
    unittest.main(verbosity=1)
