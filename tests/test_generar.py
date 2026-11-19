import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generar as g


class TestPuentes(unittest.TestCase):
    def test_jueves_y_viernes_santo_son_un_solo_bloque(self):
        p = g.calcular_puentes(2027, {"2027-03-25": "Jueves Santo", "2027-03-26": "Viernes Santo"})
        self.assertEqual(p, [{"tipo": "largo", "desde": "2027-03-25", "hasta": "2027-03-28", "dias": 4,
                              "fiestas": ["Jueves Santo", "Viernes Santo"]}])

    def test_puente_martes(self):
        p = g.calcular_puentes(2027, {"2027-10-12": "Fiesta Nacional de España"})
        self.assertEqual(p[0]["dia_puente"], "2027-10-11")
        self.assertEqual(p[0]["dias"], 4)

    def test_festivo_en_sabado_no_genera_nada(self):
        self.assertEqual(g.calcular_puentes(2027, {"2027-05-01": "Fiesta del Trabajo"}), [])


if __name__ == "__main__":
    unittest.main()
