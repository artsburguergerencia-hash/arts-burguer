from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

# Importando o motor do nosso sistema
from database import SessionLocal, ProdutoModel
from vendas_pdv import ClienteModel, registrar_venda_pdv, TipoPedido

router_99food = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================================================================
# 1. SCHEMAS (O formato de dados que a 99Food envia para nós)
# ==============================================================================
# Nota: Este é um modelo adaptado de como as APIs de delivery funcionam
class Item99Food(BaseModel):
    codigo_pdv: str # O ID do nosso produto lá no painel deles
    nome: str
    quantidade: int
    observacao: str = ""
    preco_unitario: float

class Cliente99Food(BaseModel):
    nome: str
    telefone_ofuscado: str # A 99Food costuma não mandar o número real por privacidade

class WebhookPedido99Food(BaseModel):
    id_pedido_99: str
    codigo_verificacao: str
    cliente: Cliente99Food
    itens: List[Item99Food]
    valor_total: float

# ==============================================================================
# 2. ROTAS DE COMUNICAÇÃO (Webhooks)
# ==============================================================================

@router_99food.post("/api/webhooks/99food/novo-pedido")
async def receber_pedido_99food(payload: WebhookPedido99Food, db: Session = Depends(get_db)):
    """
    Esta é a porta que fica aberta esperando a 99Food enviar pedidos.
    Quando um cliente compra lá no app da 99, o servidor deles aciona essa função.
    """
    
    # 1. Identificando o Cliente (Cadastra se não existir)
    # Como as plataformas ofuscam o número, usamos um formato misto
    telefone_provisorio = f"99FOOD-{payload.cliente.telefone_ofuscado}"
    
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == telefone_provisorio).first()
    if not cliente:
        cliente = ClienteModel(nome=f"[99Food] {payload.cliente.nome}", telefone=telefone_provisorio)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    # 2. Convertendo o pedido da 99Food para o formato do nosso sistema
    itens_carrinho = []
    for item_99 in payload.itens:
        # A 99Food manda um ID de texto, precisamos garantir que é um número do nosso banco
        try:
            produto_id_real = int(item_99.codigo_pdv)
            itens_carrinho.append({
                "produto_id": produto_id_real,
                "quantidade": item_99.quantidade,
                "observacao": item_99.observacao
            })
        except ValueError:
            # Se o ID não for reconhecido, ignora (ou poderia mapear para um produto "Genérico")
            continue
            
    if not itens_carrinho:
        raise HTTPException(status_code=400, detail="Nenhum produto válido encontrado no pedido da 99Food.")

    # 3. Mágica acontecendo: Joga pro Frente de Caixa -> Estoque -> KDS da Cozinha
    try:
        novo_pedido = registrar_venda_pdv(
            db=db,
            tipo=TipoPedido.DELIVERY, 
            itens_carrinho=itens_carrinho,
            cliente_id=cliente.id
        )
        
        # Assim que essa função termina, o KDS já vai apitar em vermelho na sua cozinha!
        return {
            "status": "sucesso",
            "mensagem": "Pedido integrado com sucesso no KDS",
            "pedido_interno_id": novo_pedido.id,
            "id_99food": payload.id_pedido_99
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar pedido 99Food: {str(e)}")

# Rota para a 99Food checar se nosso sistema está online
@router_99food.get("/api/webhooks/99food/status")
def checar_status_integracao():
    return {"status": "ONLINE", "loja": "Art's Burguer", "versao": "1.0.0"}