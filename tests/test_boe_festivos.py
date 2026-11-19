import json, sys, unittest
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import boe_festivos as b

XML = (Path(__file__).parent / "fixtures" / "boe_mini.xml").read_bytes()
EXTRA = b"".join(f"<tr><td>{d} Prueba.</td>".encode() + b"<td>*</td>" * 19 + b"</tr>" for d in range(10, 20))


class TestParser(unittest.TestCase):
    def test_rechaza_incompleto(self):
        with self.assertRaises(ValueError):
            b.parsear(XML, 2027)

    def test_lee_estructura_real(self):
        d = b.parsear(XML.replace(b"</table>", EXTRA + b"</table>"), 2027)
        self.assertEqual(len(d["regiones"]), 19)
        self.assertEqual(d["fiestas"][0]["fecha"], "2027-01-01")
        self.assertEqual(d["fiestas"][0]["nombre"], "Año Nuevo")
        self.assertEqual(d["fiestas"][1], {"fecha": "2027-03-01", "nombre": "Día de Andalucía", "marcas": {"Andalucía": "***"}})
        self.assertEqual(d["leyenda"]["***"], "Fiesta de Comunidad Autónoma")


class TestDatosPublicados(unittest.TestCase):
    def test_coherencia_2027(self):
        d = json.loads((RAIZ / "data/es/festivos-2027.json").read_text(encoding="utf-8"))
        cuenta = {r: 0 for r in d["regiones"]}
        for f in d["fiestas"]:
            for r in f["marcas"]:
                cuenta[r] += 1
        # Estatuto: maximo 14 fiestas, 2 locales -> 12 entre nacionales y autonomicas
        self.assertTrue(all(n <= 12 for n in cuenta.values()), cuenta)
        self.assertEqual(sorted(set(cuenta.values())), [11, 12])  # Canarias completa con la insular


if __name__ == "__main__":
    unittest.main()
