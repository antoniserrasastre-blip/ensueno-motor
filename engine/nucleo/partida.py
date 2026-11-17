"""Una partida y su mundo. La partida es una carpeta (partida.json, estado.json, cronica/, mesa.jsonl,
dados.jsonl); el mundo, otra (mundo.json, constitucion.md, tipos/, datos/, sistemas.json, sistemas/).
partida.json dice de qué mundo es: {"nombre", "mundo": ruta relativa o absoluta, "creada"}."""
import json
import os
from pathlib import Path


def leer_json(f, defecto=None):
    f = Path(f)
    if not f.exists():
        if defecto is not None:
            return defecto
        raise SystemExit(f"No existe el archivo: {f}")
    return json.loads(f.read_text(encoding="utf-8"))


def escribir_json(f, x):
    Path(f).write_text(json.dumps(x, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


class Mundo:
    """Lo que no cambia al jugar: constitución, tipos, datos y qué sistemas se enchufan."""
    def __init__(self, carpeta):
        self.dir = Path(carpeta).resolve()
        if not (self.dir / "mundo.json").exists():
            raise SystemExit(f"{self.dir} no es un mundo (falta mundo.json)")
        self.info = leer_json(self.dir / "mundo.json")
        self.id = self.info.get("id", self.dir.name)
        self.tipos = {f.stem: leer_json(f) for f in sorted((self.dir / "tipos").glob("*.json"))}
        self.datos = {f.stem: leer_json(f) for f in sorted((self.dir / "datos").glob("*.json"))}
        self.sistemas_on = leer_json(self.dir / "sistemas.json", {})
        c = self.dir / "constitucion.md"
        self.constitucion = c.read_text(encoding="utf-8") if c.exists() else ""

    def tipo_de_coleccion(self, col):
        return next((t for t, d in self.tipos.items() if d["coleccion"] == col), None)


class Partida:
    def __init__(self, carpeta):
        self.dir = Path(carpeta).resolve()
        if not (self.dir / "partida.json").exists():
            raise SystemExit(f"{self.dir} no es una partida (falta partida.json)")
        self.info = leer_json(self.dir / "partida.json")
        m = Path(self.info["mundo"])
        self.mundo = Mundo(m if m.is_absolute() else (self.dir / m))
        self.cronica = self.dir / "cronica"
        self.cronica.mkdir(exist_ok=True)

    @property
    def f_estado(self):
        return self.dir / "estado.json"

    def estado(self):
        return leer_json(self.f_estado)

    def guardar(self, e):
        escribir_json(self.f_estado, e)

    def anotar(self, archivo, x):
        """Una línea más en un registro de la partida (mesa.jsonl, dados.jsonl)."""
        with open(self.dir / archivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")


def nueva(carpeta, mundo, nombre=None, inicio=None):
    """Crea una partida vacía de un mundo: colecciones de sus tipos, el reloj del mundo y el turno 0. `inicio`
    (o el inicio.json del mundo) es un bloque de colecciones para empezar: {"personas": {...}, …}."""
    carpeta, mundo_dir = Path(carpeta), Path(mundo).resolve()
    if (carpeta / "partida.json").exists():
        raise SystemExit(f"Ya hay una partida en {carpeta}")
    w = Mundo(mundo_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "cronica").mkdir(exist_ok=True)
    # el mundo, relativo a la partida: así la carpeta se puede mover con el repo
    escribir_json(carpeta / "partida.json", {"nombre": nombre or w.info.get("nombre", w.id),
                                             "mundo": os.path.relpath(mundo_dir, carpeta.resolve()), "version": 1})
    e = {"version": 1, "mundo": w.id, "turno": 0, "reloj": dict(w.info.get("reloj", {"dia": 1, "hora": 8})),
         "colecciones": {d["coleccion"]: {} for d in w.tipos.values()}, "timeline": [], "avisos": []}
    ini = inicio if inicio is not None else leer_json(w.dir / "inicio.json", {})
    for col, xs in ini.items():
        e["colecciones"].setdefault(col, {}).update(xs)
    escribir_json(carpeta / "estado.json", e)
    return Partida(carpeta)
