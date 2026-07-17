import requests
import os

# O .strip() garante que nenhum espaço em branco copiado sem querer quebre a sua chave
TOKEN_ASAAS = os.getenv("TOKEN_ASAAS", "").strip() 

# IMPORTANTE: Se a sua conta do Asaas for de testes (Sandbox), 
# troque a URL abaixo para: "https://sandbox.asaas.com/api/v3"
URL_ASAAS = "https://api.asaas.com/api/v3"

def criar_checkout_asaas(pedido_id, valor_total, nome_cliente, detalhes_itens=None):
    headers = {
        "access_token": TOKEN_ASAAS,
        "Content-Type": "application/json",
        "User-Agent": "ArtsBurguer/1.0" # Evita que o firewall do banco bloqueie a requisição
    }
    
    payload = {
        "name": f"Pedido #{pedido_id} - {nome_cliente}",
        "description": f"Pagamento do pedido #{pedido_id} no Art's Burguer",
        "value": float(valor_total),
        "billingType": "PIX", # Forçamos apenas PIX para ignorar a restrição de valor mínimo do cartão
        "chargeType": "DETACHED",
        "dueDateLimitDays": 1
    }
    
    try:
        response = requests.post(f"{URL_ASAAS}/paymentLinks", headers=headers, json=payload)
        if response.status_code == 200:
            dados = response.json()
            return dados.get("url")
        else:
            # Agora o log vai nos mostrar o número do erro e o texto exato da recusa!
            print(f"❌ Erro Asaas (Status {response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro de Conexão Asaas: {e}")
        return None
