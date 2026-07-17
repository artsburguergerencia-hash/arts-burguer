import requests
import os

# O .strip() garante que nenhum espaço em branco copiado sem querer quebre a sua chave
TOKEN_ASAAS = os.getenv("TOKEN_ASAAS", "").strip() 

# URL CORRETA DO ASAAS (sem o /api no meio)
URL_ASAAS = "https://api.asaas.com/v3"

# Adicionamos a forma_pagamento aqui
def criar_checkout_asaas(pedido_id, valor_total, nome_cliente, detalhes_itens=None, forma_pagamento="pix"):
    headers = {
        "access_token": TOKEN_ASAAS,
        "Content-Type": "application/json",
        "User-Agent": "ArtsBurguer/1.0"
    }
    
    # O sistema decide sozinho se é Cartão ou Pix
    tipo_cobranca = "CREDIT_CARD" if forma_pagamento == "credito" else "PIX"
    
    payload = {
        "name": f"Pedido #{pedido_id} - {nome_cliente}",
        "description": f"Pagamento do pedido #{pedido_id} no Art's Burguer",
        "value": float(valor_total),
        "billingType": tipo_cobranca, # Agora o bloqueio saiu, o sistema é livre!
        "chargeType": "DETACHED",
        "dueDateLimitDays": 1
    }
    
    try:
        response = requests.post(f"{URL_ASAAS}/paymentLinks", headers=headers, json=payload)
        if response.status_code == 200:
            return response.json().get("url")
        else:
            print(f"❌ Erro Asaas (Status {response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro de Conexão Asaas: {e}")
        return None
