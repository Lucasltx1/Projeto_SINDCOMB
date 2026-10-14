import unittest

from app.modulos.processos.duplicidade_service import (
    movimentacao_duplicada,
    normalizar_data,
)


class TestDuplicidade(unittest.TestCase):

    def test_movimentacao_duplicada(self):
        existentes = [
            {
                "texto": "Intimação expedida",
                "data_hora_origem": "2026-10-14T15:30:00Z"
            }
        ]

        resultado = movimentacao_duplicada(
            "  INTIMAÇÃO EXPEDIDA  ",
            "2026-10-14T12:30:00-03:00",
            existentes
        )

        self.assertTrue(resultado)

    def test_movimentacao_em_horario_diferente(self):
        existentes = [
            {
                "texto": "Intimação expedida",
                "data_hora_origem": "2026-10-14T15:30:00Z"
            }
        ]

        resultado = movimentacao_duplicada(
            "Intimação expedida",
            "2026-10-14T16:30:00Z",
            existentes
        )

        self.assertFalse(resultado)

    def test_movimentacao_sem_data(self):
        existentes = [
            {
                "texto": "Intimação expedida",
                "data_hora_origem": "2026-10-14T15:30:00Z"
            }
        ]

        resultado = movimentacao_duplicada(
            "Intimação expedida",
            None,
            existentes
        )

        self.assertFalse(resultado)

    def test_data_invalida(self):
        resultado = normalizar_data("data-invalida")

        self.assertIsNone(resultado)


if __name__ == "__main__":
    unittest.main()
