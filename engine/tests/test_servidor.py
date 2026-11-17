"""Tests del servidor del panel: el HQ, la API de partidas y el pasillo a las partidas de otros motores (con un
servidor de mentira en lugar del de EnSueño)."""
import http.server
import json
import shutil
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ENGINE / "tests"))
import servidor  # noqa: E402
from nucleo import partida as P  # noqa: E402


def libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    n = s.getsockname()[1]
    s.close()
    return n


class Viejo(http.server.BaseHTTPRequestHandler):
    """Hace de servidor de EnSueño: un panel, un estado con ETag y una mesa que recibe POST."""
    recibido = []
    html = None

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/estado.json" and self.headers.get("If-None-Match") == '"v1"':
            self.send_response(304)
            self.end_headers()
            return
        cuerpo = (self.html if self.path == "/panel/con_body" else b"<html>panel de siempre</html>") \
            if self.path.startswith("/panel/") else b'{"turno": 7}'
        self.send_response(200)
        self.send_header("Content-Type", "text/html" if self.path.startswith("/panel/") else "application/json")
        self.send_header("ETag", '"v1"')
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_POST(self):
        Viejo.recibido.append((self.path, self.rfile.read(int(self.headers["Content-Length"])), self.headers["Content-Type"]))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


class Servidor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="engine_hq_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copytree(ENGINE.parent / "mundos" / "baleares_123", self.tmp / "mundos" / "baleares_123")
        (self.tmp / "vieja").mkdir()
        (self.tmp / "vieja" / "estado.json").write_text(json.dumps(
            {"turno": 391, "timeline": [{"titulo": "La Santa Creu"}], "relojes": {"dentro": {"dia": 302}}}))
        self.pv = libre()
        viejo = http.server.ThreadingHTTPServer(("127.0.0.1", self.pv), Viejo)
        threading.Thread(target=viejo.serve_forever, daemon=True).start()
        self.addCleanup(viejo.shutdown)
        (self.tmp / "hq.json").write_text(json.dumps({"externas": [
            {"id": "ensueno", "nombre": "EnSueño", "subtitulo": "Juancho", "ruta": "/ensueno/", "panel": "panel/",
             "servidor": f"http://127.0.0.1:{self.pv}", "estado": "vieja/estado.json"},
            {"id": "caida", "nombre": "Caída", "ruta": "/caida/", "servidor": f"http://127.0.0.1:{libre()}",
             "estado": "no/existe.json"}]}))
        for k, v in {"RAIZ": self.tmp, "PARTIDAS": self.tmp / "partidas", "MUNDOS": self.tmp / "mundos",
                     "HQ": self.tmp / "hq.json"}.items():
            setattr(servidor, k, v)
        self.puerto = libre()
        s = http.server.ThreadingHTTPServer(("127.0.0.1", self.puerto), servidor.Handler)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.shutdown)

    def pedir(self, ruta, datos=None, cab=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.puerto}{ruta}", method="POST" if datos is not None else "GET",
                                     data=json.dumps(datos).encode() if datos is not None else None,
                                     headers={"Content-Type": "application/json", **(cab or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode(), r.headers
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read().decode(), ex.headers

    def test_el_hq_y_las_partidas(self):
        c, html, _ = self.pedir("/")
        self.assertEqual(c, 200)
        self.assertIn("Partidas", html)
        c, d, _ = self.pedir("/api/nueva", {"mundo": "baleares_123", "nombre": "Los honderos"})
        self.assertEqual(json.loads(d)["id"], "los_honderos")
        ps = {p["id"]: p for p in json.loads(self.pedir("/api/partidas")[1])}
        self.assertEqual((ps["ensueno"]["turno"], ps["ensueno"]["ultimo"], ps["ensueno"]["url"]), (391, "La Santa Creu", "ensueno/panel/"))
        self.assertEqual((ps["los_honderos"]["turno"], ps["los_honderos"]["url"]), (0, "p/los_honderos/"))
        self.assertIsNone(ps["caida"]["turno"])                    # sin estado legible: sale igual, sin datos
        self.assertEqual(json.loads(self.pedir("/api/mundos")[1])[0]["id"], "baleares_123")
        d = json.loads(self.pedir("/api/p/los_honderos")[1])
        self.assertIn("NO EXISTE", d["mundo"]["constitucion"])
        self.assertIn("ses_paisses", d["estado"]["colecciones"]["lugares"])
        self.assertEqual(self.pedir("/p/los_honderos/")[0], 200)
        self.assertEqual(self.pedir("/api/p/no_existe")[0], 404)
        self.assertEqual(self.pedir("/api/nueva", {"mundo": "../etc"})[0], 400)
        self.assertEqual(json.loads(self.pedir("/api/nueva", {"mundo": "baleares_123", "nombre": "Los honderos"})[1])["id"], "los_honderos_2")

    def test_ordenes_desde_el_panel(self):
        pid = json.loads(self.pedir("/api/nueva", {"mundo": "baleares_123"})[1])["id"]
        p = P.Partida(self.tmp / "partidas" / pid)
        e = p.estado()
        e["colecciones"]["personas"]["tala"] = {"nombre": "Tala", "donde": "ses_paisses", "tuyo": True}
        p.guardar(e)
        c, d, _ = self.pedir(f"/api/p/{pid}/orden", {"tipo": "trabajo", "datos": {"persona": "tala", "trabajo": "honda", "prioridad": 1}})
        self.assertEqual((c, json.loads(d)["estado"]), (200, "aplicada"))
        todo = json.loads(self.pedir(f"/api/p/{pid}")[1])
        self.assertEqual(todo["estado"]["colecciones"]["personas"]["tala"]["trabajos"], {"honda": 1})
        self.assertTrue(any(t["id"] == "honda" for t in todo["trabajos"]))
        c, d, _ = self.pedir(f"/api/p/{pid}/orden", {"tipo": "trabajo", "datos": {"persona": "tala", "trabajo": "volar", "prioridad": 1}})
        self.assertEqual(c, 400)
        self.assertIn("no existe", json.loads(d)["error"])
        self.assertEqual(self.pedir("/api/p/no_hay/orden", {"tipo": "trabajo"})[0], 404)

    def test_mundo_nuevo_desde_el_hq(self):
        c, d, _ = self.pedir("/api/mundo", {"nombre": "Las islas de niebla", "icono": "🌫"})
        r = json.loads(d)
        self.assertEqual((c, r["mundo"], r["id"]), (200, "las_islas_de_niebla", "las_islas_de_niebla_1"))
        ps = {p["id"]: p for p in json.loads(self.pedir("/api/partidas")[1])}
        obra = ps["las_islas_de_niebla_1"]
        self.assertEqual((obra["icono"], obra["construccion"][0]["ok"]), ("🌫", False))
        self.assertNotIn("las_islas_de_niebla", [m["id"] for m in json.loads(self.pedir("/api/mundos")[1])])
        self.assertIsNotNone(json.loads(self.pedir("/api/p/las_islas_de_niebla_1")[1])["construccion"])
        self.assertEqual(json.loads(self.pedir("/api/p/las_islas_de_niebla_1/mapa")[1]), {"capas": []})   # sin mapa, sin error
        self.assertEqual(json.loads(self.pedir("/api/mundo", {"nombre": "Las islas de niebla"})[1])["mundo"], "las_islas_de_niebla_2")
        self.assertEqual(self.pedir("/api/mundo", {"nombre": " "})[0], 400)

    def test_los_botones_hablan_solos(self):
        pid = json.loads(self.pedir("/api/nueva", {"mundo": "baleares_123"})[1])["id"]
        c, d, _ = self.pedir(f"/api/p/{pid}/mesa", {"evento": "empezar"})
        self.assertEqual((c, json.loads(d)["evento"], json.loads(d)["texto"]), (200, "empezar", "▶ Empieza la sesión cero"))
        self.assertEqual(self.pedir(f"/api/p/{pid}/mesa", {"evento": "empezar"})[0], 400)          # una sola vez
        ps = {p["id"]: p for p in json.loads(self.pedir("/api/partidas")[1])}
        self.assertEqual((ps[pid]["esperando"], ps[pid]["empezada"]), (True, True))
        self.assertEqual(self.pedir(f"/api/p/{pid}/mesa", {"texto": "  "})[0], 400)
        self.assertEqual(json.loads(self.pedir(f"/api/p/{pid}/mesa", {"texto": "Miro al mar"})[1])["de"], "toni")
        r = json.loads(self.pedir("/api/mundo", {"nombre": "Las islas de niebla"})[1])               # crear un mundo habla solo
        primero = json.loads(self.pedir(f"/api/p/{r['id']}")[1])["mesa"][0]
        self.assertEqual((primero["evento"], primero["nombre"]), ("crear_mundo", "Las islas de niebla"))
        self.assertEqual(self.pedir(f"/api/p/{r['id']}/mesa", {"evento": "empezar"})[0], 400)        # en construcción, no
        self.assertEqual(self.pedir(f"/api/p/{pid}/mesa", {"evento": "crear_mundo"})[0], 400)        # ya está hecho

    def test_el_mapa_del_mundo(self):
        pid = json.loads(self.pedir("/api/nueva", {"mundo": "baleares_123"})[1])["id"]
        m = json.loads(self.pedir(f"/api/p/{pid}/mapa")[1])
        self.assertEqual([c["id"] for c in m["capas"]], ["baleares", "mallorca", "pitiusas"])
        c, txt, _ = self.pedir(f"/api/p/{pid}/mapa/mallorca.txt")
        self.assertEqual((c, len(txt.splitlines())), (200, m["capas"][1]["h"]))
        self.assertEqual(self.pedir(f"/api/p/{pid}/mapa/../../hq.json")[0], 404)
        self.assertEqual(self.pedir(f"/api/p/{pid}/mapa/no_hay.txt")[0], 404)

    def test_la_forja_desde_el_panel(self):
        pid = json.loads(self.pedir("/api/nueva", {"mundo": "baleares_123"})[1])["id"]
        c, d, _ = self.pedir(f"/api/p/{pid}/forja", {"nombre": "Cría de caballos", "que": "que haya potros"})
        self.assertEqual((c, json.loads(d)["estado"]), (200, "pedido"))
        todo = json.loads(self.pedir(f"/api/p/{pid}")[1])
        self.assertEqual(todo["forja"][0]["pedido_por"], "jugador")
        c, d, _ = self.pedir(f"/api/p/{pid}/forja/cria_de_caballos", {"encendido": True})
        self.assertEqual(c, 400)
        self.assertIn("no está lista", json.loads(d)["error"])
        ps = {p["id"]: p for p in json.loads(self.pedir("/api/partidas")[1])}
        self.assertEqual(ps[pid]["forja"], 1)
        self.assertEqual(self.pedir(f"/api/p/{pid}/forja", {"nombre": ""})[0], 400)

    def test_el_pasillo_a_ensueno_no_cambia_nada(self):
        c, html, _ = self.pedir("/ensueno/panel/")
        self.assertEqual((c, html), (200, "<html>panel de siempre</html>"))           # sin </body>: tal cual
        c, _, h = self.pedir("/ensueno/estado.json")
        self.assertEqual(h["ETag"], '"v1"')
        self.assertEqual(self.pedir("/ensueno/estado.json", cab={"If-None-Match": '"v1"'})[0], 304)
        self.assertEqual(self.pedir("/ensueno/mesa", {"texto": "hola"})[:2], (200, "ok"))
        self.assertEqual(Viejo.recibido[-1], ("/mesa", b'{"texto": "hola"}', "application/json"))

    def test_el_pasillo_pone_el_boton_de_volver(self):
        Viejo.html = b"<html><body>panel</body></html>"
        try:
            c, html, _ = self.pedir("/ensueno/panel/con_body")
            self.assertIn("id='volver-hq'", html)
            self.assertTrue(html.endswith("</body></html>"))
            self.assertNotIn("volver-hq", self.pedir("/ensueno/estado.json")[1])        # solo en el HTML
        finally:
            Viejo.html = None

    def test_bajo_prefijo_como_en_hq_randomite_space(self):
        """Detrás de un proxy que quita /partida (como el de un servidor de fuera): todo funciona con rutas relativas."""
        import proxy_prefijo
        pp = libre()
        px = http.server.ThreadingHTTPServer(("127.0.0.1", pp), proxy_prefijo.handler(f"http://127.0.0.1:{self.puerto}"))
        threading.Thread(target=px.serve_forever, daemon=True).start()
        self.addCleanup(px.shutdown)
        base = f"http://127.0.0.1:{pp}/partida/"

        def pedir(ruta, datos=None):
            req = urllib.request.Request(base + ruta, method="POST" if datos is not None else "GET",
                                         data=json.dumps(datos).encode() if datos is not None else None,
                                         headers={"Content-Type": "application/json"})
            op = urllib.request.build_opener(proxy_prefijo.SinRedireccion)
            try:
                with op.open(req, timeout=10) as r:
                    return r.status, r.read().decode(), r.headers
            except urllib.error.HTTPError as ex:
                return ex.code, ex.read().decode(), ex.headers
        self.assertIn("Partidas", pedir("")[1])
        pid = json.loads(pedir("api/nueva", {"mundo": "baleares_123"})[1])["id"]
        ps = {p["id"]: p for p in json.loads(pedir("api/partidas")[1])}
        url = urllib.parse.urljoin(base, ps[pid]["url"])                       # el enlace de la tarjeta, resuelto
        self.assertEqual(url, base + f"p/{pid}/")
        self.assertIn("<title>Partida</title>", pedir(f"p/{pid}/")[1])
        c, _, h = pedir(f"p/{pid}")                                           # sin barra: redirige sin perder el prefijo
        self.assertEqual((c, urllib.parse.urljoin(base + f"p/{pid}", h["Location"])), (301, base + f"p/{pid}/"))
        self.assertIn("baleares", pedir(f"api/p/{pid}")[1])
        e = P.Partida(self.tmp / "partidas" / pid)
        x = e.estado()
        x["colecciones"]["personas"]["tala"] = {"nombre": "Tala", "donde": "ses_paisses", "tuyo": True}
        e.guardar(x)
        c, d, _ = pedir(f"api/p/{pid}/orden", {"tipo": "trabajo", "datos": {"persona": "tala", "trabajo": "honda", "prioridad": 1}})
        self.assertEqual((c, json.loads(d)["estado"]), (200, "aplicada"))
        self.assertEqual(urllib.parse.urljoin(base, ps["ensueno"]["url"]), base + "ensueno/panel/")
        Viejo.html = b"<html><body>panel</body></html>"
        try:
            html = pedir("ensueno/panel/con_body")[1]
            vuelta = html.split("href='")[1].split("'")[0]
            self.assertEqual(urllib.parse.urljoin(base + "ensueno/panel/con_body", vuelta), base)   # ⌂ vuelve al HQ
        finally:
            Viejo.html = None
        self.assertEqual(pedir("ensueno/mesa", {"texto": "hola"})[:2], (200, "ok"))

    def test_si_la_externa_no_esta_en_marcha_lo_dice(self):
        c, html, _ = self.pedir("/caida/panel/")
        self.assertEqual(c, 502)
        self.assertIn("no está en marcha", html)


if __name__ == "__main__":
    unittest.main(verbosity=1)
