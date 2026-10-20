import base64
import hashlib
import hmac
import secrets


_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 5


def hash_password(senha: str) -> str:
    senha_bytes = senha.encode("utf-8")
    if not senha_bytes or len(senha_bytes) > 512:
        raise ValueError("A senha deve ocupar entre 1 e 512 bytes em UTF-8.")
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(
        senha_bytes,
        salt=sal,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=64,
    )
    return "$".join(
        (
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.urlsafe_b64encode(sal).decode("ascii"),
            base64.urlsafe_b64encode(derivada).decode("ascii"),
        )
    )


def verificar_password(senha: str, hash_armazenado: str) -> bool:
    try:
        senha_bytes = senha.encode("utf-8")
        if len(senha_bytes) > 512 or len(hash_armazenado) > 512:
            return False
        algoritmo, n, r, p, sal_b64, derivada_b64 = hash_armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        sal = base64.urlsafe_b64decode(sal_b64.encode("ascii"))
        esperada = base64.urlsafe_b64decode(derivada_b64.encode("ascii"))
        custo_n, bloco_r, paralelismo = int(n), int(r), int(p)
        if (
            custo_n < (1 << 14)
            or custo_n > (1 << 16)
            or custo_n & (custo_n - 1)
            or bloco_r != 8
            or not 1 <= paralelismo <= _SCRYPT_P
            or len(sal) != 16
            or not 32 <= len(esperada) <= 128
        ):
            return False
        recebida = hashlib.scrypt(
            senha_bytes,
            salt=sal,
            n=custo_n,
            r=bloco_r,
            p=paralelismo,
            dklen=len(esperada),
        )
        return hmac.compare_digest(recebida, esperada)
    except (ValueError, TypeError, UnicodeError):
        return False
