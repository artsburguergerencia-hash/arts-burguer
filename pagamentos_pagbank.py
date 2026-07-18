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
        "items": [
            {
                "title": f"Pedido #{pedido_id} - Art's Burguer",
                "quantity": 1,
                "unit_price": float(valor_total)
            }
        ],
        "external_reference": str(pedido_id),
        "payer": {
            "name": nome_cliente,
            "email": "cliente@artsburguer.com.br"
        }
    }
