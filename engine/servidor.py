"""El servidor del panel: el HQ en «/», las partidas del motor nuevo en «/p/<id>/» y las partidas de otros
motores (EnSueño) tal cual, por un pasillo: «/ensueno/…» se reenvía a su propio servidor, que no cambia.

  /                      HQ: las partidas en marcha (engine/hq/index.html)
  /p/<id>/               el panel de una partida del motor nuevo (engine/panel/index.html)
  /api/partidas          todas, para el HQ
  /api/mundos            los mundos con los que se puede empezar
  /api/p/<id>            estado, mundo y mesa de una partida
  POST /api/nueva        {"mundo": id, "nombre"?}: crea una partida y devuelve su id
  /<externa>/…           reenvío a su servidor (hq.json, «externas»)

Las externas se apuntan en hq.json (raíz del repo):
  {"externas": [{"id": "ensueno", "nombre": "EnSueño", "subtitulo": "…", "ruta": "/ensueno/", "panel": "panel/",
                 "servidor": "http://127.0.0.1:8765", "estado": "partida/estado.json",
                 "arrancar": ["python3", "partida/motor/motor.py", "servir", "--puerto", "8765"]}]}"""
import http.server
import json
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from nucleo import amenazas, constitucion, fichas as F, forja as Fo, mesa as Me, mundos as Mu, ordenes as O, partida as P, reloj as R, trueque as Tq  # noqa: F401
from nucleo.tipos import slug

ENGINE = Path(__file__).resolve().parent
RAIZ = ENGINE.parent
PARTIDAS = RAIZ / "partidas"
MUNDOS = RAIZ / "mundos"
HQ = RAIZ / "hq.json"
MAX_CUERPO = 64 * 1024
CERROJO = threading.Lock()       # dos órdenes a la vez no se pisan el estado
# El botón de volver al HQ en las páginas de una partida externa: lo pone el pasillo, sin tocar sus archivos. Pequeño,
# abajo a la izquierda, sobre todo lo demás; en el móvil, en el hueco del centro de la cabecera (sin tapar botones).
VOLVER = ("<a href='{inicio}' id='volver-hq' title='Volver a las partidas' aria-label='Volver a las partidas' style='position:fixed;"
          "left:10px;bottom:10px;z-index:9999;width:34px;height:34px;border-radius:10px;display:grid;place-items:center;"
          "background:rgba(16,20,42,.85);border:1px solid rgba(233,216,166,.25);color:#ede0bb;text-decoration:none;"
          "font:700 18px system-ui'>⌂</a><style>@media (max-width:820px){#volver-hq{bottom:auto!important;top:56px;left:50%!important;transform:translateX(-50%);width:28px!important;height:28px!important;font-size:15px!important}}</style>").encode()


def externas():
    return P.leer_json(HQ, {}).get("externas", [])


def resumen_externa(x):
    """Lo que el HQ enseña de una partida de otro motor: su estado, leído sin tocarlo."""
    out = {k: x.get(k) for k in ("id", "nombre", "subtitulo")}
    out["url"] = x["ruta"].strip("/") + "/" + x.get("panel", "")          # relativa: el HQ puede ir bajo un prefijo
    try:
        e = json.loads((RAIZ / x["estado"]).read_text(encoding="utf-8"))
        tl = (e.get("timeline") or [{}])[-1]
        d = (e.get("relojes") or {}).get("dentro") or {}
        out.update(turno=e.get("turno"), ultimo=tl.get("titulo") or tl.get("evento", "")[:60],
                   cuando=f"día {d['dia']}" if "dia" in d else "",
                   cambiado=(RAIZ / x["estado"]).stat().st_mtime)
    except (OSError, ValueError, KeyError):
        out.update(turno=None, ultimo="", cuando="")
    out["motor"] = "externo"
    return out


def resumen_partida(d):
    p = P.Partida(d)
    e = p.estado()
    tl = (e["timeline"] or [{}])[-1]
    return {"id": d.name, "nombre": p.info.get("nombre", d.name), "subtitulo": p.mundo.info.get("subtitulo", ""),
            "mundo": p.mundo.info.get("nombre", p.mundo.id), "turno": e["turno"], "ultimo": tl.get("titulo", ""),
            "cuando": R.texto(e["reloj"]), "url": f"p/{d.name}/", "cambiado": p.f_estado.stat().st_mtime,
            "motor": "nuevo", "forja": len([x for x in Fo.fichas(p) if not x.get("encendido")]),
            "forja_on": len([x for x in Fo.fichas(p) if x.get("encendido")]), "icono": p.mundo.info.get("icono", ""),
            "construccion": Mu.validar(p.mundo.dir) if Mu.en_construccion(p) else None,
            "esperando": Me.esperando(Me.leer(d / "mesa.jsonl")),
            "empezada": any(m.get("evento") == "empezar" for m in Me.leer(d / "mesa.jsonl"))}


def partidas():
    nuevas = [resumen_partida(d) for d in sorted(PARTIDAS.glob("*")) if (d / "partida.json").exists()] if PARTIDAS.exists() else []
    return [resumen_externa(x) for x in externas()] + nuevas


def mundos():
    return [{"id": d.name, "nombre": P.leer_json(d / "mundo.json").get("nombre", d.name),
             "subtitulo": P.leer_json(d / "mundo.json").get("subtitulo", "")}
            for d in sorted(MUNDOS.glob("*")) if (d / "mundo.json").exists()
            and P.leer_json(d / "mundo.json").get("estado") != "construccion"] if MUNDOS.exists() else []


def todo(pid):
    """Lo que necesita el panel de una partida, en una sola respuesta."""
    d = PARTIDAS / pid
    if not re.fullmatch(r"[a-z0-9_]+", pid) or not (d / "partida.json").exists():
        return None
    p = P.Partida(d)
    e = p.estado()
    f = d / "mesa.jsonl"
    mesa = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()[-40:] if x.strip()] if f.exists() else []
    w = p.mundo
    return {"id": pid, "partida": p.info, "construccion": Mu.validar(p.mundo.dir) if Mu.en_construccion(p) else None, "estado": e, "reloj": R.texto(e["reloj"]), "mesa": mesa, "ordenes": O.lista(p)[-30:],
            "trabajos": (w.datos.get("trabajos") or {}).get("trabajos", []), "habilidades": list(F.habilidades(w).values()),
            "trueque": w.datos.get("trueque") or {}, "forja": Fo.fichas(p),
            "mundo": {"id": w.id, **{k: w.info.get(k) for k in ("nombre", "subtitulo", "fecha_inicio", "jugador")},
                      "constitucion": w.constitucion}}


def nueva(datos):
    mid = str(datos.get("mundo", ""))
    if not re.fullmatch(r"[a-z0-9_]+", mid) or not (MUNDOS / mid / "mundo.json").exists():
        raise ValueError("ese mundo no existe")
    base = slug(datos.get("nombre") or mid)[:40] or mid
    pid, n = base, 2
    while (PARTIDAS / pid).exists():
        pid, n = f"{base}_{n}", n + 1
    P.nueva(PARTIDAS / pid, MUNDOS / mid, datos.get("nombre"))
    return pid


class Handler(http.server.BaseHTTPRequestHandler):
    arrancar = False

    def log_message(self, *args):
        pass

    def enviar(self, codigo, cuerpo, tipo="application/json; charset=utf-8", extra=None):
        datos = cuerpo if isinstance(cuerpo, bytes) else (json.dumps(cuerpo, ensure_ascii=False) if not isinstance(cuerpo, str) else cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def externa(self):
        return next((x for x in externas() if self.path == x["ruta"].rstrip("/") or self.path.startswith(x["ruta"])), None)

    def pasillo(self, x):
        """Reenvía la petición al servidor de la partida externa, sin tocar nada."""
        resto = self.path[len(x["ruta"].rstrip("/")):] or "/"
        if self.path == x["ruta"].rstrip("/"):
            return self.enviar(301, b"", extra={"Location": x["ruta"].strip("/") + "/"})          # relativa
        cuerpo = self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 4 * MAX_CUERPO)) if self.command == "POST" else None
        cab = {k: self.headers[k] for k in ("Content-Type", "If-None-Match", "Cookie") if self.headers.get(k)}
        for intento in range(2):
            try:
                req = urllib.request.Request(x["servidor"].rstrip("/") + resto, data=cuerpo, headers=cab, method=self.command)
                with urllib.request.urlopen(req, timeout=20) as r:
                    return self.copiar(r.status, r.headers, r.read())
            except urllib.error.HTTPError as ex:
                return self.copiar(ex.code, ex.headers, ex.read())
            except (urllib.error.URLError, OSError):
                if intento == 0 and self.arrancar and x.get("arrancar"):
                    subprocess.Popen(x["arrancar"], cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1.5)
                    continue
                orden = " ".join(x.get("arrancar") or ["(su servidor)"])
                return self.enviar(502, f"<!doctype html><meta charset=utf-8><body style='font:16px system-ui;padding:2em;"
                                        f"background:#10142a;color:#ede0bb'><h2>{x['nombre']} no está en marcha</h2>"
                                        f"<p>Arráncalo con <code>{orden}</code> y vuelve a cargar.</p><p><a style='color:#f2b134' "
                                        f"href='{self.inicio()}'>← Volver al inicio</a></p>", "text/html; charset=utf-8")

    def inicio(self):
        """El HQ, relativo a esta página (sirve en «/» y bajo un prefijo, como /partida/ detrás de un proxy)."""
        return "../" * (self.path.split("?")[0].count("/") - 1) or "./"

    def copiar(self, codigo, cab, cuerpo):
        if codigo == 200 and "text/html" in (cab.get("Content-Type") or "") and b"</body>" in cuerpo:
            cuerpo = cuerpo.replace(b"</body>", VOLVER.replace(b"{inicio}", self.inicio().encode()) + b"</body>", 1)
        self.send_response(codigo)
        for k in ("Content-Type", "ETag", "Cache-Control", "Location", "Set-Cookie"):
            if cab.get(k):
                self.send_header(k, cab[k])
        if codigo != 304:
            self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        if codigo != 304:
            self.wfile.write(cuerpo)

    def archivo(self, f):
        tipos = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
                 ".json": "application/json", ".png": "image/png"}
        if not f.is_file():
            return self.enviar(404, {"error": "no existe"})
        self.enviar(200, f.read_bytes(), tipos.get(f.suffix, "application/octet-stream"))

    def do_GET(self):
        x = self.externa()
        if x:
            return self.pasillo(x)
        ruta = self.path.split("?")[0]
        if ruta in ("/", "/index.html"):
            return self.archivo(ENGINE / "hq" / "index.html")
        if ruta == "/api/partidas":
            return self.enviar(200, partidas())
        if ruta == "/api/mundos":
            return self.enviar(200, mundos())
        mp = re.fullmatch(r"/api/p/([a-z0-9_]+)/mapa(?:/([a-z0-9_]+\.(?:txt|json)))?", ruta)
        if mp and (PARTIDAS / mp.group(1) / "partida.json").exists():
            carpeta = P.Partida(PARTIDAS / mp.group(1)).mundo.dir / "mapas"     # los mapas son del mundo
            f = carpeta / (mp.group(2) or "mapas.json")
            if not mp.group(2) and not f.is_file():
                return self.enviar(200, {"capas": []})                 # el mapa es opcional: sin mapa no es un error
            return self.archivo(f) if f.is_file() else self.enviar(404, {"error": "este mundo no tiene ese mapa"})
        m = re.fullmatch(r"/api/p/([a-z0-9_]+)", ruta)
        if m:
            t = todo(m.group(1))
            return self.enviar(200, t) if t else self.enviar(404, {"error": "esa partida no existe"})
        if re.fullmatch(r"/p/[a-z0-9_]+/?", ruta):
            if not ruta.endswith("/"):
                return self.enviar(301, b"", extra={"Location": ruta.rsplit("/", 1)[1] + "/"})   # relativa: vale con prefijo
            return self.archivo(ENGINE / "panel" / "index.html")
        self.enviar(404, {"error": "no existe"})

    def do_POST(self):
        x = self.externa()
        if x:
            return self.pasillo(x)
        b = re.fullmatch(r"/api/p/([a-z0-9_]+)/balanza", self.path)
        if b and (PARTIDAS / b.group(1) / "partida.json").exists():
            try:
                d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), MAX_CUERPO)))
                return self.enviar(200, Tq.balanza(P.Partida(PARTIDAS / b.group(1)).mundo, d["mercado"], d.get("da") or {}, d.get("pide") or {}))
            except (ValueError, KeyError) as ex:
                return self.enviar(400, {"error": f"balanza: {ex}"})
        fo = re.fullmatch(r"/api/p/([a-z0-9_]+)/forja(?:/([a-z0-9_]+))?", self.path)
        if fo:
            if not (PARTIDAS / fo.group(1) / "partida.json").exists():
                return self.enviar(404, {"error": "esa partida no existe"})
            try:
                d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), MAX_CUERPO)))
                p = P.Partida(PARTIDAS / fo.group(1))
                with CERROJO:
                    x = Fo.encender(p, fo.group(2), bool(d.get("encendido"))) if fo.group(2) else \
                        Fo.pedir(p, str(d.get("nombre", "")), str(d.get("que", "")), "jugador")
                return self.enviar(200, x)
            except (ValueError, SystemExit) as ex:
                return self.enviar(400, {"error": str(ex)})
        if self.path == "/api/mundo":
            try:
                d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), MAX_CUERPO)))
                nombre = str(d.get("nombre", "")).strip()[:60]
                if not nombre:
                    raise ValueError("el mundo necesita un nombre")
                base, mid, n = slug(nombre)[:36] or "mundo", None, 1
                mid = base
                while (MUNDOS / mid).exists():
                    n += 1
                    mid = f"{base}_{n}"
                with CERROJO:
                    _, p = Mu.crear(RAIZ, mid, nombre, str(d.get("icono", ""))[:4])
                # el botón habla solo: el director lo oye con «escuchar --todas» y empieza a preguntar
                Me.escribir(p.dir / "mesa.jsonl", "toni", texto=f"✨ Vamos a crear el mundo «{nombre}»: te dicto el lore",
                            evento="crear_mundo", nombre=nombre)
                return self.enviar(200, {"mundo": mid, "id": p.dir.name})
            except (ValueError, SystemExit) as ex:
                return self.enviar(400, {"error": str(ex)})
        me = re.fullmatch(r"/api/p/([a-z0-9_]+)/mesa", self.path)
        if me:
            if not (PARTIDAS / me.group(1) / "partida.json").exists():
                return self.enviar(404, {"error": "esa partida no existe"})
            try:
                d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), MAX_CUERPO)))
                p, f = P.Partida(PARTIDAS / me.group(1)), PARTIDAS / me.group(1) / "mesa.jsonl"
                if d.get("evento") == "empezar":
                    if Mu.en_construccion(p):
                        raise ValueError("el mundo aún está en construcción")
                    if p.estado()["turno"] or any(m.get("evento") == "empezar" for m in Me.leer(f)):
                        raise ValueError("esta partida ya ha empezado")
                    return self.enviar(200, Me.escribir(f, "toni", texto="▶ Empieza la sesión cero", evento="empezar"))
                if d.get("evento") == "crear_mundo":
                    if not Mu.en_construccion(p):
                        raise ValueError("este mundo ya está hecho")
                    nombre = p.mundo.info.get("nombre", p.mundo.id)
                    return self.enviar(200, Me.escribir(f, "toni", texto=f"✨ Vamos a crear el mundo «{nombre}»: te dicto el lore",
                                                        evento="crear_mundo", nombre=nombre))
                texto = str(d.get("texto", "")).strip()
                if not texto:
                    raise ValueError("no hay nada que decir")
                return self.enviar(200, Me.escribir(f, "toni", texto=texto))
            except (ValueError, SystemExit) as ex:
                return self.enviar(400, {"error": str(ex)})
        m = re.fullmatch(r"/api/p/([a-z0-9_]+)/orden", self.path)
        if not (self.path == "/api/nueva" or m) or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.enviar(400, {"error": "petición no válida"})
        try:
            datos = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), MAX_CUERPO)))
            if m:
                if not (PARTIDAS / m.group(1) / "partida.json").exists():
                    return self.enviar(404, {"error": "esa partida no existe"})
                with CERROJO:
                    o = O.nueva(P.Partida(PARTIDAS / m.group(1)), str(datos.get("tipo", "")), datos.get("datos") or {})
                return self.enviar(200, o)
            self.enviar(200, {"id": nueva(datos)})
        except (ValueError, SystemExit) as ex:
            self.enviar(400, {"error": str(ex)})


def tunel_config():
    """El túnel al HQ remoto, si este repo lo tiene (hq.json, «tunel»: {servidor, puerto, url}). Es de cada casa: una
    copia exportada no lo lleva y «servir --hq» dice que no hay túnel."""
    return P.leer_json(HQ, {}).get("tunel")


def tunel_hq(puerto, cfg):
    """Túnel SSH inverso: el puerto «puerto» de cfg.servidor llega a este servidor (el proxy de allí reenvía el prefijo
    quitándolo). Solo uno de los paneles puede tener el túnel: el panel viejo, entonces, sin --hq."""
    while True:
        r = subprocess.run(["ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                            "-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=3",
                            "-R", f"127.0.0.1:{cfg['puerto']}:127.0.0.1:{puerto}", cfg["servidor"]],
                           capture_output=True, text=True)
        print(f"túnel caído ({(r.stderr or '').strip()[:120]}); reintento en 15 s", flush=True)
        time.sleep(15)


def servir(puerto=8800, lan=False, arrancar=False, hq=False):
    Handler.arrancar = arrancar
    if hq:
        cfg = tunel_config()
        if not cfg:
            raise SystemExit("--hq: este HQ no tiene túnel (hq.json, «tunel»). Sin él, el panel está en http://localhost:%d/" % puerto)
        threading.Thread(target=tunel_hq, args=(puerto, cfg), daemon=True).start()
        print(f"túnel a {cfg.get('url', cfg['servidor'])} (el {cfg['puerto']} de allí → este {puerto})", flush=True)
    s = http.server.ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", puerto), Handler)
    print(f"HQ en http://localhost:{puerto}/", flush=True)
    s.serve_forever()
