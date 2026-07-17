import requests
import os

# A chave do Asaas que você configurou nas variáveis de ambiente do Render
TOKEN_ASAAS = os.getenv("TOKEN_ASAAS")
URL_ASAAS = "https://api.asaas.com/api/v3"

def criar_checkout_asaas(pedido_id, valor_total, nome_cliente, detalhes_itens=None):
    headers = {
        "access_token": TOKEN_ASAAS,
        "Content-Type": "application/json"
    }
    
    # Criamos um Link de Pagamento avulso (O Asaas NÃO exige CPF aqui!)
    payload = {
        "name": f"Pedido #{pedido_id} - {nome_cliente}",
        "description": f"Pagamento do pedido #{pedido_id} no Art's Burguer",
        "value": float(valor_total),
        "billingType": "UNDEFINED", # Permite que o cliente escolha entre Pix ou Cartão
        "chargeType": "DETACHED",
        "dueDateLimitDays": 1
    }
    
    try:
        response = requests.post(f"{URL_ASAAS}/paymentLinks", headers=headers, json=payload)
        if response.status_code == 200:
            dados = response.json()
            return dados.get("url") # Retorna o link mágico para o cliente
        else:
            print(f"❌ Erro Asaas: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro na integração Asaas: {e}")
        return None
