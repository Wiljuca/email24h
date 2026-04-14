#!/usr/bin/env python3
import os
import smtplib
import json
import urllib.request
import urllib.parse
import time
from email.message import EmailMessage
from datetime import datetime, timedelta
from security_config import get_email_credentials, get_telegram_credentials, get_required_secret

def get_entity_id(sky_id, key, host):
    """Busca o entityId para um determinado skyId."""
    url = f"https://{host}/flights/searchAirport?query={sky_id}"
    req = urllib.request.Request(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") and data.get("data"):
                for item in data["data"]:
                    if item.get("skyId") == sky_id:
                        return item.get("entityId")
                return data["data"][0].get("entityId")
    except Exception as e:
        print(f"⚠️ Erro ao buscar entityId para {sky_id}: {e}")
    return None

def get_prices_for_date(date_str, origin_sky, dest_sky, origin_ent, dest_ent, key, host):
    """Busca preços para uma data específica."""
    params = {
        "originSkyId": origin_sky,
        "destinationSkyId": dest_sky,
        "originEntityId": origin_ent,
        "destinationEntityId": dest_ent,
        "date": date_str,
        "currency": "BRL",
        "market": "BR",
        "countryCode": "BR"
    }
    url = f"https://{host}/flights/searchFlights?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host})
    
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
            itineraries = data.get("data", {}).get("itineraries", [])
            if not itineraries and "itineraries" in data:
                itineraries = data["itineraries"]
            return itineraries
    except Exception as e:
        print(f"⚠️ Erro na data {date_str}: {e}")
        return []

def get_best_prices_45_days():
    """Busca os melhores preços da Azul e GOL nos próximos 45 dias."""
    try:
        key = get_required_secret("RAPIDAPI_KEY")
        host = "skyscanner-flights-travel-api.p.rapidapi.com"

        origin_sky, dest_sky = "CGB", "OPS"
        origin_ent = get_entity_id(origin_sky, key, host) or "95673515"
        dest_ent = get_entity_id(dest_sky, key, host) or "95673516"

        best_azul = {"price": float('inf'), "formatted": "N/A", "date": ""}
        best_gol = {"price": float('inf'), "formatted": "N/A", "date": ""}

        # Para não estourar o limite da API, vamos testar datas estratégicas
        # (ex: a cada 3 dias nos próximos 45 dias para cobrir o período sem excesso de chamadas)
        # Se você tiver limite alto, pode mudar o step para 1.
        for i in range(0, 46, 3): 
            current_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            print(f"🔍 Consultando data: {current_date}...")
            
            itineraries = get_prices_for_date(current_date, origin_sky, dest_sky, origin_ent, dest_ent, key, host)
            
            for f in itineraries:
                price_raw = f.get('price', {}).get('raw', float('inf'))
                price_fmt = f.get('price', {}).get('formatted', 'N/A')
                
                carriers_found = []
                legs = f.get('legs', [])
                for leg in legs:
                    marketing_carriers = leg.get('carriers', {}).get('marketing', [])
                    for carrier in marketing_carriers:
                        carriers_found.append(carrier.get('name', '').upper())

                for c in carriers_found:
                    if "AZUL" in c and price_raw < best_azul["price"]:
                        best_azul = {"price": price_raw, "formatted": price_fmt, "date": current_date}
                    if "GOL" in c and price_raw < best_gol["price"]:
                        best_gol = {"price": price_raw, "formatted": price_fmt, "date": current_date}
            
            # Pequena pausa para evitar bloqueio por excesso de requisições
            time.sleep(1)

        return best_azul, best_gol
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return None, None

def main():
    print("🚀 Iniciando busca de 45 dias...")
    azul, gol = get_best_prices_45_days()
    
    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()

    msg_text = "✈️ MELHORES PREÇOS (PRÓXIMOS 45 DIAS):\n\n"
    msg_text += f"🔵 AZUL: {azul['formatted']} (Data: {azul['date']})\n"
    msg_text += f"🟠 GOL: {gol['formatted']} (Data: {gol['date']})\n\n"
    msg_text += "🚀 Via API Skyscanner (Busca em intervalo)"

    # Enviar E-mail
    try:
        msg = EmailMessage()
        msg.set_content(msg_text)
        msg["Subject"] = f"✈️ Alerta de Preços {datetime.now().strftime('%H:%M')}"
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







