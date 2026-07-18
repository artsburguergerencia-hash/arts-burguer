import requests
import os
import uuid # O Mercado Pago exige isso para não cobrar o cliente duas vezes por acidente

TOKEN_MP = os.getenv("TOKEN_MERCADOPAGO", "").strip()
URL_MP = "https://api.mercadopago.com/v1/payments"

def criar_pagamento_pix_mp(pedido_id, valor_total, nome_cliente, cpf_cliente):
    headers = {
        "Authorization": f"Bearer {TOKEN_MP}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4()) # Chave de segurança única para cada tentativa
    }
    
    # Limpa o CPF (tira pontos e traços)
    cpf_limpo = "".join(filter(str.isdigit, str(cpf_cliente)))
    
    payload = {
        "transaction_amount": float(valor_total),
        "description": f"Pedido #{pedido_id} - Art's Burguer",
        "payment_method_id": "pix",
        "payer": {
            "email": "cliente@artsburguer.com.br", # E-mail fantasma para o cliente não precisar digitar
            "first_name": nome_cliente,
            "identification": {
                "type": "CPF",
                "number": cpf_limpo
            }
        }
    }
    
    try:
        response = requests.post(URL_MP, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            dados = response.json()
            # O Mercado Pago esconde o "Copia e Cola" dentro de várias pastas, aqui nós pescamos ele:
            copia_e_cola = dados.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code")
            return copia_e_cola
            
        print(f"❌ Erro Mercado Pago (Status {response.status_code}): {response.text}")
        return None
    except Exception as e:
        print(f"❌ Erro de Conexão Mercado Pago: {e}")
        return None

def criar_link_pagamento_mp(pedido_id, valor_total, nome_cliente):
    headers = {
        "Authorization": f"Bearer {TOKEN_MP}",
        "Content-Type": "application/json"
    }
    
    # Rota de 'Preferences' (Checkout Pro) do Mercado Pago
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
            # Retorna a URL do link de pagamento para redirecionar o cliente
            return dados.get("init_point") 
            
        print(f"❌ Erro MP Cartão: {response.text}")
        return None
    except Exception as e:
        print(f"❌ Erro Conexão MP Cartão: {e}")
        return None
