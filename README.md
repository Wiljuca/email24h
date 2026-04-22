# ✈️ Alerta de Passagem CGB-OPS - Duffel Edition v20.10

Monitor automático de preços Cuiabá → Sinop usando API NDC da Duffel. 
Busca sem cookie, sem rastreamento de IP e sem manipulação de preço.

### Por que existe

Sites de companhias aéreas usam cookies e fingerprint pra subir preço a cada busca. 
Este script busca direto na Duffel via GitHub Actions: IP novo a cada execução, 
zero rastreabilidade. Você vê o `base_fare` real.

### Como funciona

1. **Busca**: Roda a cada 20min via GitHub Actions
2. **Janela**: D+1 até D+45, de 5 em 5 dias
3. **Companhias**: Azul e GOL via NDC Duffel
4. **Cotação**: Banco Central do Brasil PTAX + Banco Central Europeu. 100% automático
5. **Alerta**: Telegram + Email só quando acha preço menor
6. **Cache**: Evita bater API à toa. Respeita rate limit

### Stack

Python 3.11 | GitHub Actions | Duffel API v2 | urllib | smtplib

Zero dependência externa. Não precisa instalar nada.

### Como usar

1. **Fork** este repositório
2. **Adicione os Secrets** em `Settings > Secrets and variables > Actions`:
