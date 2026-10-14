import base64
import hashlib
import hmac
import secrets


_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def hash_password(senha: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(
        senha.encode("utf-8"),
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
        algoritmo, n, r, p, sal_b64, derivada_b64 = hash_armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        sal = base64.urlsafe_b64decode(sal_b64.encode("ascii"))
        esperada = base64.urlsafe_b64decode(derivada_b64.encode("ascii"))
        recebida = hashlib.scrypt(
            senha.encode("utf-8"),
            salt=sal,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(esperada),
        )
        return hmac.compare_digest(recebida, esperada)
    except (ValueError, TypeError, UnicodeError):
        return False