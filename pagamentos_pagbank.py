import requests
import json

# ==========================================
# CONFIGURAÇÕES PAGBANK (Ambiente Seguro)
# ==========================================
# Quando for para a loja real, trocará este token pelo seu Token de Produção
TOKEN_PAGBANK = "SEU_TOKEN_DE_TESTE_AQUI" 
URL_PAGBANK = "https://sandbox.api.pagseguro.com/checkouts" # Sandbox = Ambiente de Teste

def criar_checkout_pagbank(pedido_id, valor_total, nome_cliente, itens_carrinho):
    headers = {
        "Authorization": f"Bearer {TOKEN_PAGBANK}",
        "Content-Type": "application/json"
    }
    valor_em_centavos = int(valor_total * 100)
    
    # Mapeia os itens do carrinho para o formato do PagBank
    lista_itens = []
    for item in itens_carrinho:
        lista_itens.append({
            "name": item["nome"] if "nome" in item else "Produto",
            "quantity": item["quantidade"],
            "unit_amount": int(item["preco"] * 100)
        })
    
    payload = {
        "reference_id": str(pedido_id),
        "customer": {
            "name": nome_cliente,
            "email": "cliente@artsburguer.com.br"
        },
        "items": lista_itens, # Agora envia os itens reais
        "payment_methods": [
            {"type": "CREDIT_CARD"},
            {"type": "PIX"}
        ],
        "redirect_url": f"http://seu-dominio-aqui.com.br/pedido-sucesso?id={pedido_id}"
    }
    
    try:
        response = requests.post(URL_PAGBANK, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            dados = response.json()
            for link in dados.get("links", []):
                if link.get("rel") == "PAY": return link.get("href")
        return None
    except Exception as e:
        print(f"❌ Erro PagBank: {e}")
        return None

def gerar_pagamento_pix(valor, pedido_id, nome_cliente):
    # Função mantida por segurança para garantir que rotas antigas não quebram
    return {"qr_code": "00020126580014br.gov.bcb.pix...", "copia_e_cola": "PIX_COPIA_E_COLA_AQUI"}