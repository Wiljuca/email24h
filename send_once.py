#!/usr/bin/env python3
import os
import urllib.request
import json
from security_config import get_required_secret

def test_api_connection():
    rapidapi_key = get_required_secret("RAPIDAPI_KEY")
    print(f"--- TESTE DE CONEXÃO RAPIDAPI ---")
    
    # Testamos um endpoint simples de busca de aeroporto (CGB)
    url = "https://skyscanner-flights-travel-api.p.rapidapi.com/flights/searchAirport?query=CGB"
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "skyscanner-flights-travel-api.p.rapidapi.com"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers )
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.getcode()
            content = json.loads(response.read().decode("utf-8"))
            print(f"✅ SUCESSO! Status: {status}")
            print(f"Dados recebidos: {content.get('data', [{}])[0].get('presentation', {}).get('title', 'N/A')}")
            return True
    except Exception as e:
        print(f"❌ ERRO NA CONEXÃO: {e}")
        if hasattr(e, 'code'):
            print(f"Código do Erro HTTP: {e.code}")
            if e.code == 401:
                print("Motivo: Chave Inválida ou Não Autorizada. Verifique o Secret no GitHub.")
            elif e.code == 403:
                print("Motivo: Você não assinou o plano Basic desta API específica.")
        return False

if __name__ == "__main__":
    test_api_connection()








