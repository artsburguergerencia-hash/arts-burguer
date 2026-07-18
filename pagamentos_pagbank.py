import requests
import os
import uuid # O Mercado Pago exige isso para não cobrar o cliente duas vezes por acidente

TOKEN_MP = os.getenv("TOKEN_MERCADOPAGO", "").strip()
URL_MP = "https://api.mercadopago.com/v1/payments"

def criar_link_pagamento_mp(pedido_id, valor_total, nome_cliente):
    # Puxa o token exato que está salvo lá no Render
    token = os.getenv("TOKEN_MERCADOPAGO")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    URL_PREF = "https://api.mercadopago.com/checkout/preferences"
    
    payload = {
        "items": [
            {
                "title": f"Pedido #{pedido_id} - Art's Burguer",
                "quantity": 1,
                "unit_price": float(valor_total)
            }
        ],
        "external_reference": str(pedido_id),
        "payer": {
            "name": nome_cliente
        }
    }
    
    try:
        response = requests.post(URL_PREF, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            dados = response.json()
            return dados.get("init_point") 
            
        print(f"❌ Erro MP Cartão: {response.text}")
        return None
    except Exception as e:
        print(f"❌ Erro Conexão MP Cartão: {e}")
        return None
