from datetime import datetime, timezone

def normalizar_texto(texto: str) -> str:
    """Normaliza um texto para facilitar as comparações."""

    return " ".join(texto.split()).casefold()


def textos_iguais(texto1: str, texto2: str) -> bool:
    """Verifica se as duas descrições são equivalentes."""

    return normalizar_texto(texto1) == normalizar_texto(texto2)



def normalizar_data(data_hora: str) -> str | None:
    """Converte datas com fuso horário para UTC."""

    try:
        data = datetime.fromisoformat(
            data_hora.strip().replace("Z", "+00:00")
        )

        if data.tzinfo is None:
            return None

        return data.astimezone(timezone.utc).isoformat()

    except ValueError:
        return None



def chave_movimentacao(
    texto: str,
    data_hora_origem: str | None
) -> tuple[str, str] | None:
    """Cria uma chave usando texto e data oficial normalizada."""

    if not data_hora_origem:
        return None

    data_normalizada = normalizar_data(data_hora_origem)

    if data_normalizada is None:
        return None

    return (
        normalizar_texto(texto),
        data_normalizada
    )




def movimentacao_duplicada(
    texto: str,
    data_hora_origem: str | None,
    movimentacoes_existentes: list[dict]
) -> bool:
    """Verifica se uma movimentação já foi registrada."""

    chave_nova = chave_movimentacao(
        texto,
        data_hora_origem
    )

    if chave_nova is None:
        return False

    for movimentacao in movimentacoes_existentes:
        chave_existente = chave_movimentacao(
            movimentacao.get("texto", ""),
            movimentacao.get("data_hora_origem")
        )

        if chave_nova == chave_existente:
            return True

    return False
