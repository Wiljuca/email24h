#!/usr/bin/env python3
import smtplib
import json
import urllib.request
import urllib.parse
from email.message import EmailMessage
from datetime import datetime, timedelta
from security_config import get_email_credentials, get_telegram_credentials

# --- CONFIGURAÇÃO DA API AMADEUS ---
# Substitua pelas chaves que você obteve no site da Amadeus
AMADEUS_API_KEY = "SUA_API_KEY_AQUI"
AMADEUS_API_SECRET = "SEU_API_SECRET_AQUI"

def get_amadeus_token():
    """Obtém o token de acesso da API Amadeus."""
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET
    }
    try:
        encoded_data = urllib.parse.urlencode(data ).encode("utf-8")
        req = urllib.request.Request(url, data=encoded_data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("access_token")
    except Exception as e:
        print(f"Erro ao obter token Amadeus: {e}")
        return None

def get_real_prices(origin="CGB", destination="OPS"):
    """Busca preços reais usando a API Amadeus."""
    token = get_amadeus_token()
    if not token: return None

    # Busca voos para daqui a 30 dias (exemplo de data futura)
    departure_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    url = f"https://test.api.amadeus.com/v2/shopping/flight-offers?originLocationCode={origin}&destinationLocationCode={destination}&departureDate={departure_date}&adults=1&max=5"
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        req = urllib.request.Request(url, headers=headers )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            prices = {"azul": "N/A", "gol": "N/A"}
            
            for offer in data.get("data", []):
                price = offer["price"]["total"]
                carrier = offer["itineraries"][0]["segments"][0]["carrierCode"]
                
                if carrier == "AD" and prices["azul"] == "N/A":
                    prices["azul"] = f"R${price}"
                elif carrier == "G3" and prices["gol"] == "N/A":
                    prices["gol"] = f"R${price}"
            
            if prices["azul"] == "N/A" and prices["gol"] == "N/A" and data.get("data"):
                prices["geral"] = f"R${data['data'][0]['price']['total']}"
                
            return prices
    except Exception as e:
        print(f"Erro ao buscar voos: {e}")
        return None

def send_email_notification(prices) -> None:
    email, password = get_email_credentials()
    azul = prices.get('azul', 'N/A') if prices else "Erro API"
    gol = prices.get('gol', 'N/A') if prices else "Erro API"

    msg = EmailMessage()
    content = f"✈️ PREÇOS REAIS (CGB -> OPS)\n\n🔵 AZUL: {azul}\n🟠 GOL: {gol}\n\n🕒 Atualizado em: {datetime.now().strftime('%d/%m %H:%M')}"
    msg.set_content(content)
    msg["Subject"] = f"✈️ Alerta de Preços {datetime.now().strftime('%d/%m %H:%M')}"
    msg["From"] = email
    msg["To"] = email

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
        server.starttls()
        server.login(email, password)
        server.send_message(msg)
    print("✅ E-mail enviado!")

def send_telegram_notification(prices) -> None:
    token, chat_id = get_telegram_credentials()
    azul = prices.get('azul', 'N/A') if prices else "Erro API"
    gol = prices.get('gol', 'N/A') if prices else "Erro API"
    
    message = f"✈️ *PREÇOS REAIS*\n🔵 AZUL: {azul}\n🟠 GOL: {gol}\n🚀 Dados via API Amadeus"
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




