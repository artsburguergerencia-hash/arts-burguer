import requests
import os
import uuid # O Mercado Pago exige isso para não cobrar o cliente duas vezes por acidente

TOKEN_MP = os.getenv("TOKEN_MERCADOPAGO", "").strip()
URL_MP = "https://api.mercadopago.com/v1/payments"

def criar_link_pagamento_mp(pedido_id, valor_total, nome_cliente):
    token = os.getenv("TOKEN_MERCADOPAGO")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    URL_PREF = "https://api.mercadopago.com/checkout/preferences"
    
    # Armadura 1: Força exatamente 2 casas decimais (ex: 24.90)
    valor_arredondado = round(float(valor_total), 2)
    
    # Armadura 2: Evita nomes vazios que o banco possa rejeitar
    nome_seguro = str(nome_cliente) if nome_cliente else "Cliente Delivery"
    
    payload = {
        "items": [
            {
                "title": f"Pedido #{pedido_id} - Art's Burguer",
                "quantity": 1,
                "currency_id": "BRL", # Armadura 3: Confirma a moeda
                "unit_price": valor_arredondado
            }
        ],
        "external_reference": str(pedido_id),
        "payer": {
            "name": nome_seguro,
            "email": "cliente@artsburguer.com.br" # Armadura 4: E-mail garantido
        }
    }
    
    try:
        response = requests.post(URL_PREF, headers=headers, json=payload)
        
        # Isso força o Render a cuspir a resposta no painel na mesma hora!
        print(f"--- STATUS MERCADO PAGO: {response.status_code} ---", flush=True)
        print(f"--- DETALHE: {response.text} ---", flush=True)
        
        if response.status_code in [200, 201]:
            dados = response.json()
            return dados.get("init_point") 
            
        return None
    except Exception as e:
        print(f"--- ERRO DO SERVIDOR: {e} ---", flush=True)
        return None
