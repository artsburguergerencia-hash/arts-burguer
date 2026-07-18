import os
import requests

# === 1. A FUNÇÃO DO PIX (Que desapareceu) ===
def criar_pagamento_pix_mp(pedido_id, valor, nome, cpf):
    token = os.getenv("TOKEN_MERCADOPAGO")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    URL = "https://api.mercadopago.com/v1/payments"
    
    payload = {
        "transaction_amount": float(valor),
        "description": f"Pedido #{pedido_id} - Art's Burguer",
        "payment_method_id": "pix",
        "payer": {
            "email": "cliente@artsburguer.com.br",
            "first_name": nome,
            "identification": {"type": "CPF", "number": cpf}
        }
    }
    try:
        resp = requests.post(URL, headers=headers, json=payload)
        if resp.status_code in [200, 201]:
            return resp.json()["point_of_interaction"]["transaction_data"]["qr_code"]
        return None
    except:
        return None


# === 2. A FUNÇÃO DO CARTÃO (Blindada pela Eli) ===
def criar_link_pagamento_mp(pedido_id, valor_total, nome_cliente):
    token = os.getenv("TOKEN_MERCADOPAGO")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    URL_PREF = "https://api.mercadopago.com/checkout/preferences"
    
    valor_arredondado = round(float(valor_total), 2)
    nome_seguro = str(nome_cliente) if nome_cliente else "Cliente Delivery"
    
    payload = {
        "items": [
            {
                "title": f"Pedido #{pedido_id} - Art's Burguer",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": valor_arredondado
            }
        ],
        "external_reference": str(pedido_id),
        "payer": {
            "name": nome_seguro,
            "email": "cliente@artsburguer.com.br" 
        }
    }
    
    try:
        response = requests.post(URL_PREF, headers=headers, json=payload)
        print(f"--- STATUS MERCADO PAGO: {response.status_code} ---", flush=True)
        print(f"--- DETALHE: {response.text} ---", flush=True)
        
        if response.status_code in [200, 201]:
            return response.json().get("init_point") 
            
        return None
    except Exception as e:
        print(f"--- ERRO DO SERVIDOR: {e} ---", flush=True)
        return None
