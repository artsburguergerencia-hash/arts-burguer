from typing import List
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from pydantic import BaseModel, Field

# 1. CONFIGURAÇÃO DO BANCO DE DADOS
DATABASE_URL = "postgresql://neondb_owner:npg_6tXbeNrB4OAL@ep-falling-frog-acuu6b2h-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. MODELOS DO BANCO DE DADOS
class InsumoModel(Base):
    __tablename__ = "insumos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False, index=True)
    unidade_medida = Column(String, nullable=False)
    quantidade_atual = Column(Float, default=0.0)
    quantidade_minima = Column(Float, default=0.0)
    custo_unitario = Column(Float, nullable=False)
    fichas_tecnicas = relationship("FichaTecnicaModel", back_populates="insumo")

class FichaTecnicaModel(Base):
    __tablename__ = "fichas_tecnicas"
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False)
    insumo_id = Column(Integer, ForeignKey("insumos.id", ondelete="RESTRICT"), nullable=False)
    quantidade_necessaria = Column(Float, nullable=False)
    produto = relationship("ProdutoModel", back_populates="itens_ficha")
    insumo = relationship("InsumoModel", back_populates="fichas_tecnicas")

class Cargo(Base):
    __tablename__ = "cargos"
    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True)

class FuncionarioModel(Base):
    __tablename__ = "funcionarios"
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    usuario = Column(String, unique=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    cargo_id = Column(Integer, ForeignKey("cargos.id"))
    foto = Column(String, nullable=True)

class ContaFinanceira(Base):
    __tablename__ = "contas_financeiras"
    id = Column(Integer, primary_key=True)
    descricao = Column(String)
    valor = Column(Float)
    tipo = Column(String)
    data_vencimento = Column(String)

class MensagemWhatsAppModel(Base):
    __tablename__ = "mensagens_whatsapp"
    id = Column(Integer, primary_key=True, index=True)
    # Guardamos apenas o telefone para evitar erros de importação circular
    telefone = Column(String, index=True)
    mensagem = Column(String)
    direcao = Column(String) # "ENVIADA" ou "RECEBIDA"
    data_hora = Column(DateTime, default=datetime.utcnow)
    lida = Column(Boolean, default=False)

# 3. VALIDAÇÃO DE DADOS (Pydantic)
class ItemFichaInput(BaseModel):
    insumo_id: int
    quantidade_necessaria: float = Field(..., gt=0)

class ProdutoCreateInput(BaseModel):
    nome: str
    preco_venda: float = Field(..., gt=0)
    categoria: str
    itens_ficha: List[ItemFichaInput]

# --- ADICIONE ESTAS NOVAS TABELAS EM database.py ---

class GrupoComplementoModel(Base):
    """Ex: 'Escolha sua Bebida', 'Escolha seu Molho'"""
    __tablename__ = "grupos_complemento"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    obrigatorio = Column(Boolean, default=False)
    minimo_opcoes = Column(Integer, default=0)
    maximo_opcoes = Column(Integer, default=1)
    produto_id = Column(Integer, ForeignKey("produtos.id")) # O lanche a que pertence
    
    itens = relationship("ItemComplementoModel", back_populates="grupo", cascade="all, delete-orphan")

class ItemComplementoModel(Base):
    """Ex: 'Coca-Cola 350ml', 'Molho Cheddar'"""
    __tablename__ = "itens_complemento"
    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos_complemento.id"))
    nome = Column(String, nullable=False)
    preco_adicional = Column(Float, default=0.0)
    
    grupo = relationship("GrupoComplementoModel", back_populates="itens")

# --- ATUALIZE O SEU ProdutoModel EM database.py ---
class ProdutoModel(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False, index=True)
    descricao = Column(String, nullable=True) # Adicionado para os ingredientes
    preco_venda = Column(Float, nullable=False)
    categoria = Column(String, nullable=False)
    imagem_url = Column(String, nullable=True) # 👈 Adicionado para a foto do lanche
    ativo = Column(Integer, default=1)
    
    itens_ficha = relationship("FichaTecnicaModel", back_populates="produto", cascade="all, delete-orphan")

# 4. FUNÇÕES DE NEGÓCIO
def cadastrar_insumo(db, nome: str, unidade: str, qtd_inicial: float, qtd_min: float, custo: float):
    insumo = InsumoModel(nome=nome, unidade_medida=unidade, quantidade_atual=qtd_inicial, quantidade_minima=qtd_min, custo_unitario=custo)
    db.add(insumo)
    db.commit()
    db.refresh(insumo)
    return insumo

def criar_produto_com_ficha(db, dados_produto: ProdutoCreateInput):
    novo_produto = ProdutoModel(nome=dados_produto.nome, preco_venda=dados_produto.preco_venda, categoria=dados_produto.categoria)
    db.add(novo_produto)
    db.flush()
    for item in dados_produto.itens_ficha:
        db.add(FichaTecnicaModel(produto_id=novo_produto.id, insumo_id=item.insumo_id, quantidade_necessaria=item.quantidade_necessaria))
    db.commit()
    db.refresh(novo_produto)
    return novo_produto

def processar_baixa_estoque(db, produto_id: int, quantidade_vendida: int = 1):
    produto = db.query(ProdutoModel).filter(ProdutoModel.id == produto_id).first()
    if not produto: return False
    for item in produto.itens_ficha:
        item.insumo.quantidade_atual -= (item.quantidade_necessaria * quantidade_vendida)
    db.commit()
    return True

def inicializar_banco():
    Base.metadata.create_all(bind=engine)
    
    # --- AUTO-PREENCHIMENTO E ATUALIZAÇÃO ---
    db = SessionLocal()
    try:
        # ATUALIZAÇÕES DO SISTEMA (Forçando a criação das colunas novas no Neon DB)
        from sqlalchemy import text
        db.execute(text("ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS foto VARCHAR"))
        db.execute(text("ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS tipo_despesa VARCHAR DEFAULT 'Empresa'"))
        
        # Novas colunas da Fase 1 (Cardápio e Clientes)
        db.execute(text("ALTER TABLE produtos ADD COLUMN IF NOT EXISTS descricao VARCHAR"))
        db.execute(text("ALTER TABLE produtos ADD COLUMN IF NOT EXISTS imagem_url VARCHAR"))
        
        db.execute(text("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS senha_hash VARCHAR"))
        db.execute(text("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cpf VARCHAR"))
        db.execute(text("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS data_nascimento VARCHAR"))
        db.commit()

        # Injetando cargos padrão no banco de dados se estiver vazio
        if db.query(Cargo).count() == 0:
            print("⚙️ Injetando cargos padrão no banco de dados...")
            db.add_all([
                Cargo(id=1, nome="Administrador"),
                Cargo(id=2, nome="Caixa"),
                Cargo(id=3, nome="Cozinha"),
                Cargo(id=4, nome="Motoboy")
            ])
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Aviso no banco de dados (As colunas já devem existir): {e}")
    finally:
        db.close()