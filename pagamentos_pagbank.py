import os
import requests

# === 1. A FUNÇÃO DO PIX (Que desapareceu) ===
def criar_pagamento_pix_mp(pedido_id, valor, nome, cpf):
    token = os.getenv("TOKEN_MERCADOPAGO")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    URL = "https://api.mercadopago.com/v1/payments"
    
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
        },
        "payment_methods": {
            "excluded_payment_types": [
                {"id": "ticket"} # A regra que bloqueia Boleto e Lotérica
            ]
        }
    }
