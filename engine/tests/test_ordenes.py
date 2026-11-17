"""Tests de las órdenes del panel: la tabla de trabajos (al momento) y las que se narran (ir a otro sitio)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_nucleo import Base  # noqa: E402
from nucleo import ordenes as O  # noqa: E402


class Trabajos(Base):
    def test_se_aplica_al_momento(self):
        o = O.nueva(self.p, "trabajo", {"persona": "abi", "trabajo": "labrar", "prioridad": 1})
        self.assertEqual(o["estado"], "aplicada")
        self.assertEqual(self.p.estado()["colecciones"]["personas"]["abi"]["trabajos"], {"labrar": 1})
        O.nueva(self.p, "trabajo", {"persona": "abi", "trabajo": "labrar", "prioridad": 0})
        self.assertEqual(self.p.estado()["colecciones"]["personas"]["abi"]["trabajos"], {})
        self.assertIn("hecho en el panel", self.motor("briefing").stdout)

    def test_lo_que_no_vale_no_se_guarda(self):
        for d, msg in [({"persona": "nadie", "trabajo": "labrar", "prioridad": 1}, "no existe la persona"),
                       ({"persona": "abi", "trabajo": "volar", "prioridad": 1}, "no existe en este mundo"),
                       ({"persona": "abi", "trabajo": "labrar", "prioridad": 9}, "prioridad"),
                       ({"persona": "forastero", "trabajo": "labrar", "prioridad": 1}, "no es de los tuyos")]:
            with self.assertRaises(SystemExit) as ctx:
                O.nueva(self.p, "trabajo", d)
            self.assertIn(msg, str(ctx.exception))
        with self.assertRaises(SystemExit):
            O.nueva(self.p, "volar", {})
        self.assertEqual(O.lista(self.p), [])


class Narrar(Base):
    def test_ir_espera_al_director_y_el_turno_la_aplica(self):
        o = O.nueva(self.p, "ir", {"persona": "abi", "a": "monte"})
        self.assertEqual(o["estado"], "para_narrar")
        self.assertEqual(self.p.estado()["colecciones"]["personas"]["abi"]["donde"], "poblado")   # aún no
        self.assertIn(f"#{o['id']} Abi va a El monte", self.motor("briefing").stdout)
        self.turno({"ordenes": [o["id"]]})
        self.assertEqual(self.p.estado()["colecciones"]["personas"]["abi"]["donde"], "monte")
        self.assertEqual(O.lista(self.p)[0]["estado"], "narrada")
        with self.assertRaises(SystemExit):
            self.turno({"ordenes": [o["id"]]})                     # una vez narrada, no se repite

    def test_rechazar_con_motivo(self):
        o = O.nueva(self.p, "ir", {"persona": "abi", "a": "monte"})
        self.turno({"ordenes_no": {str(o["id"]): "hay tormenta"}})
        x = O.lista(self.p)[0]
        self.assertEqual((x["estado"], x["motivo"]), ("rechazada", "hay tormenta"))
        self.assertEqual(self.p.estado()["colecciones"]["personas"]["abi"]["donde"], "poblado")

    def test_simular_no_marca_nada(self):
        o = O.nueva(self.p, "ir", {"persona": "abi", "a": "monte"})
        self.turno({"ordenes": [o["id"]]}, simular=True)
        self.assertEqual(O.lista(self.p)[0]["estado"], "para_narrar")

    def test_por_la_linea_de_ordenes(self):
        r = self.motor("orden", "trabajo", '{"persona": "abi", "trabajo": "pastorear", "prioridad": 2}')
        self.assertIn("aplicada", r.stdout)
        self.assertIn("[aplicada]", self.motor("ordenes").stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
