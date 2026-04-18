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

# Adicionar uma função de retry para chamadas de API
def retry_api_call(func, *args, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except urllib.error.HTTPError as e:
            if e.code in [502, 503, 504] and attempt < max_retries - 1:
                print(f"⚠️ Erro HTTP {e.code}. Tentando novamente em {2 ** attempt} segundos...")
                time.sleep(2 ** attempt)
            else:
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Erro na API: {e}. Tentando novamente em {2 ** attempt} segundos...")
                time.sleep(2 ** attempt)
            else:
                raise
    return None

def get_entity_id_raw(sky_id, key, host):
    """Busca o entityId para um determinado skyId (sem retry inicial)."""
    url = f"https://{host}/flights/searchAirport?query={sky_id}"
    req = urllib.request.Request(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
        if isinstance(data, dict) and data.get("status") and data.get("data"):
            for item in data["data"]:
                if isinstance(item, dict) and item.get("skyId") == sky_id:
                    return item.get("entityId")
            # Fallback para o primeiro item se o skyId exato não for encontrado
            if data["data"]:
                return data["data"][0].get("entityId")
    return None

def get_entity_id(sky_id, key, host):
    try:
        return retry_api_call(get_entity_id_raw, sky_id, key, host)
    except Exception as e:
        print(f"⚠️ Erro final ao buscar entityId para {sky_id}: {e}")
        return None

def get_prices_for_date_raw(date_str, origin_sky, dest_sky, origin_ent, dest_ent, key, host):
    """Busca preços para uma data específica (sem retry inicial)."""
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
                    print("Exemplo do primeiro itinerário (JSON):")
                    print(json.dumps(itineraries[0], indent=2)[:1000])
            elif 'itineraries' in data:
                print(f"Número de itinerários encontrados (raiz): {len(data['itineraries'])}")
        elif isinstance(data, list):
            print(f"A resposta é uma LISTA com {len(data)} itens.")
            if data:
                print("Exemplo do primeiro item da lista:")
                print(json.dumps(data[0], indent=2)[:1000])
        
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

def get_prices_for_date(date_str, origin_sky, dest_sky, origin_ent, dest_ent, key, host):
    try:
        return retry_api_call(get_prices_for_date_raw, date_str, origin_sky, dest_sky, origin_ent, dest_ent, key, host)
    except Exception as e:
        print(f"⚠️ Erro final ao buscar preços para {date_str}: {e}")
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

        # Consultando os próximos 45 dias, a cada 5 dias
        for i in range(0, 46, 5): 
            current_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            print(f"\n🔍 Consultando data: {current_date}...")
            
            itineraries, carriers_map = get_prices_for_date(current_date, origin_sky, dest_sky, origin_ent, dest_ent, key, host)
            
            if not isinstance(itineraries, list) or not itineraries: # Se não houver itinerários, pula para a próxima data
                print(f"Nenhum itinerário encontrado para {current_date}.")
                continue

            for f in itineraries:
                if not isinstance(f, dict): continue
                price_data = f.get('price', {})
                if not isinstance(price_data, dict): continue
                price_raw = price_data.get('raw', float('inf'))
                price_fmt = price_data.get('formatted', 'N/A')
                
                carriers_found = []
                # Prioriza a busca por IDs mapeados
                for leg in f.get('legs', []):
                    for segment in leg.get('segments', []):
                        for operating_carrier_id in segment.get('operatingCarrierIds', []):
                            if str(operating_carrier_id) in carriers_map:
                                carriers_found.append(carriers_map[str(operating_carrier_id)]["name"])
                                carriers_found.append(carriers_map[str(operating_carrier_id)]["code"])
                        for marketing_carrier_id in segment.get('marketingCarrierIds', []):
                            if str(marketing_carrier_id) in carriers_map:
                                carriers_found.append(carriers_map[str(marketing_carrier_id)]["name"])
                                carriers_found.append(carriers_map[str(marketing_carrier_id)]["code"])

                # Fallback: Procura no JSON do itinerário (menos preciso, mas mantém compatibilidade)
                f_str = json.dumps(f).upper()
                if "AZUL" in f_str or " AD " in f_str or '"AD"' in f_str: carriers_found.append("AZUL")
                if "GOL" in f_str or " G3 " in f_str or '"G3"' in f_str: carriers_found.append("GOL")

                for c in set(carriers_found):
                    if ("AZUL" in c or c == "AD") and price_raw < best_azul["price"]:
                        best_azul = {"price": price_raw, "formatted": price_fmt, "date": current_date}
                    if ("GOL" in c or c == "G3") and price_raw < best_gol["price"]:
                        best_gol = {"price": price_raw, "formatted": price_fmt, "date": current_date}
            
            time.sleep(1) # Pequeno delay para evitar sobrecarga da API

        return best_azul, best_gol
    except Exception as e:
        print(f"❌ Erro crítico em get_best_prices_45_days: {e}")
        return None, None

def main():
    print("🚀 Iniciando busca de preços de voos...")
    azul, gol = get_best_prices_45_days()
    
    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()

    msg_text = "✈️ MELHORES PREÇOS ENCONTRADOS:\n\n"
    
    if azul and azul["formatted"] != "N/A":
        msg_text += f"🔵 AZUL: {azul['formatted']} (Data: {azul['date']})\n"
    else:
        msg_text += "🔵 AZUL: Nenhum preço encontrado ou erro na busca.\n"

    if gol and gol["formatted"] != "N/A":
        msg_text += f"🟠 GOL: {gol['formatted']} (Data: {gol['date']})\n\n"
    else:
        msg_text += "🟠 GOL: Nenhum preço encontrado ou erro na busca.\n\n"

    # Enviar Notificações
    try:
        msg = EmailMessage()
        msg.set_content(msg_text)
        msg["Subject"] = "✈️ Melhores Preços de Voos"
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







