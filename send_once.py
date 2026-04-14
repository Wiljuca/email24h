#!/usr/bin/env python3
import smtplib
from email.message import EmailMessage
from datetime import datetime
import json
import urllib.request
import urllib.parse
import sys

from security_config import get_email_credentials, get_telegram_credentials


def send_email_notification() -> None:
    email, password = get_email_credentials()

    msg = EmailMessage()
    content = f"""
🛫 PASSAGENS CGB→OPS - {datetime.now().strftime("%d/%m %H:%M")}
🟠 GOL Ida R$847 | Volta R$792
🔵 AZUL Ida R$892 | Volta R$835
📧 Monitoramento GitHub Actions ativo!
📱 Telegram integrado!
"""
    msg.set_content(content)
    msg["Subject"] = f"✈️ Passagens Atualizadas {datetime.now().strftime('%d/%m %H:%M')}"
    msg["From"] = email
    msg["To"] = email

    print(f"--- Iniciando envio de EMAIL para {email} ---")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
        server.starttls()
        print("-> TLS iniciado")
        server.login(email, password)
        print("-> Login realizado com sucesso")
        server.send_message(msg)
    print(f"✅ Email enviado com sucesso às {datetime.now()}")


def send_telegram_notification() -> None:
    token, chat_id = get_telegram_credentials()

    message = (
        f"🛫 *PASSAGENS CGB→OPS* - {datetime.now().strftime('%d/%m %H:%M')}\n"
        "🟠 GOL Ida R$847 | Volta R$792\n"
        "🔵 AZUL Ida R$892 | Volta R$835\n"
        "📧 Email enviado\n"
        "✅ Monitoramento ativo no GitHub Actions"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")

    print("--- Iniciando envio de TELEGRAM ---")
    with urllib.request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8", errors="ignore")
        parsed = json.loads(body)
        if not parsed.get("ok"):
            raise RuntimeError(f"Falha Telegram: {body}")
    print("✅ Telegram enviado com sucesso")


def main() -> int:
    try:
        send_email_notification()
        send_telegram_notification()
        print("✅ Fluxo completo concluído (Email + Telegram)")
        return 0
    except RuntimeError as e:
        print(f"❌ ERROR: {e}")
        return 1
    except smtplib.SMTPAuthenticationError:
        print("❌ ERRO DE AUTENTICAÇÃO SMTP: verifique GMAIL_USER e GMAIL_PASS (Senha de App).")
        return 1
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
