import re


_FORMATO_CNJ = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")
_SOMENTE_DIGITOS = re.compile(r"^\d{20}$")


def normalizar_numero_cnj(valor: str) -> str:
    """Mantém o número CNJ formatado ou aplica a pontuação aos 20 dígitos."""
    if not isinstance(valor, str):
        raise ValueError("Informe o número CNJ como texto.")

    numero = valor.strip()
    if _FORMATO_CNJ.fullmatch(numero):
        return numero
    if not _SOMENTE_DIGITOS.fullmatch(numero):
        raise ValueError(
            "Informe os 20 dígitos do processo ou use o formato "
            "NNNNNNN-DD.AAAA.J.TR.OOOO."
        )

    return (
        f"{numero[:7]}-{numero[7:9]}.{numero[9:13]}."
        f"{numero[13]}.{numero[14:16]}.{numero[16:20]}"
    )


def numero_cnj_sem_formatacao(valor: str) -> str:
    """Retorna os 20 dígitos no padrão que a API Pública do DataJud pesquisa."""
    formatado = normalizar_numero_cnj(valor)
    return re.sub(r"\D", "", formatado)


_CODIGO_ESTADO = {
    "01": "ac",
    "02": "al",
    "03": "ap",
    "04": "am",
    "05": "ba",
    "06": "ce",
    "07": "dft",
    "08": "es",
    "09": "go",
    "10": "ma",
    "11": "mt",
    "12": "ms",
    "13": "mg",
    "14": "pa",
    "15": "pb",
    "16": "pr",
    "17": "pe",
    "18": "pi",
    "19": "rj",
    "20": "rn",
    "21": "rs",
    "22": "ro",
    "23": "rr",
    "24": "sc",
    "25": "se",
    "26": "sp",
    "27": "to",
}


def alias_datajud_por_numero(valor: str) -> str:
    """Infere o endpoint DataJud a partir dos campos J/TR do número CNJ."""
    numero = numero_cnj_sem_formatacao(valor)
    segmento = numero[13]
    tribunal = numero[14:16]

    if segmento == "3" and tribunal == "00":
        return "stj"
    if segmento == "4" and tribunal in {"01", "02", "03", "04", "05", "06"}:
        return f"trf{int(tribunal)}"
    if segmento == "5":
        if tribunal == "00":
            return "tst"
        if 1 <= int(tribunal) <= 24:
            return f"trt{int(tribunal)}"
    if segmento == "6":
        if tribunal == "00":
            return "tse"
        estado = _CODIGO_ESTADO.get(tribunal)
        if estado:
            return f"tre-{estado}"
    if segmento == "7" and tribunal == "00":
        return "stm"
    if segmento == "8":
        estado = _CODIGO_ESTADO.get(tribunal)
        if estado:
            return f"tj{estado}"
    if segmento == "9":
        alias_militar = {"13": "tjmmg", "21": "tjmrs", "26": "tjmsp"}
        if tribunal in alias_militar:
            return alias_militar[tribunal]

    raise ValueError(
        f"Não foi possível identificar um endpoint público do DataJud para o segmento "
        f"{segmento} e tribunal {tribunal} deste número."
    )
