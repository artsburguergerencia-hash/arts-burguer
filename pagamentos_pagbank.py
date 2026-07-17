import requests
import os

TOKEN_PAGBANK = os.getenv("TOKEN_PAGBANK", "").strip()
# ATENÇÃO: Se for usar a conta real depois, mude a URL de 'sandbox.api' para apenas 'api'
URL_PAGBANK = "https://api.pagseguro.com/orders" 

def criar_pagamento_pix_pagbank(pedido_id, valor_total, nome_cliente, cpf_cliente):
    headers = {
        "Authorization": f"Bearer {TOKEN_PAGBANK}",
        "Content-Type": "application/json"
    }
    
    # Limpa o CPF (tira pontos e traços se vier do site)
    cpf_limpo = "".join(filter(str.isdigit, str(cpf_cliente)))
    valor_em_centavos = int(float(valor_total) * 100)
    
    payload = {
        "reference_id": f"PEDIDO_{pedido_id}",
        "customer": {
            "name": nome_cliente,
            "email": "cliente@artsburguer.com.br", # O nosso e-mail "fantasma" para não pedir ao cliente!
            "tax_id": cpf_limpo
        },
        "qr_codes": [
            {
                "amount": {
                    "value": valor_em_centavos
                }
            }
        ]
    }
    
    try:
        response = requests.post(URL_PAGBANK, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            dados = response.json()
            # Pega a lista de QRs gerados
            qr_codes = dados.get("qr_codes", [])
            if qr_codes:
                # Retorna apenas o texto do "Copia e Cola"
                return qr_codes[0].get("text")
                
        print(f"❌ Erro PagBank: {response.text}")
        return None
    except Exception as e:
        print(f"❌ Erro de Conexão PagBank: {e}")
        return None
