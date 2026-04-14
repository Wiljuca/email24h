#!/usr/bin/env python3
import os
import smtplib
import json
import urllib.request
import urllib.parse
from email.message import EmailMessage
from datetime import datetime, timedelta
from security_config import get_email_credentials, get_telegram_credentials, get_required_secret

def get_entity_id(query):
    """Busca o ID correto do aeroporto na API Skyscanner."""
    rapidapi_key = get_required_secret("RAPIDAPI_KEY")
    url = f"https://skyscanner-flights-travel-api.p.rapidapi.com/flights/searchAirport?query={query}"
    headers = {"X-RapidAPI-Key": rapidapi_key, "X-RapidAPI-Host": "skyscanner-flights-travel-api.p.rapidapi.com"}
    try:
        req = urllib.request.Request(url, headers=headers )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data['data'][0]['skyId'] # Pega o primeiro resultado
    except:
        return query # Se falhar, tenta usar o código original (CGB/OPS)

def get_real_prices():
    try:
        rapidapi_key = get_required_secret("RAPIDAPI_KEY")
        if not rapidapi_key: return None

        # 1. Pega os IDs reais (CGB e OPS)
        origin = get_entity_id("CGB")
        dest = get_entity_id("OPS")

        # 2. Busca preços para daqui a 7 dias
        date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        params = {"originSkyId": origin, "destinationSkyId": dest, "date": date, "currency": "BRL", "market": "BR", "countryCode": "BR"}
        url = "https://skyscanner-flights-travel-api.p.rapidapi.com/flights/searchFlights?" + urllib.parse.urlencode(params )
        
        headers = {"X-RapidAPI-Key": rapidapi_key, "X-RapidAPI-Host": "skyscanner-flights-travel-api.p.rapidapi.com"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        prices = {"azul": "N/A", "gol": "N/A"}
        for flight in data.get('data', {}).get('itineraries', []):
            price = flight.get('price', {}).get('formatted', 'N/A')
            carrier = flight.get('legs', [{}])[0].get('carriers', {}).get('marketing', [{}])[0].get('name', '').upper()
            if "AZUL" in carrier and prices["azul"] == "N/A": prices["azul"] = price
            if "GOL" in carrier and prices["gol"] == "N/A": prices["gol"] = price
        return prices
    except Exception as e:
        print(f"❌ Erro na API: {e}")
        return None

def main():
    prices = get_real_prices()
    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()
    
    # Envio de E-mail e Telegram (Mantendo sua lógica)
    azul, gol = (prices.get('azul', 'N/A'), prices.get('gol', 'N/A')) if prices else ("Erro", "Erro")
    msg_text = f"✈️ PREÇOS REAIS:\n🔵 AZUL: {azul}\n🟠 GOL: {gol}"
    
    # Enviar E-mail
    msg = EmailMessage()
    msg.set_content(msg_text)
    msg["Subject"] = f"Passagens {datetime.now().strftime('%H:%M')}"
    msg["From"], msg["To"] = email, email
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(); s.login(email, password); s.send_message(msg)
    
    # Enviar Telegram
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": msg_text} ).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req)

if __name__ == "__main__":
    main()








