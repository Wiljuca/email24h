#!/usr/bin/env python3
import os
import smtplib
import json
import urllib.request
import urllib.parse
from email.message import EmailMessage
from datetime import datetime, timedelta
# Importa as configurações do seu arquivo security_config.py
from security_config import get_email_credentials, get_telegram_credentials, get_required_secret

def get_real_prices(origin_id="CGB", destination_id="OPS"):
    """
    Busca os preços reais da Azul e GOL usando a API Skyscanner via RapidAPI.
    Usa urllib para evitar erro de 'module not found' no GitHub Actions.
    """
    try:
        # Busca a chave da RapidAPI usando sua função de segurança
        rapidapi_key = get_required_secret("RAPIDAPI_KEY")
        rapidapi_host = "skyscanner-flights-travel-api.p.rapidapi.com"

        # Define a data para daqui a 30 dias
        data_voo = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        params = {
            "originSkyId": origin_id,
            "destinationSkyId": destination_id,
            "date": data_voo,
            "adults": "1",
            "cabinClass": "economy",
            "currency": "BRL",
            "market": "BR",
            "countryCode": "BR"
        }
        
        url = f"https://{rapidapi_host}/flights/searchFlights?" + urllib.parse.urlencode(params )
        
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        prices = {"azul": "N/A", "gol": "N/A"}
        itineraries = data.get('data', {}).get('itineraries', [])
        
        for flight in itineraries:
            price = flight.get('price', {}).get('formatted', 'N/A')
            legs = flight.get('legs', [])
            if not legs: continue
            
            carriers = legs[0].get('carriers', {}).get('marketing', [])
            if not carriers: continue
            
            carrier_name = carriers[0].get('name', '').upper()
            
            if "AZUL" in carrier_name and prices["azul"] == "N/A":
                prices["azul"] = price
            elif "GOL" in carrier_name and prices["gol"] == "N/A":
                prices["gol"] = price
                
            if prices["azul"] != "N/A" and prices["gol"] != "N/A":
                break
                
        return prices

    except Exception as e:
        print(f"❌ Erro ao buscar preços na API: {e}")
        return None

def send_email_notification(prices):
    email, password = get_email_credentials()
    
    azul = prices.get('azul', 'N/A') if prices else "Erro API"
    gol = prices.get('gol', 'N/A') if prices else "Erro API"
    
    msg = EmailMessage()
    msg.set_content(
        f"✈️ PREÇOS REAIS ENCONTRADOS:\n\n"
        f"🔵 AZUL: {azul}\n"
        f"🟠 GOL: {gol}\n\n"
        f"🚀 Dados extraídos automaticamente via API Skyscanner."
    )
    
    msg["Subject"] = f"✈️ Preços {datetime.now().strftime('%d/%m %H:%M')}"
    msg["From"] = email
    msg["To"] = email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(email, password)
            server.send_message(msg)
        print("✅ E-mail enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail: {e}")

def send_telegram_notification(prices):
    token, chat_id = get_telegram_credentials()
    
    azul = prices.get('azul', 'N/A') if prices else "Erro API"
    gol = prices.get('gol', 'N/A') if prices else "Erro API"
    
    message = (
        f"✈️ *PREÇOS REAIS*\n"
        f"🔵 AZUL: {azul}\n"
        f"🟠 GOL: {gol}\n"
        f"🚀 Dados via API Skyscanner"
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        data = json.dumps(payload ).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            print("✅ Telegram enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar Telegram: {e}")

def main():
    # Busca os preços para Cuiabá (CGB) -> Sinop (OPS)
    prices = get_real_prices("CGB", "OPS")
    
    # Envia as notificações
    send_email_notification(prices)
    send_telegram_notification(prices)

if __name__ == "__main__":
    main()







