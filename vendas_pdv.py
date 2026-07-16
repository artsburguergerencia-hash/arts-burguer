import requests
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum

# Importando a base do nosso banco anterior (assumindo que estão no mesmo escopo)
# from database import Base, SessionLocal, processar_baixa_estoque
from database import Base, SessionLocal, processar_baixa_estoque, ProdutoModel

# ==============================================================================
# 1. ENUMS (Status e Tipos padronizados para evitar erros)
# ==============================================================================
class TipoPedido(str, enum.Enum):
    BALCAO = "Balcão"
    MESA = "Mesa"
    DELIVERY = "Delivery"
    IFOOD = "iFood"

class StatusPedido(str, enum.Enum):
    RECEBIDO = "Recebido"          # Caiu no sistema
    PREPARANDO = "Preparando"      # Apareceu no KDS (Cozinha)
    PRONTO = "Pronto"              # Aguardando retirada ou motoboy
    EM_ROTA = "Em Rota de Entrega" # Saiu com motoboy
    CONCLUIDO = "Concluído"        # Entregue e pago
    CANCELADO = "Cancelado"

# ==============================================================================
# 2. MODELOS DO BANCO DE DADOS (Vendas e Clientes)
# ==============================================================================

# --- ATUALIZE O SEU ClienteModel EM vendas_pdv.py ---
class ClienteModel(Base):
    """Cadastro unificado de clientes do Art's Burguer."""
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, unique=True, index=True, nullable=False) # Login
    senha_hash = Column(String, nullable=True) # 👈 Senha de acesso ao Cardápio
    cpf = Column(String, unique=True, nullable=True) # 👈 Adicionado
    data_nascimento = Column(String, nullable=True) # 👈 Formato DD/MM
    
    # Endereço
    cep = Column(String, nullable=True)
    logradouro = Column(String, nullable=True)
    numero = Column(String, nullable=True)
    bairro = Column(String, nullable=True)
    complemento = Column(String, nullable=True)
    
    pontos_fidelidade = Column(Integer, default=0)
    saldo_cashback = Column(Float, default=0.0)
    bloqueado = Column(Boolean, default=False)
    
    pedidos = relationship("PedidoModel", back_populates="cliente")
    
    
    # Relacionamento: Um cliente pode ter vários pedidos
    pedidos = relationship("PedidoModel", back_populates="cliente")


class PedidoModel(Base):
    """Cabeçalho da Comanda/Pedido."""
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True) # Nullable para pedidos rápidos no balcão
    tipo_pedido = Column(String, nullable=False) # Balcão, Delivery, etc.
    status = Column(String, default=StatusPedido.RECEBIDO)
    data_hora = Column(DateTime, default=datetime.utcnow)
    
    # Financeiro do Pedido
    subtotal = Column(Float, default=0.0)
    taxa_entrega = Column(Float, default=0.0)
    desconto = Column(Float, default=0.0)
    total_pago = Column(Float, default=0.0)

    # Relacionamentos
    cliente = relationship("ClienteModel", back_populates="pedidos")
    itens = relationship("ItemPedidoModel", back_populates="pedido", cascade="all, delete-orphan")


class ItemPedidoModel(Base):
    """Os lanches e bebidas dentro de um pedido específico."""
    __tablename__ = "itens_pedido"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False, default=1)
    preco_unitario = Column(Float, nullable=False) # Registra o preço no momento da venda
    observacao = Column(String, nullable=True)     # Ex: "Sem cebola", "Ponto da carne: Mal passada"

    # Relacionamentos
    pedido = relationship("PedidoModel", back_populates="itens")
    produto = relationship("ProdutoModel") # Conecta com a tabela de Produtos criada antes


# ==============================================================================
# 3. INTEGRAÇÃO E LÓGICA DE NEGÓCIO
# ==============================================================================

def buscar_endereco_por_cep(cep: str):
    """Consome a API pública do ViaCEP para autocompletar o cadastro do cliente."""
    cep_limpo = cep.replace("-", "").strip()
    if len(cep_limpo) != 8:
        return {"erro": "CEP inválido."}
        
    try:
        response = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=5)
        dados = response.json()
        if "erro" in dados:
            return {"erro": "CEP não encontrado."}
            
        return {
            "logradouro": dados.get("logradouro"),
            "bairro": dados.get("bairro"),
            "cidade": dados.get("localidade"),
            "uf": dados.get("uf")
        }
    except requests.exceptions.RequestException:
        return {"erro": "Falha de comunicação com o serviço de CEP."}

def registrar_venda_pdv(db, tipo: str, itens_carrinho: list, cliente_id: int = None, taxa_entrega: float = 0.0):
    """
    Função principal do Frente de Caixa:
    Cria o pedido, adiciona os itens, calcula o total e DÁ BAIXA NO ESTOQUE.
    """
    novo_pedido = PedidoModel(
        cliente_id=cliente_id,
        tipo_pedido=tipo,
        taxa_entrega=taxa_entrega,
        status=StatusPedido.RECEBIDO
    )
    db.add(novo_pedido)
    db.flush() # Gera o ID do pedido
    
    subtotal = 0.0
    
    for item in itens_carrinho:
        # Pega o produto no banco para registrar o preço atual
        produto = db.query(ProdutoModel).filter(ProdutoModel.id == item["produto_id"]).first()
        if not produto:
            continue
            
        # Adiciona o item na comanda
        novo_item = ItemPedidoModel(
            pedido_id=novo_pedido.id,
            produto_id=produto.id,
            quantidade=item["quantidade"],
            preco_unitario=produto.preco_venda,
            observacao=item.get("observacao", "")
        )
        db.add(novo_item)
        subtotal += (produto.preco_venda * item["quantidade"])
        
        # ⚠️ INTEGRAÇÃO COM ESTOQUE: Desconta os ingredientes da Ficha Técnica!
        # Aqui chamamos a função que criamos no módulo anterior
        processar_baixa_estoque(db, produto_id=produto.id, quantidade_vendida=item["quantidade"])
    
    # Atualiza os totais financeiros do pedido
    novo_pedido.subtotal = subtotal
    novo_pedido.total_pago = subtotal + taxa_entrega
    
    db.commit()
    db.refresh(novo_pedido)
    print(f"✅ Venda #{novo_pedido.id} registrada com sucesso! Total: R$ {novo_pedido.total_pago:.2f}")
    
    # Próximo passo ideal: Enviar para a tela do KDS (Cozinha)
    return novo_pedido