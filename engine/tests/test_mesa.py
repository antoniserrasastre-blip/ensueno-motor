"""Tests de la mesa: los botones que hablan solos, escuchar todas las mesas (también la de EnSueño) y decir."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
from nucleo import mesa as Me, partida as P  # noqa: E402


class Mesa(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="engine_mesa_"))
        self.addCleanup(shutil.rmtree, self.raiz, True)
        shutil.copytree(ENGINE.parent / "mundos" / "baleares_123", self.raiz / "mundos" / "baleares_123")
        self.p = P.nueva(self.raiz / "partidas" / "baleares_1", self.raiz / "mundos" / "baleares_123")
        (self.raiz / "partida").mkdir()
        self.vieja = self.raiz / "partida" / "mesa.jsonl"
        Me.escribir(self.vieja, "toni", texto="hola")
        Me.escribir(self.vieja, "director", texto="buenas")
        (self.raiz / "hq.json").write_text(json.dumps({"jugador": "Toni", "externas": [{"id": "ensueno", "nombre": "EnSueño", "ruta": "/ensueno/",
                                                                     "mesa": "partida/mesa.jsonl"}]}))

    def test_formato_como_el_de_ensueno(self):
        f = self.p.dir / "mesa.jsonl"
        a = Me.escribir(f, "toni", texto="▶ Empieza la sesión cero", evento="empezar")
        b = Me.escribir(f, "director", texto="Amanece en Ses Païsses.")
        self.assertEqual((a["id"], b["id"], a["de"], a["evento"]), (1, 2, "toni", "empezar"))
        self.assertRegex(a["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertFalse(Me.esperando(Me.leer(f)))
        Me.escribir(f, "toni", texto="voy al pozo")
        self.assertTrue(Me.esperando(Me.leer(f)))
        with self.assertRaises(SystemExit):
            Me.escribir(f, "toni", texto="x" * 5000)

    def test_escuchar_todas_las_mesas_con_un_solo_vigilante(self):
        f = self.p.dir / "mesa.jsonl"
        Me.escribir(f, "toni", texto="pendiente de antes")                        # lo pendiente sale al arrancar
        oido = []
        import threading
        hilo = threading.Thread(target=Me.escuchar, args=(self.raiz, oido.append, 6, 0.2), daemon=True)
        hilo.start()
        import time
        time.sleep(0.3)
        Me.escribir(f, "toni", texto="▶ Empieza la sesión cero", evento="empezar")
        Me.escribir(self.vieja, "toni", texto="y ahora, a Ciutat\npor la costa")
        Me.escribir(f, "director", texto="(no sale: es del director)")
        otra = P.nueva(self.raiz / "partidas" / "islas_1", self.raiz / "mundos" / "baleares_123")    # una partida nueva entra sola
        Me.escribir(otra.dir / "mesa.jsonl", "toni", texto="✨ Vamos a crear el mundo «Islas»", evento="crear_mundo", nombre="Islas")
        hilo.join(5)
        self.assertEqual(oido[0], "MESA baleares_1 #1 Toni: pendiente de antes")                # lo pendiente, primero
        self.assertEqual(sorted(oido[1:]), sorted(["EVENTO baleares_1 empezar", "MESA ensueno #3 Toni: y ahora, a Ciutat / por la costa",
                                                   "EVENTO islas_1 crear_mundo «Islas»"]))     # cada mesa en su vuelta, sin repetir

    def test_decir_por_la_linea_de_ordenes(self):
        # el motor busca la raíz junto a engine/: se prueba sobre una copia del motor en la raíz temporal
        shutil.copytree(ENGINE, self.raiz / "engine", ignore=shutil.ignore_patterns("__pycache__", "tests"))
        motor = lambda *a: subprocess.run([sys.executable, str(self.raiz / "engine" / "motor.py"), *a], capture_output=True, text=True)
        r = motor("decir", "baleares_1", "Amanece en **Ses Païsses**.")
        self.assertIn("baleares_1: mesa #1", r.stdout, r.stderr)
        self.assertEqual(Me.leer(self.p.dir / "mesa.jsonl")[-1]["de"], "director")
        self.assertIn("ensueno: mesa #3", motor("decir", "ensueno", "Seguimos.").stdout)
        self.assertIn("no hay partida", motor("decir", "nadie", "x").stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
