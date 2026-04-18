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
    """Busca preços para uma data específica e imprime a estrutura para diagnóstico."""
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
            
            # DIAGNÓSTICO PROFUNDO: Imprime um resumo da estrutura recebida
            print(f"\n--- DIAGNÓSTICO PARA A DATA {date_str} ---")
            if isinstance(data, dict):
                print(f"Campos principais: {list(data.keys())}")
                if 'data' in data and isinstance(data['data'], dict):
                    print(f"Campos dentro de 'data': {list(data['data'].keys())}")
                    itineraries = data['data'].get('itineraries', [])
                    print(f"Número de itinerários encontrados: {len(itineraries)}")
                    if itineraries:
                        # Imprime o primeiro itinerário completo para análise
                        print("Exemplo do primeiro itinerário (JSON):")
                        print(json.dumps(itineraries[0], indent=2)[:1000]) # Limita a 1000 caracteres
                elif 'itineraries' in data:
                    print(f"Número de itinerários encontrados (raiz): {len(data['itineraries'])}")
            elif isinstance(data, list):
                print(f"A resposta é uma LISTA com {len(data)} itens.")
                if data:
                    print("Exemplo do primeiro item da lista:")
                    print(json.dumps(data[0], indent=2)[:1000])
            
            # Retorna os dados para processamento normal
            itineraries = []
            carriers_map = {}
            if isinstance(data, dict):
                d_content = data.get("data", {})
                if isinstance(d_content, dict):
                    itineraries = d_content.get("itineraries", [])
                    carriers_list = d_content.get("carriers", [])
                    for c in carriers_list:
                        if isinstance(c, dict):
                            carriers_map[str(c.get("id", ""))] = {"name": c.get("name", "").upper(), "code": c.get("displayCode", "").upper()}
            
            return itineraries, carriers_map
    except Exception as e:
        print(f"⚠️ Erro na data {date_str}: {e}")
        return [], {}

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

        # Consultando apenas 3 datas para o diagnóstico ser rápido e focado
        for i in [15, 30, 45]: 
            current_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            print(f"\n🔍 Consultando data: {current_date}...")
            
            itineraries, carriers_map = get_prices_for_date(current_date, origin_sky, dest_sky, origin_ent, dest_ent, key, host)
            
            if not isinstance(itineraries, list): continue

            for f in itineraries:
                if not isinstance(f, dict): continue
                price_data = f.get('price', {})
                if not isinstance(price_data, dict): continue
                price_raw = price_data.get('raw', float('inf'))
                price_fmt = price_data.get('formatted', 'N/A')
                
                carriers_found = []
                # Tenta por IDs mapeados
                for cid in f.get('carrierIds', []):
                    if str(cid) in carriers_map:
                        carriers_found.append(carriers_map[str(cid)]["name"])
                        carriers_found.append(carriers_map[str(cid)]["code"])

                # Fallback: Procura no JSON do itinerário
                f_str = json.dumps(f).upper()
                if "AZUL" in f_str or " AD " in f_str or '"AD"' in f_str: carriers_found.append("AZUL")
                if "GOL" in f_str or " G3 " in f_str or '"G3"' in f_str: carriers_found.append("GOL")

                for c in set(carriers_found):
                    if ("AZUL" in c or c == "AD") and price_raw < best_azul["price"]:
                        best_azul = {"price": price_raw, "formatted": price_fmt, "date": current_date}
                    if ("GOL" in c or c == "G3") and price_raw < best_gol["price"]:
                        best_gol = {"price": price_raw, "formatted": price_fmt, "date": current_date}
            
            time.sleep(1)

        return best_azul, best_gol
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        return None, None

def main():
    print("🚀 Iniciando DIAGNÓSTICO PROFUNDO (v5)...")
    azul, gol = get_best_prices_45_days()
    
    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()

    msg_text = "✈️ RESULTADO DO DIAGNÓSTICO:\n\n"
    msg_text += f"🔵 AZUL: {azul.get('formatted', 'N/A')} (Data: {azul.get('date', 'N/A')})\n"
    msg_text += f"🟠 GOL: {gol.get('formatted', 'N/A')} (Data: {gol.get('date', 'N/A')})\n\n"
    msg_text += "⚠️ Por favor, envie o log do GitHub Actions para análise."

    # Enviar Notificações
    try:
        msg = EmailMessage()
        msg.set_content(msg_text)
        msg["Subject"] = "✈️ Diagnóstico de Preços"
        msg["From"] = email
        msg["To"] = email
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(email, password)
            s.send_message(msg)
        print("✅ E-mail enviado!")
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": msg_text}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req)
        print("✅ Telegram enviado!")
    except Exception as e:
        print(f"❌ Erro nas notificações: {e}")

if __name__ == "__main__":
    main()






