import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Buscando as credenciais do .env (O jeito seguro!)
WA_API_URL = os.getenv("WA_API_URL")
WA_TOKEN = os.getenv("WA_TOKEN")

def enviar_mensagem_whatsapp(telefone: str, mensagem: str):
    # Fallback: Se não achar no .env, tenta usar a string fixa (Atenção ao ngrok!)
    api_url = WA_API_URL or "https://coziness-unable-letter.ngrok-free.dev/message/sendText/Baileys"
    api_token = WA_TOKEN or "5EE027BB2D93-4E25-907C-D45EC31F03F1"
    
    print(f"\n--- 🚀 TENTANDO ENVIAR PARA: {telefone} EM {api_url} ---", flush=True)
    
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
    headers = {"apikey": api_token, "Content-Type": "application/json"}
    
    try:
        response = requests.post(api_url, json=payload, headers=headers)
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
    # Textos ajustados para um tom mais natural, vibrante e brasileiro
    mensagens = {
        "RECEBIDO": f"Olá, {nome}! 🍔 Acabamos de receber o seu pedido #{pedido_id}. Já estamos conferindo os detalhes para enviar para a cozinha!",
        "EM_PREPARO": f"Aí sim, {nome}! O seu pedido #{pedido_id} acabou de ir para a chapa. Daqui a pouco ele está pronto! 🔥👨‍🍳",
        "PRONTO": f"Tudo pronto, {nome}! O seu pedido #{pedido_id} já está embalado e quentinho aguardando! 📦✨",
        "SAIU_PARA_ENTREGA": f"Lanche na pista, {nome}! 🏍️💨 O nosso motoboy acabou de sair com o seu pedido #{pedido_id}. Fique atento ao portão!",
        "ENTREGUE": f"Pedido entregue! 🎉 Muito obrigado por escolher o Art's Burguer, {nome}. Bom apetite e até a próxima! ⭐",
        "CANCELADO": f"Poxa, {nome}... O seu pedido #{pedido_id} foi cancelado. Se houve algum problema, mande uma mensagem pra gente tentar ajudar!"
    }
    
    msg = mensagens.get(status.upper())
    if msg:
        enviar_mensagem_whatsapp(telefone, msg)

def responder_com_ia(mensagem_cliente: str, telefone: str):
    """
    Cérebro da IA para responder os clientes que mandam mensagem no WhatsApp.
    Você pode no futuro plugar a API da OpenAI (ChatGPT) aqui!
    """
    texto = str(mensagem_cliente).lower()
    resposta = ""
    
    # Árvore de decisão inteligente do Chatbot
    if "cardapio" in texto or "menu" in texto or "pedir" in texto or "fome" in texto:
        resposta = "Olá! Nosso cardápio é 100% digital e super rápido. Faça seu pedido por aqui: https://artsburguer.com.br 🍔🍟"
    
    elif "horario" in texto or "aberto" in texto or "funcionamento" in texto:
        resposta = "Nossas chapas esquentam de Terça a Domingo, das 18h às 23h59! 🕒🔥"
    
    elif "humano" in texto or "atendente" in texto or "problema" in texto or "errado" in texto:
        resposta = "Entendi! Vou chamar um humano da nossa equipe para falar com você. Só um instante! 👨‍💻"
    
    else:
        resposta = "Oi! Sou a assistente virtual do Art's Burguer 🤖🍔. Para fazer um pedido, acesse nosso link: https://artsburguer.com.br. Posso ajudar com mais alguma dúvida?"
        
    print(f"🤖 [IA RESPONDENDO O NÚMERO {telefone}]: {resposta}", flush=True)
    
    # Como você já tem a função real de envio, a IA já vai responder o cliente de verdade!
    enviar_mensagem_whatsapp(telefone, resposta)
    
    return resposta
