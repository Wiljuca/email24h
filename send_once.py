#!/usr/bin/env python3
import smtplib
import json
import urllib.request
import re
from email.message import EmailMessage
from datetime import datetime
from security_config import get_email_credentials, get_telegram_credentials

def get_real_prices(origin="CGB", destination="OPS"):
    """
    Busca os preços diretamente do script.js do site fornecido.
    """
    url = "https://8080-ilddj876s0oigmq53o8ij-57c5bd0c.us2.manus.computer/script.js"
    try:
        with urllib.request.urlopen(url ) as response:
            js_content = response.read().decode('utf-8')
            
            # Extrai o bloco MOCK_DATA usando Regex
            match = re.search(r'const MOCK_DATA = ({.*?});', js_content, re.DOTALL)
            if not match:
                return None
            
            # Limpa o conteúdo para ser um JSON válido (remove vírgulas extras e aspas simples)
            json_str = match.group(1).replace("'", '"')
            # Remove vírgulas antes de fechamento de colchetes/chaves (comum em JS mas inválido em JSON)
            json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
            
            data = json.loads(json_str)
            
            # Filtra os preços para a rota desejada
            prices = {"azul": "N/A", "gol": "N/A"}
            
            for airline in ["azul", "gol"]:
                flights = [f for f in data.get(airline, []) if f['origin'] == origin and f['destination'] == destination]
                if flights:
                    # Pega o menor preço da lista
                    min_price = min(f['price'] for f in flights)
                    prices[airline] = f"R${min_price:.2f}"
            
            return prices
    except Exception as e:
        print(f"Erro ao buscar preços: {e}")
        return None

def send_email_notification(prices) -> None:
    email, password = get_email_credentials()
    
    azul_price = prices['azul'] if prices else "Erro ao buscar"
    gol_price = prices['gol'] if prices else "Erro ao buscar"

    msg = EmailMessage()
    content = f"""
PASSAGENS {datetime.now().strftime("%d/%m %H:%M")}
🟠 GOL: {gol_price}
🔵 AZUL: {azul_price}
✅ Monitoramento Automático Ativo!
"""
    msg.set_content(content)
    msg["Subject"] = f"✈️ Preços Atualizados {datetime.now().strftime('%d/%m %H:%M')}"
    msg["From"] = email
    msg["To"] = email

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
        server.starttls()
        server.login(email, password)
        server.send_message(msg)
    print(f"✅ E-mail enviado com sucesso!")

def send_telegram_notification(prices) -> None:
    token, chat_id = get_telegram_credentials()
    
    azul_price = prices['azul'] if prices else "Erro"
    gol_price = prices['gol'] if prices else "Erro"

    message = (
        f"*PASSAGENS* - {datetime.now().strftime('%d/%m %H:%M')}\n"
        f"🟠 GOL: {gol_price}\n"
        f"🔵 AZUL: {azul_price}\n"
        f"🚀 Dados extraídos do site automaticamente."
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    
    data = urllib.parse.urlencode(payload ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as response:
        print("✅ Telegram enviado com sucesso")

def main():
    # 1. Busca os preços dinâmicos
    prices = get_real_prices("CGB", "OPS")
    
    # 2. Envia as notificações com os preços encontrados
    send_email_notification(prices)
    send_telegram_notification(prices)

if __name__ == "__main__":
    main()




