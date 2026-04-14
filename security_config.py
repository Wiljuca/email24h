import os

def get_required_secret(name: str) -> str:
    # Busca a variável de ambiente e remove espaços extras
    value = os.environ.get(name, "").strip()
    
    # Se não encontrar, tenta buscar com prefixo 'secrets.' (comum em alguns ambientes)
    if not value:
        value = os.environ.get(f"secrets.{name}", "").strip()
    
    if not value:
        print(f"⚠️ Aviso: Secret '{name}' não encontrado no ambiente.")
        return "" # Retorna vazio em vez de travar o script
    return value

def get_email_credentials() -> tuple[str, str]:
    email = get_required_secret("GMAIL_USER")
    password = get_required_secret("GMAIL_PASS")
    return email, password

def get_telegram_credentials() -> tuple[str, str]:
    token = get_required_secret("TELEGRAM_BOT_TOKEN")
    chat_id = get_required_secret("TELEGRAM_CHAT_ID")
    return token, chat_id
