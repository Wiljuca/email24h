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

def retry_api_call(func, *args, **kwargs):
    max_retries = 3 # Reduzido para 3 para não travar o workflow
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Se for 429, esperamos um tempo fixo e moderado
                wait_time = 15
                print(f"⚠️ Erro 429 (Limite de Requisições). Aguardando {wait_time} segundos...")
                time.sleep(wait_time)
                if attempt < max_retries - 1: continue
                else: raise
            elif e.code in [502, 503, 504] and attempt < max_retries - 1:
                print(f"⚠️ Erro HTTP {e.code}. Tentando novamente em 5 segundos...")
                time.sleep(5)
            else:
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Erro na API: {e}. Tentando novamente em 5 segundos...")
                time.sleep(5)
            else:
                raise
    return None

def get_prices_for_date_raw(date_str, origin_sky, dest_sky, origin_ent, dest_ent, key, host):
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
    
    with urllib.request.urlopen(req, timeout=20) as response:
        raw_data = response.read().decode("utf-8")
        data = json.loads(raw_data)
        
        itineraries = []
        if isinstance(data, dict):
            if 'data' in data and isinstance(data['data'], dict):
                itineraries = data['data'].get('itineraries', [])
            elif 'itineraries' in data:
                itineraries = data.get('itineraries', [])
        
        return itineraries

def get_best_prices_minimal():
    best_azul = {"price": float('inf'), "formatted": "N/A", "date": "N/A"}
    best_gol = {"price": float('inf'), "formatted": "N/A", "date": "N/A"}
    
    try:
        key = get_required_secret("RAPIDAPI_KEY")
        host = "skyscanner-flights-travel-api.p.rapidapi.com"

        # IDs fixos para economizar quota
        origin_sky, dest_sky = "CGB", "OPS"
        origin_ent, dest_ent = "95673515", "95673516"

        # CONSULTA ÚNICA: Apenas uma data para garantir que o script termine
        target_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        print(f"🔍 Consultando data única: {target_date}...")
        
        try:
            itineraries = retry_api_call(get_prices_for_date_raw, target_date, origin_sky, dest_sky, origin_ent, dest_ent, key, host)
        except Exception as e:
            print(f"⚠️ Falha ao buscar preços para {target_date}: {e}")
            return best_azul, best_gol
        
        if not itineraries:
            print(f"Nenhum itinerário encontrado para {target_date}.")
            return best_azul, best_gol

        print(f"✅ {len(itineraries)} itinerários encontrados. Analisando...")

        for f in itineraries:
            if not isinstance(f, dict): continue
            
            price_data = f.get('price', {})
            price_raw = price_data.get('raw') or price_data.get('amount') or float('inf')
            price_fmt = price_data.get('formatted') or f"R$ {price_raw}"
            
            f_str = json.dumps(f).upper()
            is_azul = "AZUL" in f_str or '"AD"' in f_str or " AD " in f_str
            is_gol = "GOL" in f_str or '"G3"' in f_str or " G3 " in f_str

            if is_azul and price_raw < best_azul["price"]:
                best_azul = {"price": price_raw, "formatted": price_fmt, "date": target_date}
            if is_gol and price_raw < best_gol["price"]:
                best_gol = {"price": price_raw, "formatted": price_fmt, "date": target_date}

        return best_azul, best_gol
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        return None, None

def main():
    print("🚀 Iniciando busca de preços (v10 - Modo de Segurança Máxima)...")
    azul, gol = get_best_prices_minimal()
    
    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()

    msg_text = "✈️ PREÇOS ENCONTRADOS (MODO DE SEGURANÇA):\n\n"
    msg_text += f"🔵 AZUL: {azul['formatted']} (Data: {azul['date']})\n"
    msg_text += f"🟠 GOL: {gol['formatted']} (Data: {gol['date']})\n\n"
    msg_text += f"Status: Busca simplificada concluída em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"

    try:
        msg = EmailMessage()
        msg.set_content(msg_text)
        msg["Subject"] = "✈️ Preços de Voos (v10)"
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







