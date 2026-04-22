#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import time
import logging
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib

# ============================================
# LOGGING SEGURO
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============================================
# CONSTANTES
# ============================================

DUFFEL_API_BASE = "https://api.duffel.com/air"
DUFFEL_VERSION = "2025-02-17" # Versão atual. Duffel muda a cada 2-3 meses
ORIGIN = "CGB"
DESTINATION = "OPS"
SEARCH_DAYS = 45
INTERVAL_DAYS = 5
MAX_RETRIES = 3
RETRY_DELAY = 2
CACHE_DIR = Path("/tmp/duffel_cache")
CACHE_EXPIRY = 3600
POLLING_ATTEMPTS = 4
POLLING_DELAY = 1.5

CACHE_DIR.mkdir(exist_ok=True)

# ============================================
# CACHE
# ============================================

class DuffelCache:
    @staticmethod
    def get_cache_key(endpoint: str, params: Dict) -> str:
        key_str = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    @staticmethod
    def get(endpoint: str, params: Dict) -> Optional[Dict]:
        cache_key = DuffelCache.get_cache_key(endpoint, params)
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age > CACHE_EXPIRY:
            cache_file.unlink()
            return None
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def set(endpoint: str, params: Dict, data: Dict) -> None:
        cache_key = DuffelCache.get_cache_key(endpoint, params)
        cache_file = CACHE_DIR / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

# ============================================
# CLIENTE DUFFEL
# ============================================

class DuffelClient:
    def __init__(self, token: str):
        self.token = token

    def call_api(self, endpoint: str, method: str = "GET", body: Optional[Dict] = None,
                 retry_count: int = 0) -> Optional[Dict]:

        cache_key = {"endpoint": endpoint, "method": method, "body": body}
        cached_response = DuffelCache.get(endpoint, cache_key)
        if cached_response:
            logger.info(f"CACHE_HIT endpoint={endpoint}")
            return cached_response

        url = f"{DUFFEL_API_BASE}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Duffel-Version": DUFFEL_VERSION,
            "Content-Type": "application/json",
            "User-Agent": "DuffelMonitor/v20.1"
        }
        data = json.dumps(body).encode("utf-8") if body else None

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                DuffelCache.set(endpoint, cache_key, response_data)
                logger.info(f"API_OK method={method} endpoint={endpoint} status={response.status}")
                return response_data

        except urllib.error.HTTPError as e:
            err_type = "unknown"
            err_title = ""
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                err_obj = error_json.get('errors', [{}])[0]
                err_type = err_obj.get('type', 'unknown')
                # Logamos só o title, nunca detail/request_id/meta
                err_title = err_obj.get('title', '')
            except Exception:
                pass
            logger.error(f"API_ERR method={method} endpoint={endpoint} status={e.code} type={err_type} title={err_title}")

            if (e.code >= 500 or e.code == 429) and retry_count < MAX_RETRIES:
                wait_time = RETRY_DELAY * (2 ** retry_count)
                logger.info(f"RETRY attempt={retry_count + 1}/{MAX_RETRIES} wait={wait_time}s")
                time.sleep(wait_time)
                return self.call_api(endpoint, method, body, retry_count + 1)
            return None

        except Exception as e:
            logger.error(f"API_EXC method={method} endpoint={endpoint} exc={type(e).__name__}")
            if retry_count < MAX_RETRIES:
                wait_time = RETRY_DELAY * (2 ** retry_count)
                time.sleep(wait_time)
                return self.call_api(endpoint, method, body, retry_count + 1)
            return None

# ============================================
# BUSCA COM SCHEMA CORRETO DA VERSÃO 2025-02-17
# ============================================

def search_prices(client: DuffelClient) -> Tuple[Dict, Dict]:
    best_azul = {"price": float('inf'), "formatted": "N/A", "date": "N/A", "airline": "Azul"}
    best_gol = {"price": float('inf'), "formatted": "N/A", "date": "N/A", "airline": "GOL"}

    logger.info(f"SEARCH_START origin={ORIGIN} dest={DESTINATION} days={SEARCH_DAYS} interval={INTERVAL_DAYS}")
    total_offers = 0
    zero_offers_requests = 0

    for i in range(1, SEARCH_DAYS + 1, INTERVAL_DAYS):
        target_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        logger.info(f"SEARCH_DATE date={target_date}")

        # CORREÇÃO: cabin_class agora vai dentro do slice
        search_body = {
            "data": {
                "slices": [{
                    "origin": ORIGIN,
                    "destination": DESTINATION,
                    "departure_date": target_date,
                    "cabin_class": "economy" # <-- MUDOU AQUI
                }],
                "passengers": [{"type": "adult"}]
            }
        }

        response = client.call_api("offer_requests", method="POST", body=search_body)
        if not response or "data" not in response:
            logger.warning(f"SEARCH_SKIP date={target_date} reason=no_offer_request")
            continue

        offer_request_id = response["data"]["id"]

        offers = []
        for attempt in range(POLLING_ATTEMPTS):
            if attempt > 0:
                time.sleep(POLLING_DELAY)
            offers_resp = client.call_api(f"offers?offer_request_id={offer_request_id}&limit=50", method="GET")
            if offers_resp and "data" in offers_resp:
                offers = offers_resp["data"]
                if offers:
                    logger.info(f"OFFERS_FOUND date={target_date} count={len(offers)} attempt={attempt+1}")
                    break

        if not offers:
            zero_offers_requests += 1
            logger.warning(f"OFFERS_EMPTY date={target_date}")
            continue

        total_offers += len(offers)
        for offer in offers:
            try:
                price_raw = float(offer.get("total_amount", float('inf')))
                currency = offer.get("total_currency", "BRL")
                owner = offer.get("owner", {})
                name = owner.get("name", "").upper()
                code = owner.get("iata_code", "").upper()

                is_azul = "AZUL" in name or code == "AD"
                is_gol = "GOL" in name or code == "G3"

                if is_azul and price_raw < best_azul["price"]:
                    best_azul = {"price": price_raw, "formatted": f"{currency} {price_raw:.2f}", "date": target_date, "airline": "Azul"}
                    logger.info(f"BEST_AZUL price={price_raw:.2f} date={target_date}")

                if is_gol and price_raw < best_gol["price"]:
                    best_gol = {"price": price_raw, "formatted": f"{currency} {price_raw:.2f}", "date": target_date, "airline": "GOL"}
                    logger.info(f"BEST_GOL price={price_raw:.2f} date={target_date}")
            except Exception:
                continue
        time.sleep(0.5)

    logger.info(f"SEARCH_END total_offers={total_offers} zero_offers_requests={zero_offers_requests}")
    if total_offers == 0:
        logger.error("SEARCH_FAIL reason=no_inventory_or_test_token")
    return best_azul, best_gol

# ============================================
# NOTIFICAÇÕES
# ============================================

def send_email(azul: Dict, gol: Dict) -> bool:
    try:
        email = os.getenv("GMAIL_USER")
        password = os.getenv("GMAIL_PASS")
        if not email or not password:
            logger.error("EMAIL_SKIP reason=missing_env")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✈️ Alerta Duffel - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        msg["From"] = email
        msg["To"] = email

        html = f"""
        <html><body style="font-family: Arial, sans-serif;">
        <h2>✈️ MELHORES PREÇOS - DUFFEL EDITION (v20.1)</h2>
        <p><strong>Rota:</strong> {ORIGIN} → {DESTINATION}</p><hr>
        <h3>🔵 AZUL</h3><p><strong>Preço:</strong> {azul['formatted']}</p><p><strong>Data:</strong> {azul['date']}</p><hr>
        <h3>🟠 GOL</h3><p><strong>Preço:</strong> {gol['formatted']}</p><p><strong>Data:</strong> {gol['date']}</p><hr>
        <p><small>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</small></p>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email, password)
            server.send_message(msg)
        logger.info("EMAIL_OK")
        return True
    except Exception as e:
        logger.error(f"EMAIL_ERR exc={type(e).__name__}")
        return False

def send_telegram(azul: Dict, gol: Dict) -> bool:
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            logger.error("TELEGRAM_SKIP reason=missing_env")
            return False

        msg_text = f"""✈️ MELHORES PREÇOS - DUFFEL EDITION (v20.1)

🔵 AZUL: {azul['formatted']}
📅 Data: {azul['date']}

🟠 GOL: {gol['formatted']}
📅 Data: {gol['date']}

Rota: {ORIGIN} → {DESTINATION}
⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"""

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": msg_text}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("ok"):
                logger.info("TELEGRAM_OK")
                return True
            logger.error("TELEGRAM_ERR reason=api_false")
            return False
    except Exception as e:
        logger.error(f"TELEGRAM_ERR exc={type(e).__name__}")
        return False

# ============================================
# MAIN
# ============================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 Script v20.1 - Duffel Edition SEGURA")
    logger.info("=" * 60)

    token = os.getenv("DUFFEL_ACCESS_TOKEN")
    if not token:
        logger.error("INIT_FAIL reason=missing_duffel_token")
        sys.exit(1)

    client = DuffelClient(token)
    try:
        azul, gol = search_prices(client)
    except Exception as e:
        logger.error(f"SEARCH_EXC exc={type(e).__name__}")
        sys.exit(1)

    msg_text = f"✈️ MELHORES PREÇOS - DUFFEL EDITION (v20.1):\n\n🔵 AZUL: {azul['formatted']} (Data: {azul['date']})\n🟠 GOL: {gol['formatted']} (Data: {gol['date']})\n\nRota: {ORIGIN} → {DESTINATION}\nVersão API: {DUFFEL_VERSION}\nGerado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    logger.info("\n" + msg_text)

    result = {"timestamp": datetime.now().isoformat(), "origin": ORIGIN, "destination": DESTINATION, "azul": azul, "gol": gol}
    try:
        with open("/tmp/duffel_result.json", 'w') as f:
            json.dump(result, f, indent=2)
        logger.info("RESULT_SAVED path=/tmp/duffel_result.json")
    except Exception:
        pass

    logger.info("NOTIFY_START")
    email_sent = send_email(azul, gol)
    telegram_sent = send_telegram(azul, gol)
    if email_sent or telegram_sent:
        logger.info("NOTIFY_OK")
    else:
        logger.warning("NOTIFY_FAIL")

    logger.info("=" * 60)
    logger.info("✅ Script finalizado")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()



