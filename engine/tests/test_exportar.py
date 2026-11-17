"""Tests de la copia para regalar: sin nada privado y jugable desde cero, sin nada de este repo (se exporta a una
carpeta temporal, se arranca allí y se juega una sesión cero completa por el panel y la línea de órdenes)."""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
RAIZ = ENGINE.parent
sys.path.insert(0, str(ENGINE))
from nucleo import exportar as X  # noqa: E402


def libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    n = s.getsockname()[1]
    s.close()
    return n


class Copia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="engine_regalo_"))
        cls.d = X.exportar(RAIZ, cls.tmp / "ensueno")
        cls.env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cls.tmp), "LANG": "C.UTF-8"}   # nada de aquí

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def motor(self, *a, ok=True, timeout=60):
        r = subprocess.run([sys.executable, str(self.d / "engine" / "motor.py"), *a], capture_output=True, text=True,
                           cwd=self.d, env=self.env, timeout=timeout)
        if ok and r.returncode:
            self.fail(f"motor {' '.join(a)}:\n{r.stdout}\n{r.stderr}")
        return r

    def test_sin_nada_privado(self):
        self.assertEqual(X.revisar(self.d), [])
        hay = {p.name for p in self.d.iterdir()}
        self.assertEqual(hay, {".git", ".gitignore", "CLAUDE.md", "LEEME.md", "engine", "hq.json", "mundos", "partidas"})
        self.assertEqual([p.name for p in (self.d / "mundos").iterdir()], ["baleares_123"])
        self.assertEqual([p.name for p in (self.d / "partidas").iterdir()], [".gitkeep"])
        self.assertEqual(json.loads((self.d / "hq.json").read_text())["externas"], [])
        self.assertNotIn("tunel", json.loads((self.d / "hq.json").read_text()))
        self.assertFalse(list(self.d.rglob("__pycache__")))
        self.assertIn("EnSueño: motor de rol", subprocess.run(["git", "-C", str(self.d), "log", "--oneline"], capture_output=True, text=True).stdout)
        self.assertIn("no tiene túnel", self.motor("servir", "--hq", "--puerto", str(libre()), ok=False).stderr)
        with self.assertRaises(SystemExit):
            X.exportar(RAIZ, self.d)                                                 # no pisa una carpeta llena

    def test_una_sesion_cero_entera_desde_la_copia(self):
        puerto = libre()
        srv = subprocess.Popen([sys.executable, str(self.d / "engine" / "motor.py"), "servir", "--puerto", str(puerto)],
                               cwd=self.d, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(srv.kill)
        base = f"http://127.0.0.1:{puerto}/"

        def pedir(ruta, datos=None):
            req = urllib.request.Request(base + ruta, data=json.dumps(datos).encode() if datos is not None else None,
                                         headers={"Content-Type": "application/json"}, method="POST" if datos is not None else "GET")
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode()
        for _ in range(50):
            try:
                pedir("")
                break
            except OSError:
                time.sleep(0.1)
        self.assertIn("Partidas", pedir(""))
        self.assertEqual([p["id"] for p in json.loads(pedir("api/partidas"))], [])                 # nada jugado
        pid = json.loads(pedir("api/nueva", {"mundo": "baleares_123", "nombre": "La de Félix"}))["id"]
        pedir(f"api/p/{pid}/mesa", {"evento": "empezar"})                                         # el botón «Empezar»
        oye = subprocess.Popen([sys.executable, str(self.d / "engine" / "motor.py"), "escuchar", "--todas"], cwd=self.d,
                               env=self.env, stdout=subprocess.PIPE, text=True)
        self.addCleanup(oye.kill)
        self.assertEqual(oye.stdout.readline().strip(), f"EVENTO {pid} empezar")                  # el director lo oye
        self.motor("decir", pid, "Amanece en **Ses Païsses**. ¿Quién eres?")
        pedir(f"api/p/{pid}/mesa", {"texto": "Una hondera que nunca salió de la isla"})
        self.assertEqual(oye.stdout.readline().strip(), f"MESA {pid} #3 Jugador: Una hondera que nunca salió de la isla")
        f = Path(self.motor("-p", f"partidas/{pid}", "plantilla").stdout.strip())
        cambios = {"titulo": "La hondera", "evento": "Sesión cero: una hondera de Ses Païsses", "tiempo": {"horas": 2},
                   "crear": [{"tipo": "persona", "nombre": "Tala", "donde": "ses_paisses", "tuyo": True, "rol": "hondera"}]}
        f.write_text("## Narración\n\nTala sube al talayot con la honda.\n\n```cambios\n" + json.dumps(cambios, ensure_ascii=False) + "\n```\n")
        self.assertIn("Turno 1 cerrado", self.motor("-p", f"partidas/{pid}", "cerrar", str(f)).stdout)
        todo = json.loads(pedir(f"api/p/{pid}"))
        self.assertEqual(todo["estado"]["turno"], 1)
        self.assertIn("tala", todo["estado"]["colecciones"]["personas"])
        self.assertEqual([m["de"] for m in todo["mesa"]], ["toni", "director", "toni", "motor"])
        mundo = json.loads(pedir("api/mundo", {"nombre": "Las islas de Félix"}))                    # y un mundo inventado
        self.assertEqual(oye.stdout.readline().strip(), f"EVENTO {mundo['id']} crear_mundo «Las islas de Félix»")


if __name__ == "__main__":
    unittest.main(verbosity=1)
