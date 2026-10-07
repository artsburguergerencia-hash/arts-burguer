import requests
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import enum

# Importamos a base, produtos e o CLIENTE OFICIAL do database.py
from database import (
    Base, 
    SessionLocal, 
    processar_baixa_estoque, 
    ProdutoModel, 
    ClienteModel
)

# ==============================================================================
# 1. ENUMS (Status e Tipos padronizados)
# ==============================================================================
class TipoPedido(str, enum.Enum):
    BALCAO = "Balcão"
    MESA = "Mesa"
    DELIVERY = "Delivery"
    IFOOD = "iFood"

class StatusPedido(str, enum.Enum):
    RECEBIDO = "Recebido"
    PREPARANDO = "Preparando"
    PRONTO = "Pronto"
    EM_ROTA = "Em Rota de Entrega"
    CONCLUIDO = "Concluído"
    CANCELADO = "Cancelado"

# ==============================================================================
# 2. MODELOS DE VENDAS (Pedidos e Itens)
# ==============================================================================
class PedidoModel(Base):
    """Cabeçalho da Comanda / Pedido de Venda."""
    __tablename__ = "pedidos"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True) # Nullable para balcão rápido
    tipo_pedido = Column(String, nullable=False, default="Balcão")
    status = Column(String, default=StatusPedido.RECEBIDO)
    data_hora = Column(DateTime, default=datetime.utcnow)
    data_pedido = Column(DateTime, default=datetime.utcnow)
    origem = Column(String, default="BALCAO")
    senha_diaria = Column(String, default="001")
    forma_pagamento = Column(String, default="Dinheiro")
    
    # Coordenadas do entregador para o mapa
    entregador_lat = Column(Float, nullable=True, default=0.0)
    entregador_lng = Column(Float, nullable=True, default=0.0)

    # Financeiro do Pedido
    subtotal = Column(Float, default=0.0)
    taxa_entrega = Column(Float, default=0.0)
    desconto = Column(Float, default=0.0)
    total_pago = Column(Float, default=0.0)

    # Relacionamentos com Cliente e Itens
    cliente = relationship("ClienteModel", backref="pedidos")
    itens = relationship("ItemPedidoModel", back_populates="pedido", cascade="all, delete-orphan")


class ItemPedidoModel(Base):
    """Lanches, bebidas e complementos dentro de um pedido."""
    __tablename__ = "itens_pedido"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False, default=1)
    preco_unitario = Column(Float, nullable=False)
    observacao = Column(String, nullable=True, default="")

    pedido = relationship("PedidoModel", back_populates="itens")
    produto = relationship("ProdutoModel")


# ==============================================================================
# 3. LÓGICA DE NEGÓCIO DO PDV
# ==============================================================================
def buscar_endereco_por_cep(cep: str):
    """Consome a API pública do ViaCEP com timeout de segurança."""
    cep_limpo = cep.replace("-", "").strip()
    if len(cep_limpo) != 8:
        return {"erro": "CEP inválido."}
        
    try:
        response = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=4)
        dados = response.json()
        if "erro" in dados:
            return {"erro": "CEP não encontrado."}
            
        return {
            "logradouro": dados.get("logradouro", ""),
            "bairro": dados.get("bairro", ""),
            "cidade": dados.get("localidade", ""),
            "uf": dados.get("uf", "")
        }
    except Exception:
        return {"erro": "Falha de comunicação com o serviço de CEP."}


def registrar_venda_pdv(db, tipo: str, itens_carrinho: list, cliente_id: int = None, taxa_entrega: float = 0.0):
    """
    Registra o pedido no caixa, calcula o total e executa a baixa no estoque.
    """
    tipo_str = str(tipo).split('.')[-1] if hasattr(tipo, 'value') or '.' in str(tipo) else str(tipo)

    novo_pedido = PedidoModel(
        cliente_id=cliente_id,
        tipo_pedido=tipo_str,
        taxa_entrega=taxa_entrega,
        status=StatusPedido.RECEBIDO
    )
    db.add(novo_pedido)
    db.flush() # Gera o ID do pedido antes de inserir os itens
    
    subtotal = 0.0
    
    for item in itens_carrinho:
        produto = db.query(ProdutoModel).filter(ProdutoModel.id == item["produto_id"]).first()
        if not produto:
            continue
            
        novo_item = ItemPedidoModel(
            pedido_id=novo_pedido.id,
            produto_id=produto.id,
            quantidade=item["quantidade"],
            preco_unitario=produto.preco_venda,
            observacao=item.get("observacao", "")
        )
        db.add(novo_item)
        subtotal += (produto.preco_venda * item["quantidade"])
        
        # Baixa atômica de estoque protegida por concorrência
        processar_baixa_estoque(db, produto_id=produto.id, quantidade_vendida=item["quantidade"])
    
    novo_pedido.subtotal = subtotal
    novo_pedido.total_pago = subtotal + taxa_entrega
    
    db.commit()
    db.refresh(novo_pedido)
    print(f"✅ Pedido #{novo_pedido.id} registrado com sucesso! Total: R$ {novo_pedido.total_pago:.2f}", flush=True)
    return novo_pedido
