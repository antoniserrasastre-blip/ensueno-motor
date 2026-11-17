"""Tests de los mundos inventados: crear vacío, validar lo que falta, no jugar hasta que esté y abrirlo."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
from nucleo import briefing as B, cierre as Ci, mundos as Mu, partida as P  # noqa: E402

LORE = """# Las islas de niebla — constitución (BORRADOR: se rellena dictando; «⬜» es lo que falta)

ÉPOCA       Un archipiélago sin nombre, en la edad del bronce, siempre en niebla. [Toni]
QUIÉN       Una pescadora de la isla mayor que oye voces en la niebla. [Toni]
SOCIEDAD    Clanes de pescadores; las abuelas mandan. [propuesta del director, aceptada]
TECNOLOGÍA  Bronce, redes de fibra, barcas de piel. [Toni]
NO EXISTE   Hierro · velas · escritura. [Toni]
DE FUERA    Los barcos de los Altos, que nunca se ven enteros. [Toni]
MONEDA      Trueque de pescado seco y ámbar. [Toni]
TONO        Mítico y húmedo. [Toni]
MARCO       No: mundo puro. [Toni]
"""


class Inventado(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="engine_mundos_"))
        self.addCleanup(shutil.rmtree, self.raiz, True)
        self.d, self.p = Mu.crear(self.raiz, "islas_de_niebla", "Las islas de niebla", "🌫")

    def rellenar(self):
        (self.d / "constitucion.md").write_text(LORE, encoding="utf-8")
        (self.d / "inicio.json").write_text(json.dumps({"lugares": {
            "isla_mayor": {"nombre": "La isla mayor", "tipo": "isla", "estado": "conocido"},
            "roca_voces": {"nombre": "La roca de las voces", "tipo": "roca", "estado": "oido"},
            "playa_ambar": {"nombre": "La playa del ámbar", "tipo": "playa", "estado": "visto"}}}))
        cat = json.loads((self.d / "datos" / "catalogo.json").read_text())
        cat["objetos"] = ["Red", "Barca de piel", "Pescado seco", "Ámbar", "Arpón de bronce"]
        (self.d / "datos" / "catalogo.json").write_text(json.dumps(cat, ensure_ascii=False))
        (self.d / "datos" / "habilidades.json").write_text(json.dumps({"habilidades": [
            {"id": "pescar", "nombre": "Pescar", "atributo": "sab"}, {"id": "remar", "nombre": "Remar", "atributo": "fue"},
            {"id": "oir_niebla", "nombre": "Oír la niebla", "atributo": "sab"}]}))
        (self.d / "datos" / "anacronismos.json").write_text(json.dumps({"bloquea": [
            {"que": "hierro", "palabras": ["hierro"]}, {"que": "velas", "palabras": ["vela de barco"]}], "avisa": []}))

    def test_nace_vacio_y_en_construccion(self):
        ap = Mu.validar(self.d)
        self.assertEqual([a["id"] for a in ap if not a["ok"]][:3], ["época", "quién", "sociedad"])
        self.assertTrue(next(a for a in ap if a["id"] == "mapa")["ok"])                     # el mapa no es obligatorio
        self.assertTrue(Mu.en_construccion(self.p))
        self.assertIn("MUNDO EN CONSTRUCCIÓN", B.texto(self.p))
        self.assertEqual(json.loads((self.d / "mundo.json").read_text())["icono"], "🌫")
        with self.assertRaises(SystemExit):
            Mu.crear(self.raiz, "islas_de_niebla", "Otra vez")

    def test_no_se_juega_hasta_que_esta(self):
        f = Ci.plantilla(self.p)
        f.write_text('## Narración\n\n```cambios\n{"titulo": "x", "evento": "x"}\n```\n')
        with self.assertRaises(SystemExit) as ctx:
            Ci.cerrar(self.p, f)
        self.assertIn("en construcción", str(ctx.exception))
        with self.assertRaises(SystemExit) as ctx:
            Mu.listo(self.raiz, "islas_de_niebla")
        self.assertIn("aún falta", str(ctx.exception))

    def test_dictado_validado_y_listo_para_la_sesion_cero(self):
        self.rellenar()
        self.assertTrue(all(a["ok"] for a in Mu.validar(self.d)), Mu.texto_validar(Mu.validar(self.d)))
        self.assertEqual(Mu.listo(self.raiz, "islas_de_niebla"), ["islas_de_niebla_1"])
        p = P.Partida(self.p.dir)
        self.assertFalse(Mu.en_construccion(p))
        self.assertIn("isla_mayor", p.estado()["colecciones"]["lugares"])
        w = json.loads((self.d / "mundo.json").read_text())
        self.assertEqual((w["estado"], w["marco_sueno"]), ("listo", False))
        self.assertEqual(w["jugador"], "Una pescadora de la isla mayor que oye voces en la niebla")       # sin «[Toni]»
        self.assertEqual(w["subtitulo"], "Un archipiélago sin nombre, en la edad del bronce, siempre…")
        self.assertNotIn("BORRADOR", (self.d / "constitucion.md").read_text())
        f = Ci.plantilla(p)
        f.write_text('## Narración\n\nSale con la red.\n\n```cambios\n{"titulo": "x", "evento": "x", "tiempo": {"horas": 2}}\n```\n')
        self.assertEqual(Ci.cerrar(p, f)["turno"], 1)
        f = Ci.plantilla(p)
        f.write_text('## Narración\n\nUn cuchillo de hierro.\n\n```cambios\n{"titulo": "x", "evento": "x"}\n```\n')
        with self.assertRaises(SystemExit):                                                  # su «NO EXISTE» manda
            Ci.cerrar(p, f)


if __name__ == "__main__":
    unittest.main(verbosity=1)
