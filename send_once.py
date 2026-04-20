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

def call_duffel_api(endpoint, method="GET", body=None):
    """Faz chamadas para a API da Duffel usando urllib."""
    token = get_required_secret("DUFFEL_ACCESS_TOKEN")
    url = f"https://api.duffel.com/air/{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v1",
        "Content-Type": "application/json"
    }
    
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Erro na Duffel ({e.code}): {error_body}")
        return None
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return None

def get_best_prices_duffel():
    """Busca os melhores preços da Azul e GOL nos próximos 45 dias via Duffel."""
    best_azul = {"price": float('inf'), "formatted": "N/A", "date": "N/A"}
    best_gol = {"price": float('inf'), "formatted": "N/A", "date": "N/A"}
    
    # Configurações de Origem e Destino (CGB -> OPS)
    origin = "CGB"
    destination = "OPS"
    
    print(f"🚀 Iniciando busca Duffel: {origin} -> {destination}")

    # Consultando em intervalos para cobrir 45 dias de forma eficiente
    # Duffel permite buscar uma data específica por requisição
    for i in range(0, 46, 5):
        target_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        print(f"🔍 Consultando data: {target_date}...")
        
        # 1. Criar Offer Request
        search_body = {
            "data": {
                "slices": [
                    {
                        "origin": origin,
                        "destination": destination,
                        "departure_date": target_date
                    }
                ],
                "passengers": [{"type": "adult"}],
                "cabin_class": "economy"
            }
        }
        
        response = call_duffel_api("offer_requests", method="POST", body=search_body)
        
        if not response or "data" not in response:
            continue
            
        offers = response["data"].get("offers", [])
        print(f"✅ {len(offers)} ofertas encontradas para {target_date}")

        for offer in offers:
            price_raw = float(offer.get("total_amount", float('inf')))
            currency = offer.get("total_currency", "BRL")
            
            # Identificar a companhia aérea (owner)
            owner = offer.get("owner", {})
            name = owner.get("name", "").upper()
            code = owner.get("iata_code", "").upper()
            
            # Filtro Azul (AD) e GOL (G3)
            is_azul = "AZUL" in name or code == "AD"
            is_gol = "GOL" in name or code == "G3"
            
            if is_azul and price_raw < best_azul["price"]:
                best_azul = {"price": price_raw, "formatted": f"{currency} {price_raw}", "date": target_date}
            if is_gol and price_raw < best_gol["price"]:
                best_gol = {"price": price_raw, "formatted": f"{currency} {price_raw}", "date": target_date}
        
        time.sleep(1) # Evitar rate limit

    return best_azul, best_gol

def main():
    print("🚀 Iniciando script v15 (Duffel Edition)...")
    
    azul, gol = get_best_prices_duffel()
    
    email, password = get_email_credentials()
    token, chat_id = get_telegram_credentials()

    msg_text = "✈️ MELHORES PREÇOS - DUFFEL EDITION (v15):\n\n"
    msg_text += f"🔵 AZUL: {azul['formatted']} (Data: {azul['date']})\n"
    msg_text += f"🟠 GOL: {gol['formatted']} (Data: {gol['date']})\n\n"
    msg_text += f"Status: Monitoramento de 45 dias concluído via Duffel API.\n"
    msg_text += f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"

    # Enviar Notificações
    try:
        # E-mail
        msg = EmailMessage()
        msg.set_content(msg_text)
        msg["Subject"] = f"✈️ Alerta Duffel {datetime.now().strftime('%H:%M')}"
        msg["From"] = email
        msg["To"] = email
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(email, password)
            s.send_message(msg)
        print("✅ E-mail enviado!")
        
        # Telegram
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": msg_text}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req)
        print("✅ Telegram enviado!")
        
    except Exception as e:
        print(f"❌ Erro nas notificações: {e}")

if __name__ == "__main__":
    main()






