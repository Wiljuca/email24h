#!/usr/bin/env python3
import smtplib
import json
import urllib.request
import re
import time
from email.message import EmailMessage
from datetime import datetime
from security_config import get_email_credentials, get_telegram_credentials

def get_real_prices(origin="CGB", destination="OPS"):
    """
    Busca os preços diretamente do script.js do site fornecido com sistema de tentativas.
    """
    url = "https://8080-ilddj876s0oigmq53o8ij-57c5bd0c.us2.manus.computer/script.js"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64 ) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                js_content = response.read().decode('utf-8')
                
                # Extrai o bloco MOCK_DATA
                match = re.search(r'const MOCK_DATA = ({.*?});', js_content, re.DOTALL)
                if not match: return None
                
                json_str = match.group(1)
                # Corrige o formato do JavaScript para JSON
                json_str = re.sub(r'(\s)(\w+):', r'\1"\2":', json_str)
                json_str = json_str.replace("'", '"')
                json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
                
                data = json.loads(json_str)
                prices = {"azul": "N/A", "gol": "N/A"}
                
                for airline in ["azul", "gol"]:
                    flights = [f for f in data.get(airline, []) if f['origin'] == origin and f['destination'] == destination]
                    if flights:
                        min_price = min(f['price'] for f in flights)
                        prices[airline] = f"R${min_price:.2f}"
                
                return prices
        except Exception as e:
            print(f"Tentativa {attempt + 1} falhou (Erro: {e}). Tentando novamente...")
            if attempt < max_retries - 1:
                time.sleep(5) # Espera 5 segundos para o site "acordar"
    return None

def send_email_notification(prices) -> None:
    email, password = get_email_credentials()
    azul_price = prices['azul'] if prices else "Offline"
    gol_price = prices['gol'] if prices else "Offline"

    msg = EmailMessage()
    content = f"PASSAGENS {datetime.now().strftime('%d/%m %H:%M')}\n🟠 GOL: {gol_price}\n🔵 AZUL: {azul_price}\n✅ Monitoramento Ativo!"
    msg.set_content(content)
    msg["Subject"] = f"✈️ Preços {datetime.now().strftime('%d/%m %H:%M')}"
    msg["From"] = email
    msg["To"] = email

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
        server.starttls()
        server.login(email, password)
        server.send_message(msg)
    print("✅ E-mail enviado!")

def send_telegram_notification(prices) -> None:
    token, chat_id = get_telegram_credentials()
    azul_price = prices['azul'] if prices else "Offline"
    gol_price = prices['gol'] if prices else "Offline"

    message = f"*PASSAGENS*\n🟠 GOL: {gol_price}\n🔵 AZUL: {azul_price}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    
    data = urllib.parse.urlencode(payload ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    urllib.request.urlopen(req, timeout=10)
    print("✅ Telegram enviado!")

def main():
    prices = get_real_prices("CGB", "OPS")
    send_email_notification(prices)
    send_telegram_notification(prices)

if __name__ == "__main__":
    main()







