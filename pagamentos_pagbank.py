import os
import requests

# === 1. A FUNÇÃO DO PIX (A original e correta) ===
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


# === 2. A FUNÇÃO DO CARTÃO / LINK (Limpa e sem a regra inútil do boleto) ===
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
        
        if response.status_code in [200, 201]:
            return response.json().get("init_point") 
            
        return None
    except Exception as e:
        print(f"--- ERRO DO SERVIDOR: {e} ---", flush=True)
        return None


# === 3. A NOVA FUNÇÃO DO CHECKOUT TRANSPARENTE (Cartão direto no site) ===
def criar_pagamento_cartao_mp(pedido_id, valor_total, token_cartao, email_cliente, payment_method_id, parcelas, cpf_cliente):
    token_mp = os.getenv("TOKEN_MERCADOPAGO")
    headers = {
        "Authorization": f"Bearer {token_mp}", 
        "Content-Type": "application/json"
    }
    URL = "https://api.mercadopago.com/v1/payments"
    
    payload = {
        "transaction_amount": round(float(valor_total), 2),
        "token": token_cartao,
        "description": f"Pedido #{pedido_id} - Art's Burguer",
        "installments": int(parcelas),
        "payment_method_id": payment_method_id,
        "payer": {
            "email": email_cliente if email_cliente else "cliente@artsburguer.com.br",
            "identification": {
                "type": "CPF",
                "number": cpf_cliente
            }
        }
    }
    
    try:
        response = requests.post(URL, headers=headers, json=payload)
        print(f"--- STATUS PAGAMENTO TRANSPARENTE: {response.status_code} ---", flush=True)
        
        # Retorna a resposta completa do banco para o nosso site saber se aprovou
        return response.json() 
    except Exception as e:
        print(f"--- ERRO PAGAMENTO TRANSPARENTE: {e} ---", flush=True)
        return None
