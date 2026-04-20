#!/usr/bin/env python3

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
import hashlib

# ============================================
# CONFIGURAÇÃO DE LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/duffel_monitor.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# CONSTANTES
# ============================================

DUFFEL_API_BASE = "https://api.duffel.com/air"
DUFFEL_VERSION = "2021-10-25"  # ✅ Versão correta
ORIGIN = "CGB"
DESTINATION = "OPS"
SEARCH_DAYS = 45
INTERVAL_DAYS = 5
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos
CACHE_DIR = Path("/tmp/duffel_cache" )
CACHE_EXPIRY = 3600  # 1 hora em segundos

# Criar diretório de cache
CACHE_DIR.mkdir(exist_ok=True)

# ============================================
# CLASSE DE CACHE
# ============================================

class DuffelCache:
    """Gerencia cache de requisições à API Duffel."""
    
    @staticmethod
    def get_cache_key(endpoint: str, params: Dict) -> str:
        """Gera chave de cache baseada em endpoint e parâmetros."""
        key_str = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    @staticmethod
    def get(endpoint: str, params: Dict) -> Optional[Dict]:
        """Recupera dados do cache se ainda forem válidos."""
        cache_key = DuffelCache.get_cache_key(endpoint, params)
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        # Verificar se cache expirou
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age > CACHE_EXPIRY:
            cache_file.unlink()
            return None
        
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao ler cache: {e}")
            return None
    
    @staticmethod
    def set(endpoint: str, params: Dict, data: Dict) -> None:
        """Armazena dados no cache."""
        cache_key = DuffelCache.get_cache_key(endpoint, params)
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Erro ao salvar cache: {e}")

# ============================================
# CLASSE DE REQUISIÇÕES COM RETRY
# ============================================

class DuffelClient:
    """Cliente otimizado para API Duffel com retry automático."""
    
    def __init__(self, token: str):
        self.token = token
        self.session_retries = 0
    
    def _get_token(self) -> Optional[str]:
        """Obtém token da variável de ambiente."""
        token = os.getenv("DUFFEL_ACCESS_TOKEN")
        if not token:
            logger.error("❌ DUFFEL_ACCESS_TOKEN não encontrado nas variáveis de ambiente")
            return None
        return token
    
    def call_api(self, endpoint: str, method: str = "GET", body: Optional[Dict] = None, 
                 retry_count: int = 0) -> Optional[Dict]:
        """Faz chamada à API com retry automático."""
        
        # Verificar cache primeiro
        cache_key = {"endpoint": endpoint, "method": method, "body": body}
        cached_response = DuffelCache.get(endpoint, cache_key)
        if cached_response:
            logger.info(f"✅ Cache hit para {endpoint}")
            return cached_response
        
        url = f"{DUFFEL_API_BASE}/{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Duffel-Version": DUFFEL_VERSION,
            "Content-Type": "application/json",
            "User-Agent": "DuffelMonitor/v18"
        }
        
        data = json.dumps(body).encode("utf-8") if body else None
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                
                # Armazenar no cache
                DuffelCache.set(endpoint, cache_key, response_data)
                
                logger.info(f"✅ Requisição bem-sucedida: {endpoint}")
                return response_data
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            error_json = json.loads(error_body)
            
            logger.error(f"❌ Erro HTTP {e.code}: {error_json.get('errors', [{}])[0].get('message', 'Desconhecido')}")
            
            # Retry para erros temporários (5xx, 429)
            if e.code >= 500 or e.code == 429:
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)  # Backoff exponencial
                    logger.info(f"🔄 Tentando novamente em {wait_time}s (tentativa {retry_count + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    return self.call_api(endpoint, method, body, retry_count + 1)
            
            return None
        
        except urllib.error.URLError as e:
            logger.error(f"❌ Erro de conexão: {e.reason}")
            
            if retry_count < MAX_RETRIES:
                wait_time = RETRY_DELAY * (2 ** retry_count)
                logger.info(f"🔄 Tentando novamente em {wait_time}s (tentativa {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.call_api(endpoint, method, body, retry_count + 1)
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {e}")
            return None

# ============================================
# FUNÇÕES DE BUSCA
# ============================================

def search_prices(client: DuffelClient) -> Tuple[Dict, Dict]:
    """Busca os melhores preços da Azul e GOL nos próximos 45 dias."""
    
    best_azul = {"price": float('inf'), "formatted": "N/A", "date": "N/A", "airline": "Azul"}
    best_gol = {"price": float('inf'), "formatted": "N/A", "date": "N/A", "airline": "GOL"}
    
    logger.info(f"🚀 Iniciando busca: {ORIGIN} → {DESTINATION}")
    logger.info(f"📅 Período: próximos {SEARCH_DAYS} dias em intervalos de {INTERVAL_DAYS} dias")
    
    total_offers = 0
    
    # Consultar em intervalos de 5 dias
    for i in range(1, SEARCH_DAYS + 1, INTERVAL_DAYS):
        target_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        logger.info(f"🔍 Consultando data: {target_date}...")
        
        search_body = {
            "data": {
                "slices": [
                    {
                        "origin": ORIGIN,
                        "destination": DESTINATION,
                        "departure_date": target_date
                    }
                ],
                "passengers": [{"type": "adult"}],
                "cabin_class": "economy"
            }
        }
        
        response = client.call_api("offer_requests", method="POST", body=search_body)
        
        if not response or "data" not in response:
            logger.warning(f"⚠️ Sem resposta para {target_date}")
            continue
        
        offers = response["data"].get("offers", [])
        logger.info(f"✅ {len(offers)} ofertas encontradas para {target_date}")
        total_offers += len(offers)
        
        for offer in offers:
            try:
                price_raw = float(offer.get("total_amount", float('inf')))
                currency = offer.get("total_currency", "BRL")
                
                owner = offer.get("owner", {})
                name = owner.get("name", "").upper()
                code = owner.get("iata_code", "").upper()
                
                # Filtro Azul (AD) e GOL (G3)
                is_azul = "AZUL" in name or code == "AD"
                is_gol = "GOL" in name or code == "G3"
                
                if is_azul and price_raw < best_azul["price"]:
                    best_azul = {
                        "price": price_raw,
                        "formatted": f"{currency} {price_raw:.2f}",
                        "date": target_date,
                        "airline": "Azul",
                        "code": code
                    }
                    logger.debug(f"🔵 Novo melhor preço Azul: {best_azul['formatted']} em {target_date}")
                
                if is_gol and price_raw < best_gol["price"]:
                    best_gol = {
                        "price": price_raw,
                        "formatted": f"{currency} {price_raw:.2f}",
                        "date": target_date,
                        "airline": "GOL",
                        "code": code
                    }
                    logger.debug(f"🟠 Novo melhor preço GOL: {best_gol['formatted']} em {target_date}")
            
            except Exception as e:
                logger.warning(f"⚠️ Erro ao processar oferta: {e}")
                continue
        
        # Pequeno delay entre requisições
        time.sleep(0.5)
    
    logger.info(f"📊 Total de ofertas processadas: {total_offers}")
    return best_azul, best_gol

# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def main():
    """Função principal do script."""
    
    logger.info("=" * 60)
    logger.info("🚀 Script v18 - Duffel Edition (Otimizado)")
    logger.info("=" * 60)
    
    # Obter token
    token = os.getenv("DUFFEL_ACCESS_TOKEN")
    if not token:
        logger.error("❌ DUFFEL_ACCESS_TOKEN não configurado")
        sys.exit(1)
    
    # Criar cliente
    client = DuffelClient(token)
    
    # Buscar preços
    try:
        azul, gol = search_prices(client)
    except Exception as e:
        logger.error(f"❌ Erro durante busca: {e}")
        sys.exit(1)
    
    # Preparar mensagem
    msg_text = "✈️ MELHORES PREÇOS - DUFFEL EDITION (v18 Otimizado):\n\n"
    msg_text += f"🔵 AZUL: {azul['formatted']} (Data: {azul['date']})\n"
    msg_text += f"🟠 GOL: {gol['formatted']} (Data: {gol['date']})\n\n"
    msg_text += f"Rota: {ORIGIN} → {DESTINATION}\n"
    msg_text += f"Status: ✅ Monitoramento concluído via Duffel API\n"
    msg_text += f"Versão: {DUFFEL_VERSION}\n"
    msg_text += f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    
    logger.info("\n" + msg_text)
    
    # Salvar resultado em JSON
    result = {
        "timestamp": datetime.now().isoformat(),
        "origin": ORIGIN,
        "destination": DESTINATION,
        "azul": azul,
        "gol": gol
    }
    
    result_file = Path("/tmp/duffel_result.json")
    try:
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"✅ Resultado salvo em {result_file}")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar resultado: {e}")
    
    logger.info("=" * 60)
    logger.info("✅ Script finalizado com sucesso!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()







