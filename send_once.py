#!/usr/bin/env python3
import os
import smtplib
import json
import urllib.request
import urllib.parse
from email.message import EmailMessage
from datetime import datetime, timedelta
from security_config import get_email_credentials, get_telegram_credentials, get_required_secret

def get_entity_id(sky_id, key, host):
    """Busca o entityId para um determinado skyId."""
    url = f"https://{host}/api/v1/flights/searchAirport?query={sky_id}"
    req = urllib.request.Request(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") and data.get("data"):
                for item in data["data"]:
                    if item.get("skyId") == sky_id:
                        return item.get("entityId")
    except Exception as e:
        print(f"⚠️ Erro ao buscar entityId para {sky_id}: {e}")
    return None

def get_real_prices():
    """Busca preços reais da Azul e GOL via Skyscanner (RapidAPI)."""
    try:
        key = get_required_secret("RAPIDAPI_KEY")
        host = "skyscanner-flights-travel-api.p.rapidapi.com"

        # 1. Obter os Entity IDs necessários (CGB e OPS)
        origin_entity = get_entity_id("CGB", key, host)
        dest_entity = get_entity_id("OPS", key, host)

        if not origin_entity or not dest_entity:
            print("❌ Não foi possível obter os Entity IDs necessários.")
            return None

        # 2. Buscar voos para daqui a 15 dias
        date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        params = {
            "originSkyId": "CGB",
            "destinationSkyId": "OPS",
            "originEntityId": origin_entity,
            "destinationEntityId": dest_entity,
            "date": date,
            "currency": "BRL",
            "market": "BR",
            "countryCode": "BR"
        }
        
        url = f"https://{host}/api/v1/flights/searchFlights?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host})
        
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))

        prices = {"azul": "N/A", "gol": "N/A"}
        itineraries = data.get("data", {}).get("itineraries", [])

        for f in itineraries:
            p = f.get('price', {}).get('formatted', 'N/A')
            # A estrutura da resposta pode variar, tentamos capturar o nome da companhia
            legs = f.get('legs', [])
            if legs:
                carriers = legs[0].get('carriers', {}).get('marketing', [])
                if carriers:
                    c = carriers[0].get('name', '').upper()
                    if "AZUL" in c and prices["azul"] == "N/A": prices["azul"] = p
                    if "GOL" in c and prices["gol"] == "N/A": prices["gol"] = p
            
            if prices["azul"] != "N/A" and prices["gol"] != "N/A": break
            
        return prices
    except Exception as e:
        print(f"❌ Erro na API: {e}")
        return None

def main():
    prices = get_real_prices()
    if not prices:
        print("⚠️ Falha ao obter preços. Abortando envio.")
        return

    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()

    azul = prices.get('azul', 'N/A')
    gol = prices.get('gol', 'N/A')
    msg_text = f"✈️ PREÇOS REAIS (CGB-OPS):\n🔵 AZUL: {azul}\n🟠 GOL: {gol}\n🚀 Via API Skyscanner"

    # Enviar E-mail
    try:
        msg = EmailMessage()
        msg.set_content(msg_text)
        msg["Subject"] = f"✈️ Passagens {datetime.now().strftime('%H:%M')}"
        msg["From"] = email
        msg["To"] = email
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(email, password)
            s.send_message(msg)
        print("✅ E-mail enviado!")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail: {e}")

    # Enviar Telegram
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req)
        print("✅ Telegram enviado!")
    except Exception as e:
        print(f"❌ Erro ao enviar Telegram: {e}")

if __name__ == "__main__":
    main()







