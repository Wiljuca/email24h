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
            if isinstance(data, dict) and data.get("status") and data.get("data"):
                for item in data["data"]:
                    if isinstance(item, dict) and item.get("skyId") == sky_id:
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
            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)
            
            # A API pode retornar uma lista diretamente ou um dicionário com 'data'
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Tenta encontrar a lista de itinerários em vários lugares comuns
                itineraries = data.get("data", {}).get("itineraries", [])
                if not itineraries:
                    itineraries = data.get("itineraries", [])
                if not itineraries:
                    # Se 'data' for uma lista, retorna ela
                    if isinstance(data.get("data"), list):
                        return data["data"]
                return itineraries
            return []
    except Exception as e:
        print(f"⚠️ Erro na data {date_str}: {e}")
        return []

def get_best_prices_45_days():
    """Busca os melhores preços da Azul e GOL nos próximos 45 dias."""
    best_azul = {"price": float('inf'), "formatted": "N/A", "date": "N/A"}
    best_gol = {"price": float('inf'), "formatted": "N/A", "date": "N/A"}
    
    try:
        key = get_required_secret("RAPIDAPI_KEY")
        host = "skyscanner-flights-travel-api.p.rapidapi.com"

        origin_sky, dest_sky = "CGB", "OPS"
        origin_ent = get_entity_id(origin_sky, key, host) or "95673515"
        dest_ent = get_entity_id(dest_sky, key, host) or "95673516"

        # Consultando a cada 5 dias para ser rápido e eficiente
        for i in range(0, 46, 5): 
            current_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            print(f"🔍 Consultando data: {current_date}...")
            
            itineraries = get_prices_for_date(current_date, origin_sky, dest_sky, origin_ent, dest_ent, key, host)
            
            if not isinstance(itineraries, list):
                print(f"⚠️ Resposta inesperada para {current_date}, pulando...")
                continue

            for f in itineraries:
                if not isinstance(f, dict): continue
                
                # Extração segura do preço
                price_data = f.get('price', {})
                if not isinstance(price_data, dict): continue
                
                price_raw = price_data.get('raw', float('inf'))
                price_fmt = price_data.get('formatted', 'N/A')
                
                # Extração segura das companhias aéreas
                carriers_found = []
                legs = f.get('legs', [])
                if isinstance(legs, list):
                    for leg in legs:
                        if not isinstance(leg, dict): continue
                        marketing_carriers = leg.get('carriers', {}).get('marketing', [])
                        if isinstance(marketing_carriers, list):
                            for carrier in marketing_carriers:
                                if isinstance(carrier, dict):
                                    name = carrier.get('name', '').upper()
                                    if name: carriers_found.append(name)

                # Se não achou nas legs, tenta no nível superior do itinerário
                if not carriers_found:
                    itinerary_carriers = f.get('carriers', [])
                    if isinstance(itinerary_carriers, list):
                        for carrier in itinerary_carriers:
                            if isinstance(carrier, dict):
                                name = carrier.get('name', '').upper()
                                if name: carriers_found.append(name)
                            elif isinstance(carrier, str):
                                carriers_found.append(carrier.upper())

                # Atualiza os melhores preços
                for c in carriers_found:
                    if "AZUL" in c and price_raw < best_azul["price"]:
                        best_azul = {"price": price_raw, "formatted": price_fmt, "date": current_date}
                    if "GOL" in c and price_raw < best_gol["price"]:
                        best_gol = {"price": price_raw, "formatted": price_fmt, "date": current_date}
            
            time.sleep(0.5)

        return best_azul, best_gol
    except Exception as e:
        print(f"❌ Erro crítico na busca: {e}")
        return best_azul, best_gol

def main():
    print("🚀 Iniciando busca de 45 dias...")
    azul, gol = get_best_prices_45_days()
    
    # Fallback final para garantir que as variáveis existam
    if not azul: azul = {"formatted": "N/A", "date": "N/A"}
    if not gol: gol = {"formatted": "N/A", "date": "N/A"}

    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()

    msg_text = "✈️ MELHORES PREÇOS (PRÓXIMOS 45 DIAS):\n\n"
    msg_text += f"🔵 AZUL: {azul.get('formatted', 'N/A')} (Data: {azul.get('date', 'N/A')})\n"
    msg_text += f"🟠 GOL: {gol.get('formatted', 'N/A')} (Data: {gol.get('date', 'N/A')})\n\n"
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






