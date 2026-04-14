#!/usr/bin/env python3
import os
import smtplib
import json
import requests
from email.message import EmailMessage
from datetime import datetime, timedelta
from security_config import get_email_credentials, get_telegram_credentials

# --- CONFIGURAÇÃO DA API SKYSCANNER (RAPIDAPI) ---
# No GitHub, cadastre sua chave no "Secrets" como RAPIDAPI_KEY
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "skyscanner-flights-travel-api.p.rapidapi.com"

def get_real_prices(origin_id="CGB", destination_id="OPS"):
    """
    Busca os preços reais da Azul e GOL usando a API Skyscanner via RapidAPI.
    """
    if not RAPIDAPI_KEY:
        print("❌ Erro: RAPIDAPI_KEY não configurada no GitHub Secrets.")
        return None

    url = f"https://{RAPIDAPI_HOST}/flights/searchFlights"
    
    # Define a data para daqui a 30 dias (exemplo)
    data_voo = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    querystring = {
        "originSkyId": origin_id,
        "destinationSkyId": destination_id,
        "date": data_voo,
        "adults": "1",
        "cabinClass": "economy",
        "currency": "BRL",
        "market": "BR",
        "countryCode": "BR"
    }

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=20)
        response.raise_for_status()
        data = response.json()
        
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
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
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





