"""Validação de segredos e configuração de implantação."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from cryptography.fernet import Fernet


_PREFIXOS_DE_EXEMPLO = ("dev-only", "change-me", "changeme", "replace-me", "placeholder", "example")


def validar_segredo(nome: str, *, minimo: int = 32) -> str:
    valor = os.getenv(nome, "").strip()
    normalizado = valor.casefold()
    if len(valor) < minimo or any(normalizado.startswith(prefixo) for prefixo in _PREFIXOS_DE_EXEMPLO):
        raise RuntimeError(f"Configure {nome} com um valor aleatório de pelo menos {minimo} caracteres.")
    if len(set(valor)) < 8:
        raise RuntimeError(f"{nome} não pode ser composto por poucos caracteres repetidos.")
    return valor


def validar_senha_administrativa_inicial(valor: str) -> None:
    normalizado = valor.strip().casefold()
    if (
        len(valor) < 16
        or len(valor) > 128
        or normalizado in {"adm123", "admin123", "password123456"}
        or any(normalizado.startswith(prefixo) for prefixo in _PREFIXOS_DE_EXEMPLO)
        or len(set(valor)) < 8
    ):
        raise RuntimeError(
            "SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD deve ter de 16 a 128 caracteres e ser única."
        )


def validar_configuracao_seguranca() -> None:
    """Falha cedo para evitar iniciar a API usando segredos de exemplo."""
    validar_segredo("SINDCOMB_AUTH_SECRET")

    chave_email = os.getenv("SINDCOMB_EMAIL_ENCRYPTION_KEY", "").strip()
    try:
        Fernet(chave_email.encode("ascii"))
    except (ValueError, UnicodeError) as erro:
        raise RuntimeError(
            "Configure SINDCOMB_EMAIL_ENCRYPTION_KEY com uma chave Fernet válida."
        ) from erro

    ambiente = os.getenv("SINDCOMB_ENVIRONMENT", "development").strip().casefold()
    if ambiente not in {"development", "test", "production"}:
        raise RuntimeError("SINDCOMB_ENVIRONMENT deve ser development, test ou production.")

    senha_bootstrap = os.getenv("SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD", "")
    if senha_bootstrap:
        validar_senha_administrativa_inicial(senha_bootstrap)

    if ambiente == "production":
        validar_segredo("SINDCOMB_ML_API_KEY")
        senha_postgres = validar_segredo("POSTGRES_PASSWORD", minimo=24)
        if senha_postgres.casefold() in {"dev-only-password", "postgres", "sindcomb"}:
            raise RuntimeError("POSTGRES_PASSWORD deve ser exclusiva em produção.")
        database_url = os.getenv("DATABASE_URL", "")
        try:
            database = urlsplit(database_url)
        except ValueError as erro:
            raise RuntimeError("DATABASE_URL inválida para produção.") from erro
        if database.scheme != "postgresql+psycopg" or database.password != senha_postgres:
            raise RuntimeError(
                "Em produção, DATABASE_URL deve usar PostgreSQL e a senha POSTGRES_PASSWORD configurada."
            )
        origens = [item.strip() for item in os.getenv("SINDCOMB_CORS_ORIGINS", "").split(",") if item.strip()]
        if not origens or any(not item.startswith("https://") for item in origens):
            raise RuntimeError("Em produção, configure SINDCOMB_CORS_ORIGINS com origens HTTPS explícitas.")
        for variavel in ("SINDCOMB_PUBLIC_API_URL", "SINDCOMB_PUBLIC_APP_URL"):
            if not os.getenv(variavel, "").strip().startswith("https://"):
                raise RuntimeError(f"Em produção, {variavel} deve usar HTTPS.")
        smtp_ssl = os.getenv("SMTP_USE_SSL", "false").strip().casefold() in {"1", "true", "yes"}
        smtp_starttls = os.getenv("SMTP_STARTTLS", "true").strip().casefold() in {"1", "true", "yes"}
        if os.getenv("SMTP_HOST", "").strip() and not (smtp_ssl or smtp_starttls):
            raise RuntimeError("Em produção, SMTP precisa usar TLS ou SSL.")
        if os.getenv("SMTP_USERNAME", "").strip() and not os.getenv("SMTP_PASSWORD", ""):
            raise RuntimeError("SMTP_PASSWORD é obrigatória quando SMTP_USERNAME está configurado.")
