#!/usr/bin/env python3
import os
import smtplib
import json
import urllib.request
import urllib.parse
from email.message import EmailMessage
from datetime import datetime, timedelta
from security_config import get_email_credentials, get_telegram_credentials, get_required_secret

def get_real_prices():
    """Busca preços reais da Azul e GOL via Skyscanner (RapidAPI)."""
    try:
        key = get_required_secret("RAPIDAPI_KEY")
        host = "skyscanner-flights-travel-api.p.rapidapi.com"
        
        # Busca voos para daqui a 15 dias (CGB -> OPS)
        date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        params = {
            "originSkyId": "CGB", 
            "destinationSkyId": "OPS", 
            "date": date, 
            "currency": "BRL", 
            "market": "BR", 
            "countryCode": "BR"
        }
        url = f"https://{host}/flights/searchFlights?" + urllib.parse.urlencode(params )
        
        req = urllib.request.Request(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host})
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        prices = {"azul": "N/A", "gol": "N/A"}
        itineraries = data.get('data', {}).get('itineraries', [])
        
        for f in itineraries:
            p = f.get('price', {}).get('formatted', 'N/A')
            c = f.get('legs', [{}])[0].get('carriers', {}).get('marketing', [{}])[0].get('name', '').upper()
            if "AZUL" in c and prices["azul"] == "N/A": prices["azul"] = p
            if "GOL" in c and prices["gol"] == "N/A": prices["gol"] = p
            if prices["azul"] != "N/A" and prices["gol"] != "N/A": break
        return prices
    except Exception as e:
        print(f"❌ Erro na API: {e}")
        return None

def main():
    prices = get_real_prices()
    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()
    
    azul = prices.get('azul', 'N/A') if prices else "Erro"
    gol = prices.get('gol', 'N/A') if prices else "Erro"
    msg_text = f"✈️ PREÇOS REAIS (CGB-OPS):\n🔵 AZUL: {azul}\n🟠 GOL: {gol}\n🚀 Via API Skyscanner"

    # Enviar E-mail
    msg = EmailMessage()
    msg.set_content(msg_text)
    msg["Subject"] = f"Passagens {datetime.now().strftime('%H:%M')}"
    msg["From"], msg["To"] = email, email
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(); s.login(email, password); s.send_message(msg)
    
    # Enviar Telegram
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown"} ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req)
    print("✅ Notificações enviadas!")

if __name__ == "__main__":
    main()






