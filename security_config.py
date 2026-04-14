"""
Configuração central de secrets para projeto público.
Carrega credenciais apenas de variáveis de ambiente e falha cedo com mensagem clara.
"""
import os


def get_required_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Secret obrigatório ausente: {name}")
    return value


def get_email_credentials() -> tuple[str, str]:
    email = get_required_secret("GMAIL_USER")
    password = get_required_secret("GMAIL_PASS")
    return email, password


def get_telegram_credentials() -> tuple[str, str]:
    token = get_required_secret("TELEGRAM_BOT_TOKEN")
    chat_id = get_required_secret("TELEGRAM_CHAT_ID")
    return token, chat_id
