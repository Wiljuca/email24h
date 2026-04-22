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
DUFFEL_VERSIONS_TO_TRY = ["v2", "2025-02-17", "2024-12-01"]
ORIGIN = "CGB"
DESTINATION = "OPS"
SEARCH_START_DAY = 1
SEARCH_END_DAY = 45
INTERVAL_DAYS = 5
MAX_RETRIES = 3
RETRY_DELAY = 2
CACHE_DIR = Path("/tmp/duffel_cache")
CACHE_EXPIRY = 3600
POLLING_ATTEMPTS = 4
POLLING_DELAY = 1.5
CURRENCY_CACHE = {} # Cache de cotação pra não bater na API toda hora

CACHE_DIR.mkdir(exist_ok=True)

# ============================================
# COTAÇÃO DE MOEDAS
# ============================================

def get_exchange_rate(from_currency: str, to_currency: str = "BRL") -> Optional[float]:
    """Busca cotação do dia. Cache em memória durante a execução."""
    if from_currency == to_currency:
        return 1.0

    cache_key = f"{from_currency}_{to_currency}"
    if cache_key in CURRENCY_CACHE:
        return CURRENCY_CACHE[cache_key]

    try:
        # API gratuita, sem chave. Atualiza 1x por dia
        url = f"https://api.exchangerate.host/convert?from={from_currency}&to={to_currency}&amount=1"
        req = urllib.request.Request(url, headers={"User-Agent": "DuffelMonitor/v20.5"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            rate = data.get("result")
            if rate:
                CURRENCY_CACHE[cache_key] = float(rate)
                logger.info(f"CURRENCY_RATE from={from_currency} to={to_currency} rate={rate:.4f}")
                return float(rate)
    except Exception as e:
        logger.error(f"CURRENCY_ERR from={from_currency} to={to_currency} exc={type(e).__name__}")

    return None

def convert_currency(amount: float, from_currency: str) -> Tuple[str, float]:
    """Converte pra BRL e retorna string formatada + valor float"""
    if from_currency == "BRL":
        return f"R$ {amount:.2f}", amount

    rate = get_exchange_rate(from_currency, "BRL")
    if not rate:
        # Se falhar cotação, mostra original
        return f"{from_currency} {amount:.2f}", amount

    brl_amount = amount * rate
    return f"R$ {brl_amount:.2f} ({from_currency} {amount:.2f})", brl_amount

# ============================================
# CACHE
# ============================================

class DuffelCache:
    @staticmethod
    def get_cache_key(endpoint: str, params: Dict, version: str) -> str:
        key_str = f"{version}:{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    @staticmethod
    def get(endpoint: str, params: Dict, version: str) -> Optional[Dict]:
        cache_key = DuffelCache.get_cache_key(endpoint, params, version)
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
    def set(endpoint: str, params: Dict, version: str, data: Dict) -> None:
        cache_key = DuffelCache.get_cache_key(endpoint, params, version)
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
        self.working_version = None

    def _try_version(self, version: str, endpoint: str, method: str, body: Optional[Dict]) -> Tuple[Optional[Dict], Optional[str]]:
        cache_key = {"endpoint": endpoint, "method": method, "body": body}
        cached_response = DuffelCache.get(endpoint, cache_key, version)
        if cached_response:
            logger.info(f"CACHE_HIT endpoint={endpoint} version={version}")
            return cached_response, None

        url = f"{DUFFEL_API_BASE}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Duffel-Version": version,
            "Content-Type": "application/json",
            "User-Agent": "DuffelMonitor/v20.5"
        }
        data = json.dumps(body).encode("utf-8") if body else None

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                DuffelCache.set(endpoint, cache_key, version, response_data)
                logger.info(f"API_OK method={method} endpoint={endpoint} status={response.status} version={version}")
                self.working_version = version
                return response_data, None

        except urllib.error.HTTPError as e:
            err_type = "unknown"
            err_title = ""
            err_detail = ""
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                err_obj = error_json.get('errors', [{}])[0]
                err_type = err_obj.get('type', 'unknown')
                err_title = err_obj.get('title', '')
                detail_raw = err_obj.get('detail', '')
                if detail_raw:
                    err_detail = detail_raw[:80].replace('req_', 'req_***').replace('orq_', 'orq_***')
            except Exception:
                pass
            logger.error(f"API_ERR method={method} endpoint={endpoint} status={e.code} type={err_type} title={err_title} detail={err_detail} version={version}")

            if err_title == "Unsupported version":
                return None, "unsupported_version"
            return None, f"{err_type}:{err_title}"

        except Exception as e:
            logger.error(f"API_EXC method={method} endpoint={endpoint} exc={type(e).__name__} version={version}")
            return None, "exception"

    def call_api(self, endpoint: str, method: str = "GET", body: Optional[Dict] = None,
                 retry_count: int = 0) -> Optional[Dict]:

        versions_to_try = [self.working_version] if self.working_version else DUFFEL_VERSIONS_TO_TRY

        for version in versions_to_try:
            if not version:
                continue
            response, err = self._try_version(version, endpoint, method, body)
            if response:
                return response
            if err == "unsupported_version":
                logger.warning(f"VERSION_SKIP version={version} reason=unsupported")
                continue
            else:
                break

        if retry_count < MAX_RETRIES:
            wait_time = RETRY_DELAY * (2 ** retry_count)
            logger.info(f"RETRY attempt={retry_count + 1}/{MAX_RETRIES} wait={wait_time}s")
            time.sleep(wait_time)
            return self.call_api(endpoint, method, body, retry_count + 1)

        return None

# ============================================
# BUSCA COM CONVERSÃO
# ============================================

def search_prices(client: DuffelClient) -> Tuple[Dict][Dict]:
    best_azul = {"price": float('inf'), "formatted": "N/A", "formatted_brl": "N/A", "date": "N/A", "airline": "Azul"}
    best_gol = {"price": float('inf'), "formatted": "N/A", "formatted_brl": "N/A", "date": "N/A", "airline": "GOL"}

    logger.info(f"SEARCH_START origin={ORIGIN} dest={DESTINATION} start={SEARCH_START_DAY} end={SEARCH_END_DAY} interval={INTERVAL_DAYS}")
    total_offers = 0
    zero_offers_requests = 0
    dates_checked = 0

    for i in range(SEARCH_START_DAY, SEARCH_END_DAY + 1, INTERVAL_DAYS):
        target_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        dates_checked += 1
        logger.info(f"SEARCH_DATE date={target_date} step={dates_checked}")

        search_body = {
            "data": {
                "slices": [{
                    "origin": ORIGIN,
                    "destination": DESTINATION,
                    "departure_date": target_date
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

                # Converte pra BRL aqui
                formatted_brl, brl_value = convert_currency(price_raw, currency)
                formatted_orig = f"{currency} {price_raw:.2f}"

                if is_azul and price_raw < best_azul["price"]:
                    best_azul = {
                        "price": price_raw,
                        "formatted": formatted_orig,
                        "formatted_brl": formatted_brl,
                        "date": target_date,
                        "airline": "Azul",
                        "brl_value": brl_value
                    }
                    logger.info(f"BEST_AZUL price={price_raw:.2f} {currency} brl={brl_value:.2f} date={target_date}")

                if is_gol and price_raw < best_gol["price"]:
                    best_gol = {
                        "price": price_raw,
                        "formatted": formatted_orig,
                        "formatted_brl": formatted_brl,
                        "date": target_date,
                        "airline": "GOL",
                        "brl_value": brl_value
                    }
                    logger.info(f"BEST_GOL price={price_raw:.2f} {currency} brl={brl_value:.2f} date={target_date}")
            except Exception:
                continue
        time.sleep(0.5)

    logger.info(f"SEARCH_END total_offers={total_offers} zero_offers_requests={zero_offers_requests} dates_checked={dates_checked} version_used={client.working_version}")
    if total_offers == 0:
        logger.error("SEARCH_FAIL reason=no_inventory_or_test_token")
    return best_azul, best_gol

# ============================================
# NOTIFICAÇÕES COM BRL
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
        <h2>✈️ MELHORES PREÇOS - DUFFEL EDITION (v20.5)</h2>
        <p><strong>Rota:</strong> {ORIGIN} → {DESTINATION}</p>
        <p><strong>Janela:</strong> D+{SEARCH_START_DAY} até D+{SEARCH_END_DAY}, a cada {INTERVAL_DAYS} dias</p><hr>
        <h3>🔵 AZUL</h3><p><strong>Preço:</strong> {azul['formatted_brl']}</p><strong>Data:</strong> {azul['date']}</p><hr>
        <h3>🟠 GOL</h3><p><strong>Preço:</strong> {gol['formatted_brl']}</p><p><strong>Data:</strong> {gol['date']}</p><hr>
        <p><small>Conversão via exchangerate.host em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</small></p>
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

        msg_text = f"""✈️ MELHORES PREÇOS - DUFFEL EDITION (v20.5)

🔵 AZUL: {azul['formatted_brl']}
📅 Data: {azul['date']}

🟠 GOL: {gol['formatted_brl']}
📅 Data: {gol['date']}

Rota: {ORIGIN} → {DESTINATION}
Janela: D+{SEARCH_START_DAY} a D+{SEARCH_END_DAY} / {INTERVAL_DAYS} em {INTERVAL_DAYS} dias
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
    logger.info("🚀 Script v20.5 - Duffel Edition SEGURA")
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

    msg_text = f"✈️ MELHORES PREÇOS - DUFFEL EDITION (v20.5):\n\n🔵 AZUL: {azul['formatted_brl']} (Data: {azul['date']})\n🟠 GOL: {gol['formatted_brl']} (Data: {gol['date']})\n\nRota: {ORIGIN} → {DESTINATION}\nJanela: D+{SEARCH_START_DAY} a D+{SEARCH_END_DAY} / {INTERVAL_DAYS}d\nVersão API usada: {client.working_version}\nGerado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    logger.info("\n" + msg_text)

    result = {"timestamp": datetime.now().isoformat(), "origin": ORIGIN, "destination": DESTINATION, "azul": azul, "gol": gol, "version": client.working_version}
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



