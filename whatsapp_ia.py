import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Vai buscar os dados corretos ao .env que acabámos de arranjar
WA_API_URL = os.getenv("WA_API_URL")
WA_TOKEN = os.getenv("WA_TOKEN")

def enviar_mensagem_whatsapp(telefone: str, mensagem: str):
    # DEFINIÇÃO FORÇADA PARA EVITAR O CACHE DO DOCKER
    WA_API_URL = "http://192.168.3.67:8083/message/sendText/Baileys"
    WA_TOKEN = "5EE027BB2D93-4E25-907C-D45EC31F03F1"
    
    print(f"\n--- 🚀 TENTANDO ENVIAR PARA: {telefone} EM {WA_API_URL} ---", flush=True)
    # ... resto do seu código permanece igual ...
    
    if not telefone or telefone == "BALCAO": 
        return False
        
    telefone_limpo = ''.join(filter(str.isdigit, telefone))
    if not telefone_limpo.startswith("55") and len(telefone_limpo) <= 11:
        telefone_limpo = f"55{telefone_limpo}"
        
    # ESTRUTURA EXATA EXIGIDA PELA EVOLUTION API
    payload = {
        "number": telefone_limpo,
        "text": mensagem,
        "delay": 1200
    }
    headers = {"apikey": WA_TOKEN, "Content-Type": "application/json"}
    
    try:
        response = requests.post(WA_API_URL, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            print(f"✅ SUCESSO! Notificação enviada para {telefone_limpo}\n", flush=True)
            return True
        else:
            print(f"❌ FALHA API: {response.status_code} - {response.text}\n", flush=True)
            return False
    except Exception as e:
        print(f"❌ ERRO DE REDE: {e}\n", flush=True)
        return False

def notificar_status_pedido(telefone: str, nome: str, pedido_id: int, status: str):
    mensagens = {
        "RECEBIDO": f"Olá {nome}! 🍔 Acabámos de receber o seu pedido #{pedido_id} pelo Cardápio Online. Estamos a analisar os detalhes!",
        "EM_PREPARO": f"Oba, {nome}! O seu pedido #{pedido_id} já foi confirmado e acabou de ir para a chapa! 🔥",
        "PRONTO": f"Atenção, {nome}! O seu pedido #{pedido_id} já está pronto e embalado! 📦",
        "SAIU_PARA_ENTREGA": f"Aí vai o seu lanche, {nome}! 🏍️💨 O nosso motoboy está a caminho, fique atento à porta!",
        "ENTREGUE": f"{nome}, o pedido #{pedido_id} foi entregue! Muito obrigado por escolher o Art's Burguer! ⭐",
        "CANCELADO": f"Poxa, {nome}. O seu pedido #{pedido_id} foi cancelado. Se houve algum problema com o pagamento, tente fazer um novo pedido!"
    }
    
    msg = mensagens.get(status.upper())
    if msg:
        enviar_mensagem_whatsapp(telefone, msg)