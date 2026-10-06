# whatsapp_ia.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Buscando as credenciais exclusivamente do ambiente (.env / Render)
WA_API_URL = os.getenv("WA_API_URL")
WA_TOKEN = os.getenv("WA_TOKEN")

def enviar_mensagem_whatsapp(telefone: str, mensagem: str):
    """
    Dispara mensagens de texto via Evolution API / Baileys.
    """
    if not WA_API_URL or not WA_TOKEN: 
        print("⚠️ [WhatsApp] Envio ignorado: WA_API_URL ou WA_TOKEN não configurados nas variáveis de ambiente.", flush=True)
        return False
        
    if not telefone or telefone == "BALCAO": 
        return False
        
    telefone_limpo = ''.join(filter(str.isdigit, str(telefone)))
    if not telefone_limpo.startswith("55") and len(telefone_limpo) <= 11:
        telefone_limpo = f"55{telefone_limpo}"
        
    # Estrutura exigida pela Evolution API
    payload = {
        "number": telefone_limpo,
        "text": mensagem,
        "delay": 1200
    }
    headers = {
        "apikey": WA_TOKEN, 
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(WA_API_URL, json=payload, headers=headers, timeout=8)
        if response.status_code in [200, 201]:
            print(f"✅ [WhatsApp] Notificação enviada com sucesso para {telefone_limpo}", flush=True)
            return True
        else:
            print(f"❌ [WhatsApp] Falha API: {response.status_code} - {response.text}", flush=True)
            return False
    except Exception as e:
        print(f"❌ [WhatsApp] Erro de rede: {e}", flush=True)
        return False


def notificar_status_pedido(telefone: str, nome: str, pedido_id: int, status: str):
    """
    Notifica o cliente sobre as etapas de produção e entrega do pedido.
    """
    link_mapa = os.getenv("BASE_URL", "https://artsburguer.com.br")

    mensagens = {
        "RECEBIDO": f"Olá, {nome}! 🍔 Acabamos de receber o seu pedido #{pedido_id}. Já estamos conferindo os detalhes para enviar para a cozinha!",
        "EM_PREPARO": f"Aí sim, {nome}! O seu pedido #{pedido_id} acabou de ir para a chapa. Daqui a pouco ele está pronto! 🔥👨‍🍳",
        "PRONTO": f"Tudo pronto, {nome}! O seu pedido #{pedido_id} já está embalado e quentinho aguardando! 📦✨",
        "SAIU_PARA_ENTREGA": f"Lanche na pista, {nome}! 🏍️💨 O nosso motoboy acabou de sair com o seu pedido #{pedido_id}. Fique atento ao portão!\n\n🗺️ Acompanhe o trajeto pelo mapa:\n{link_mapa}/mapa?pedido={pedido_id}",
        "ENTREGUE": f"Pedido entregue! 🎉 Muito obrigado por escolher o Art's Burguer, {nome}. Bom apetite e até a próxima! ⭐",
        "CANCELADO": f"Poxa, {nome}... O seu pedido #{pedido_id} foi cancelado. Se houve algum problema, mande uma mensagem pra gente tentar ajudar!"
    }
    
    msg = mensagens.get(status.upper())
    if msg:
        enviar_mensagem_whatsapp(telefone, msg)


def responder_com_ia(mensagem_cliente: str, telefone: str):
    """
    Cérebro de respostas automáticas da hamburgueria.
    Pode ser estendido no futuro para a API da OpenAI.
    """
    texto = str(mensagem_cliente).lower()
    resposta = ""
    
    # Árvore de decisão de autoatendimento
    if any(palavra in texto for palavra in ["cardapio", "menu", "pedir", "fome", "lanche"]):
        resposta = "Olá! Nosso cardápio é 100% digital e super rápido. Faça seu pedido por aqui: https://artsburguer.com.br 🍔🍟"
    
    elif any(palavra in texto for palavra in ["horario", "aberto", "funcionamento", "horas"]):
        resposta = "Nossas chapas esquentam de Terça a Domingo, das 18h às 23h59! 🕒🔥"
    
    elif any(palavra in texto for palavra in ["humano", "atendente", "problema", "errado", "ajuda"]):
        resposta = "Entendi! Vou chamar um humano da nossa equipe para falar com você. Só um instante! 👨‍💻"
    
    else:
        resposta = "Oi! Sou a assistente virtual do Art's Burguer 🤖🍔. Para fazer um pedido rápido, acesse nosso link: https://artsburguer.com.br. Posso te ajudar com mais alguma dúvida?"
        
    print(f"🤖 [IA RESPONDENDO {telefone}]: {resposta}", flush=True)
    enviar_mensagem_whatsapp(telefone, resposta)
    return resposta
