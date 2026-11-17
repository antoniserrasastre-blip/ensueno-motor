"""Un proxy como el de un servidor de fuera: lo que llega a /partida/… lo reenvía al servidor quitando el prefijo
(GET y POST, cabeceras y cuerpo tal cual). Para probar el HQ bajo prefijo sin servidor de fuera:

    python3 engine/tests/proxy_prefijo.py 8810 8800      →  http://localhost:8810/partida/"""
import http.server
import sys
import urllib.error
import urllib.request

PREFIJO = "/partida"


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def handler(destino):
    class Proxy(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reenviar(self):
            if not (self.path == PREFIJO or self.path.startswith(PREFIJO + "/")):
                self.send_error(404)
                return
            resto = self.path[len(PREFIJO):] or "/"
            cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
            cab = {k: self.headers[k] for k in ("Content-Type", "If-None-Match", "Cookie") if self.headers.get(k)}
            req = urllib.request.Request(destino + resto, data=cuerpo, headers=cab, method=self.command)
            try:
                with urllib.request.build_opener(SinRedireccion).open(req, timeout=20) as r:    # la redirección, al navegador
                    codigo, h, datos = r.status, r.headers, r.read()
            except urllib.error.HTTPError as ex:
                codigo, h, datos = ex.code, ex.headers, ex.read()
            self.send_response(codigo)
            for k in ("Content-Type", "ETag", "Cache-Control", "Location"):
                if h.get(k):
                    self.send_header(k, h[k])
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        do_GET = do_POST = reenviar

    return Proxy


if __name__ == "__main__":
    puerto, servidor = int(sys.argv[1]), int(sys.argv[2])
    print(f"proxy: http://localhost:{puerto}{PREFIJO}/ → http://127.0.0.1:{servidor}/", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", puerto), handler(f"http://127.0.0.1:{servidor}")).serve_forever()
