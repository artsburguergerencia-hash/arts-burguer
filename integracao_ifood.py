from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

# Importando o motor que já construímos
from database import SessionLocal, ProdutoModel
from vendas_pdv import registrar_venda_pdv, TipoPedido, ClienteModel

# ==============================================================================
# 1. CONFIGURAÇÃO DO MÓDULO E SCHEMAS DO IFOOD
# ==============================================================================
# Usamos APIRouter para poder acoplar este arquivo no nosso main.py depois
router_ifood = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Estrutura simplificada do JSON que o iFood envia para o nosso sistema
class ItemiFood(BaseModel):
    externalCode: str  # É o ID do nosso banco de dados cadastrado lá no painel do iFood
    name: str
    quantity: int
    price: float
    observations: Optional[str] = ""

class ClienteiFood(BaseModel):
    id: str
    name: str
    phone: str

class PedidoiFoodPayload(BaseModel):
    id: str
    orderType: str # DELIVERY ou TAKEOUT
    customer: ClienteiFood
    items: List[ItemiFood]
    totalOrderAmount: float
    deliveryFee: float


# ==============================================================================
# 2. LÓGICA DE INTEGRAÇÃO (O Tradutor)
# ==============================================================================

def processar_pedido_externo(db: Session, payload: PedidoiFoodPayload):
    """
    Pega os dados brutos do iFood e converte para o formato do Art's Burguer.
    """
    print(f"\n🔴 [iFood] NOVO PEDIDO RECEBIDO! ID do iFood: {payload.id}")
    
    # 1. Verifica/Cadastra o cliente no nosso banco local para o CRM
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == payload.customer.phone).first()
    if not cliente:
        cliente = ClienteModel(nome=payload.customer.name, telefone=payload.customer.phone)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        print(f"   👤 Novo cliente do iFood salvo no banco local: {cliente.nome}")

    # 2. Traduz os itens do iFood para o nosso carrinho
    itens_carrinho = []
    for item in payload.items:
        try:
            # Transforma o 'externalCode' do iFood no ID do nosso ProdutoModel
            produto_id_local = int(item.externalCode) 
            
            itens_carrinho.append({
                "produto_id": produto_id_local,
                "quantidade": item.quantity,
                "observacao": item.observations
            })
        except ValueError:
            print(f"   ❌ Erro: externalCode '{item.externalCode}' inválido para o produto '{item.name}'.")
            continue

    # 3. Injeta no Frente de Caixa (que avisa a cozinha e dá baixa no estoque)
    if itens_carrinho:
        novo_pedido_local = registrar_venda_pdv(
            db=db,
            tipo=TipoPedido.IFOOD,
            itens_carrinho=itens_carrinho,
            cliente_id=cliente.id,
            taxa_entrega=payload.deliveryFee
        )
        print(f"   ✅ Pedido iFood integrado com sucesso! Comanda Local: #{novo_pedido_local.id}")
        return novo_pedido_local
    else:
        print("   ⚠️ O pedido não pôde ser integrado pois os itens não bateram com o estoque local.")
        return None

# ==============================================================================
# 3. ENDPOINT WEBHOOK (A Porta de Entrada)
# ==============================================================================

@router_ifood.post("/webhook/ifood/pedidos")
def webhook_receber_pedido_ifood(payload: PedidoiFoodPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Esta é a URL que você cadastraria no Portal do Parceiro do iFood.
    Sempre que um cliente comprar lá, o iFood dispara um 'POST' para cá.
    """
    try:
        # Usamos BackgroundTasks para responder '200 OK' ao iFood instantaneamente 
        # (evitando timeout) e processar a baixa de estoque em segundo plano.
        background_tasks.add_task(processar_pedido_externo, db, payload)
        
        # Em uma integração real, aqui também faríamos uma requisição POST de volta
        # para a API do iFood avisando: "O restaurante aceitou o pedido!"
        
        return {"status": "success", "message": "Pedido recebido. Processando integração local..."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na integração: {str(e)}")

# ==============================================================================
# Nota: Para rodar isso, basta adicionar `app.include_router(router_ifood)` 
# no seu arquivo `main.py`!
# ==============================================================================