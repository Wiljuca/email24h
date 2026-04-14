#!/usr/bin/env python3
import smtplib
from email.message import EmailMessage # Recomendado para Python moderno
from datetime import datetime
import sys
from security_config import get_email_credentials

def main():
    # Captura e limpa as credenciais
    try:
        email, password = get_email_credentials()
    except RuntimeError as e:
        print(f'❌ ERROR: {e}')
        return 1
    
    # Usando EmailMessage (mais robusto que MIMEText)
    msg = EmailMessage()
    content = f'''
🛫 PASSAGENS CGB→OPS - {datetime.now().strftime("%d/%m %H:%M")}
🟠 GOL Ida R$847 | Volta R$792
🔵 AZUL Ida R$892 | Volta R$835
📧 Monitoramento GitHub Actions ativo!
'''
    msg.set_content(content)
    msg['Subject'] = f'✈️ Passagens Atualizadas {datetime.now().strftime("%d/%m %H:%M")}'
    msg['From'] = email
    msg['To'] = email
    
    print(f"--- Iniciando tentativa de envio para {email} ---")
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
            server.starttls()
            print("-> TLS iniciado")
            server.login(email, password)
            print("-> Login realizado com sucesso")
            server.send_message(msg)
            print(f'✅ Email enviado com sucesso às {datetime.now()}')
        return 0
    except smtplib.SMTPAuthenticationError:
        print("❌ ERRO DE AUTENTICAÇÃO: Verifique se a 'Senha de App' está correta.")
        return 1
    except Exception as e:
        print(f'❌ Erro inesperado no envio: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
