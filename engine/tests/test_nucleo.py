"""Tests del núcleo, sobre el mundo de prueba (nunca sobre una partida real)."""
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
MUNDO = ENGINE / "tests" / "mundo_prueba"
sys.path.insert(0, str(ENGINE))
from nucleo import cierre as Ci, dados as D, partida as P, tipos as T  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="engine_test_"))
        self.p = P.nueva(self.tmp / "partida", MUNDO, "Prueba")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def motor(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(ENGINE / "motor.py"), "-p", str(self.p.dir), *args],
                           capture_output=True, text=True)
        if ok and r.returncode:
            self.fail(f"motor {' '.join(args)}:\n{r.stdout}\n{r.stderr}")
        return r

    def turno(self, cambios, narracion="", simular=False):
        f = Ci.plantilla(self.p)
        bloque = {"titulo": "prueba", "evento": "prueba", **cambios}
        f.write_text(f"# Turno\n\n## Narración\n\n{narracion}\n\n```cambios\n{json.dumps(bloque, ensure_ascii=False)}\n```\n",
                     encoding="utf-8")
        return Ci.cerrar(self.p, f, simular)


class Partida(Base):
    def test_nueva_trae_el_inicio_del_mundo(self):
        e = self.p.estado()
        self.assertEqual(e["turno"], 0)
        self.assertEqual(e["reloj"], {"dia": 1, "hora": 8})
        self.assertIn("abi", e["colecciones"]["personas"])
        self.assertEqual(T.validar(e, self.p.mundo), [])

    def test_no_pisa_una_partida(self):
        with self.assertRaises(SystemExit):
            P.nueva(self.p.dir, MUNDO)


class Cierre(Base):
    def test_tres_turnos(self):
        r = self.turno({"crear": [{"tipo": "persona", "nombre": "Bec Rotger", "donde": "poblado"}], "tiempo": {"horas": 4}})
        self.assertEqual(r["creados"], ["persona:bec_rotger"])
        self.turno({"cambiar": {"persona:abi": {"animo": 2}}, "tiempo": {"dias": 2}})
        r = self.turno({"quitar": ["persona:bec_rotger"], "tiempo": {"horas": 1}})
        e = self.p.estado()
        self.assertEqual(e["turno"], 3)
        self.assertEqual(e["reloj"], {"dia": 3, "hora": 13})
        self.assertEqual(e["colecciones"]["personas"]["abi"]["animo"], 2)
        self.assertNotIn("bec_rotger", e["colecciones"]["personas"])
        self.assertEqual(e["colecciones"]["objetos"]["trigo"]["cantidad"], 10 + 2 * 2)   # dos medianoches
        self.assertEqual([t["turno"] for t in e["timeline"]], [1, 2, 3])
        self.assertEqual(len((self.p.dir / "mesa.jsonl").read_text().splitlines()), 3)
        self.assertIn("bec_rotger", (self.p.dir / "archivo.jsonl").read_text())

    def test_un_salto_largo_va_dia_a_dia(self):
        r = self.turno({"tiempo": {"dias": 7}})
        self.assertEqual(self.p.estado()["colecciones"]["objetos"]["trigo"]["cantidad"], 10 + 7 * 2)
        self.assertIn("🌾 7 días de cosecha", r["avisos"])

    def test_simular_no_guarda(self):
        self.turno({"tiempo": {"dias": 1}}, simular=True)
        self.assertEqual(self.p.estado()["turno"], 0)
        self.assertFalse((self.p.dir / "mesa.jsonl").exists())

    def test_lo_que_no_cuadra_no_cierra_ni_guarda(self):
        casos = [({"crear": [{"tipo": "persona", "nombre": "Sin sitio", "donde": "atlantida"}]}, "no existe"),
                 ({"crear": [{"tipo": "dragon", "nombre": "X"}]}, "no existe"),
                 ({"cambiar": {"persona:nadie": {"animo": 1}}}, "no existe"),
                 ({"inventario": {"trigo": 1}}, "no conoce"),
                 ({"tiempo": {"semanas": 1}}, "tiempo"),
                 ({"tiradas": [99]}, "dados.jsonl"),
                 ({"crear": [{"tipo": "persona", "nombre": "Abi", "id": "abi", "donde": "poblado"}]}, "ya existe")]
        for c, msg in casos:
            with self.assertRaises(SystemExit) as ctx:
                self.turno(c)
            self.assertIn(msg, str(ctx.exception), c)
        self.assertEqual(self.p.estado()["turno"], 0)
        with self.assertRaises(SystemExit):
            self.turno({"titulo": ""})

    def test_el_turno_tiene_que_ser_el_siguiente(self):
        f = self.p.cronica / "turno_005.md"
        f.write_text('## Narración\n\n```cambios\n{"titulo": "x", "evento": "x"}\n```\n', encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            Ci.cerrar(self.p, f)
        self.assertIn("toca el 1", str(ctx.exception))


class Dados(Base):
    def test_tirada_queda_apuntada_y_se_puede_citar(self):
        t = D.tirar(self.p, mod=3, cd=12, motivo="honda", azar=random.Random(1))
        self.assertEqual(t["n"], 1)
        self.assertEqual(t["total"], t["d20"] + 3)
        self.assertIn(t["resultado"], ("exito", "fallo", "pifia", "maestria"))
        self.turno({"tiradas": [1]})
        self.assertEqual(self.p.estado()["timeline"][-1]["tiradas"], [1])

    def test_ventaja_y_desventaja(self):
        az = random.Random(7)
        for _ in range(50):
            v = D.tirar(self.p, ventaja=True, azar=az)
            self.assertEqual(v["d20"], max(v["dados"]))
            d = D.tirar(self.p, desventaja=True, azar=az)
            self.assertEqual(d["d20"], min(d["dados"]))


class Sistemas(Base):
    def test_un_sistema_que_toca_lo_que_no_declara_no_cierra(self):
        mundo = self.tmp / "mundo_malo"
        shutil.copytree(MUNDO, mundo)
        (mundo / "sistemas" / "cosecha.py").write_text(
            (MUNDO / "sistemas" / "cosecha.py").read_text().replace(
                's.col["objetos"]["trigo"]["cantidad"]', 's.col["personas"]["abi"]["animo"]'), encoding="utf-8")
        p = P.nueva(self.tmp / "p2", mundo)
        f = Ci.plantilla(p)
        f.write_text('## Narración\n\n```cambios\n{"titulo": "x", "evento": "x", "tiempo": {"dias": 1}}\n```\n')
        with self.assertRaises(SystemExit) as ctx:
            Ci.cerrar(p, f)
        self.assertIn("ha tocado 'personas'", str(ctx.exception))

    def test_contrato_incompleto_o_sin_datos(self):
        mundo = self.tmp / "mundo_sin"
        shutil.copytree(MUNDO, mundo)
        (mundo / "datos" / "cosecha.json").unlink()
        p = P.nueva(self.tmp / "p3", mundo)
        f = Ci.plantilla(p)
        f.write_text('## Narración\n\n```cambios\n{"titulo": "x", "evento": "x"}\n```\n')
        with self.assertRaises(SystemExit) as ctx:
            Ci.cerrar(p, f)
        self.assertIn("datos/cosecha.json", str(ctx.exception))


class Linea(Base):
    def test_la_linea_de_ordenes(self):
        self.assertIn("turno 1 (cerrado: 0)", self.motor("briefing").stdout)
        f = Path(self.motor("plantilla").stdout.strip())
        txt = f.read_text().replace('"titulo": ""', '"titulo": "Llegada"').replace('"evento": ""', '"evento": "llegan"')
        f.write_text(txt)
        self.assertIn("simulado", self.motor("cerrar", str(f), "--simular").stdout)
        self.assertIn("Turno 1 cerrado", self.motor("cerrar", str(f)).stdout)
        self.assertRegex(self.motor("tirar", "--mod", "2", "--cd", "10", "honda").stdout, r"tirada #1: d20 \d+")
        self.assertEqual(self.motor("validar").stdout.strip(), "ok")
        self.assertIn('"nombre": "cosecha"', self.motor("sistemas").stdout)
        r = self.motor("cerrar", "cronica/no.md", ok=False)
        self.assertIn("No existe el archivo", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
