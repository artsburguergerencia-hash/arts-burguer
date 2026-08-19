import os
import requests
import uuid # <-- A biblioteca que vai gerar a chave anti-duplicidade exigida pelo MP!

# 🚨 COLOQUE SEU ACCESS TOKEN REAL AQUI DENTRO DAS ASPAS 🚨
MEU_TOKEN_MP = "APP_USR-3588115293297057-071715-f7c8a8cfe1c50ab78d398101182a723f-3548282389"

def get_token():
    """Tenta pegar do servidor. Se falhar, usa a chave fixa acima."""
    token_env = os.getenv("TOKEN_MERCADOPAGO")
    return token_env if token_env else MEU_TOKEN_MP


# === 1. A FUNÇÃO DO PIX ===
def criar_pagamento_pix_mp(pedido_id, valor, nome, cpf):
    token = get_token()
    if not token or token == "APP_USR-COLE-SEU-TOKEN-AQUI":
        return {"erro": "Token do Mercado Pago não encontrado no servidor."}

    # A MÁGICA ESTÁ AQUI: Adicionando o X-Idempotency-Key
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }
    
    URL = "https://api.mercadopago.com/v1/payments"
    email_dinamico = f"cliente{pedido_id}@artsburguer.com.br"

    payload = {
        "transaction_amount": float(valor),
        "description": f"Pedido #{pedido_id} - Art's Burguer",
        "payment_method_id": "pix",
        "payer": {
            "email": email_dinamico,
            "first_name": str(nome),
            "identification": {"type": "CPF", "number": str(cpf)}
        }
    }

    try:
        resp = requests.post(URL, headers=headers, json=payload)
        dados = resp.json()

        if resp.status_code in [200, 201]:
            print(f"✅ PIX GERADO COM SUCESSO! Pedido #{pedido_id}", flush=True)
            return {"qr_code": dados["point_of_interaction"]["transaction_data"]["qr_code"]}
        else:
            msg = dados.get("message", str(dados))
            if "invalid" in msg.lower() and "identification" in msg.lower():
                msg = "O CPF informado é inválido (não passou na validação da Receita)."
            print(f"❌ O MERCADO PAGO RECUSOU O PIX! Motivo: {msg}", flush=True)
            return {"erro": msg}
    except Exception as e:
        print(f"❌ ERRO DO SERVIDOR AO CHAMAR O MP: {e}", flush=True)
        return {"erro": f"Falha interna do servidor: {e}"}


# === 2. A FUNÇÃO DO LINK DE PAGAMENTO (Se você ainda usar) ===
def criar_link_pagamento_mp(pedido_id, valor_total, nome_cliente):
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
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
        if response.status_code in [200, 201]:
            return response.json().get("init_point") 
        return None
    except Exception as e:
        return None


# === 3. A FUNÇÃO DO CHECKOUT TRANSPARENTE (Cartão direto no site) ===
def criar_pagamento_cartao_mp(pedido_id, valor_total, token_cartao, email_cliente, payment_method_id, parcelas, cpf_cliente):
    token_mp = get_token()
    
    # A MÁGICA ESTÁ AQUI TAMBÉM: Protegendo o pagamento de cartão
    headers = {
        "Authorization": f"Bearer {token_mp}", 
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
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
                "number": str(cpf_cliente)
            }
        }
    }
    
    try:
        response = requests.post(URL, headers=headers, json=payload)
        print(f"--- STATUS PAGAMENTO TRANSPARENTE: {response.status_code} ---", flush=True)
        return response.json() 
    except Exception as e:
        print(f"--- ERRO PAGAMENTO TRANSPARENTE: {e} ---", flush=True)
        return None
