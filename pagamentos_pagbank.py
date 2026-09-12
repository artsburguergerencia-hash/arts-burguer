# pagamentos_pagbank.py
import os
import requests
import uuid

def get_token():
    """Lê o token do Mercado Pago exclusivamente das variáveis de ambiente."""
    token = os.getenv("TOKEN_MERCADOPAGO")
    if not token or "COLE-SEU-TOKEN" in token:
        print("⚠️ [Mercado Pago] AVISO CRÍTICO: TOKEN_MERCADOPAGO não foi configurado no ambiente!", flush=True)
        return None
    return token.strip()


# === 1. A FUNÇÃO DO PIX (COM CHAVE DE IDEMPOTÊNCIA ANTI-DUPLICIDADE) ===
def criar_pagamento_pix_mp(pedido_id, valor, nome, cpf):
    token = get_token()
    if not token:
        return {"erro": "Token do Mercado Pago não configurado no servidor. Configure a variável TOKEN_MERCADOPAGO."}

    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }
    
    URL = "https://api.mercadopago.com/v1/payments"
    email_dinamico = f"cliente{pedido_id}@artsburguer.com.br"
    cpf_limpo = str(cpf).replace(".", "").replace("-", "").strip()

    payload = {
        "transaction_amount": float(valor),
        "description": f"Pedido #{pedido_id} - Art's Burguer",
        "payment_method_id": "pix",
        "payer": {
            "email": email_dinamico,
            "first_name": str(nome),
            "identification": {"type": "CPF", "number": cpf_limpo}
        }
    }

    try:
        resp = requests.post(URL, headers=headers, json=payload, timeout=10)
        dados = resp.json()

        if resp.status_code in [200, 201]:
            print(f"✅ PIX GERADO COM SUCESSO! Pedido #{pedido_id}", flush=True)
            return {"qr_code": dados["point_of_interaction"]["transaction_data"]["qr_code"]}
        else:
            msg = dados.get("message", str(dados))
            if "invalid" in msg.lower() and "identification" in msg.lower():
                msg = "O CPF informado é inválido perante a validação da Receita/Mercado Pago."
            print(f"❌ O MERCADO PAGO RECUSOU O PIX! Motivo: {msg}", flush=True)
            return {"erro": msg}
    except Exception as e:
        print(f"❌ ERRO DO SERVIDOR AO CHAMAR O MERCADO PAGO: {e}", flush=True)
        return {"erro": f"Falha de conexão com o Mercado Pago: {e}"}


# === 2. A FUNÇÃO DO LINK DE PAGAMENTO (CHECKOUT PRO / REDIRECT) ===
def criar_link_pagamento_mp(pedido_id, valor_total, nome_cliente):
    token = get_token()
    if not token:
        return None

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
        response = requests.post(URL_PREF, headers=headers, json=payload, timeout=10)
        if response.status_code in [200, 201]:
            return response.json().get("init_point") 
        return None
    except Exception as e:
        print(f"❌ ERRO AO CRIAR PREFERÊNCIA MP: {e}", flush=True)
        return None


# === 3. A FUNÇÃO DO CHECKOUT TRANSPARENTE (CARTÃO DIRETO NO SITE) ===
def criar_pagamento_cartao_mp(pedido_id, valor_total, token_cartao, email_cliente, payment_method_id, parcelas, cpf_cliente):
    token = get_token()
    if not token:
        return None
    
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }
    URL = "https://api.mercadopago.com/v1/payments"
    cpf_limpo = str(cpf_cliente).replace(".", "").replace("-", "").strip()
    
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
                "number": cpf_limpo
            }
        }
    }
    
    try:
        response = requests.post(URL, headers=headers, json=payload, timeout=12)
        print(f"--- STATUS PAGAMENTO TRANSPARENTE: {response.status_code} ---", flush=True)
        return response.json() 
    except Exception as e:
        print(f"--- ERRO PAGAMENTO TRANSPARENTE: {e} ---", flush=True)
        return None
