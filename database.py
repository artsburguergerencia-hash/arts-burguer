from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./banco_v3_rh.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# === CONFIGURAÇÕES DA LOJA ===
class ConfiguracaoLojaModel(Base):
    __tablename__ = "configuracoes_loja"
    id = Column(Integer, primary_key=True, index=True)
    nome_empresa = Column(String, default="Art's Burguer")
    cnpj = Column(String, default="")
    endereco = Column(String, default="")
    telefone = Column(String, default="")
    logo_url = Column(String, default="https://via.placeholder.com/150")
    aceita_delivery = Column(Boolean, default=True)
    aceita_retirada = Column(Boolean, default=True)
    aceite_automatico = Column(Boolean, default=False)
    tempo_preparo = Column(Integer, default=30)
    formas_pagamento = Column(String, default="Pix,Dinheiro,Cartão")
    sistema_fidelidade = Column(String, default="CASHBACK")
    categorias_cardapio = Column(String, default="Burger Artesanal,Bebidas,Porções")
    categorias_fornecedor = Column(String, default="Carnes,Hortifruti,Bebidas,Embalagens")
    planos_saude_opcoes = Column(String, default="Nenhum,Amil Básico,Bradesco Odonto") # NOVO: Configurável via Gestão

# === RECURSOS HUMANOS (COMPLETO) ===
class Cargo(Base):
    __tablename__ = "cargos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)

class FuncionarioModel(Base):
    __tablename__ = "funcionarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    usuario = Column(String, unique=True, index=True)
    senha_hash = Column(String)
    cargo_id = Column(Integer, ForeignKey("cargos.id"))
    foto_3x4 = Column(String, default="") # Base64 da Foto
    matricula_cracha = Column(String, unique=True, index=True, nullable=True) # Gerado pelo sistema

class InfoRHModel(Base):
    __tablename__ = "info_rh"
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer, unique=True)
    
    # Admissão e LGPD
    status_admissao = Column(String, default="PENDENTE_PREENCHIMENTO") # PENDENTE, ATIVO, DEMITIDO
    aceite_lgpd = Column(Boolean, default=False)
    data_aceite_lgpd = Column(String, default="")
    
    # Base Contratual
    telefone = Column(String, default="")
    salario = Column(Float, default=0.0)
    escala = Column(String, default="")
    
    # Dados Pessoais e Identificação
    data_nascimento = Column(String, default="")
    naturalidade = Column(String, default="")
    estado_civil = Column(String, default="")
    rg = Column(String, default="")
    cpf = Column(String, default="")
    pis_pasep = Column(String, default="")
    titulo_eleitor = Column(String, default="")
    reservista = Column(String, default="")
    endereco_completo = Column(String, default="")
    
    # Contrato e Benefícios
    dados_bancarios = Column(String, default="") # Banco, Agência, Conta
    escolaridade = Column(String, default="")
    qtd_filhos_menores = Column(Integer, default=0)
    cnh = Column(String, default="")
    plano_saude_escolhido = Column(String, default="")
    
    # Repositório de Documentos (Link Google Drive/Cloud)
    link_pasta_documentos = Column(String, default="")

class PontoModel(Base):
    __tablename__ = "pontos_rh"
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer)
    data = Column(String) 
    entrada = Column(String, default="")
    saida = Column(String, default="")

# === CLIENTES E PEDIDOS ===
class ClienteModel(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    telefone = Column(String, unique=True, index=True)
    senha_hash = Column(String, nullable=True)
    cpf = Column(String, default="")
    data_nascimento = Column(String, default="")
    cep = Column(String, default="")
    logradouro = Column(String, default="")
    numero = Column(String, default="")
    bairro = Column(String, default="")
    complemento = Column(String, default="")
    pontos_fidelidade = Column(Integer, default=0)
    saldo_cashback = Column(Float, default=0.0)
    bloqueado = Column(Boolean, default=False)
    pedidos = relationship("PedidoModel", back_populates="cliente")

class PedidoModel(Base):
    __tablename__ = "pedidos"
    id = Column(Integer, primary_key=True, index=True)
    senha_diaria = Column(Integer, default=1)
    data_pedido = Column(Date, default=datetime.utcnow().date)
    origem = Column(String, default="SITE")
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    total_pago = Column(Float)
    forma_pagamento = Column(String)
    status = Column(String, default="RECEBIDO")
    tipo = Column(String, default="DELIVERY")
    data_criacao = Column(DateTime, default=datetime.utcnow)
    cliente = relationship("ClienteModel", back_populates="pedidos")
    itens = relationship("ItemPedidoModel", backref="pedido", cascade="all, delete-orphan")

class ItemPedidoModel(Base):
    __tablename__ = "itens_pedido"
    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"))
    produto_id = Column(Integer, ForeignKey("produtos.id"))
    quantidade = Column(Integer)
    observacao = Column(String, default="")

# === CARDÁPIO E ESTOQUE ===
class InsumoModel(Base):
    __tablename__ = "insumos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    unidade_medida = Column(String)
    quantidade_atual = Column(Float, default=0.0)
    quantidade_minima = Column(Float, default=0.0)
    custo_unitario = Column(Float, default=0.0)

class ProdutoModel(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    descricao = Column(String, default="")
    preco_venda = Column(Float)
    categoria = Column(String)
    imagem_url = Column(String, default="")

class FichaTecnicaModel(Base):
    __tablename__ = "fichas_tecnicas"
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"))
    insumo_id = Column(Integer, ForeignKey("insumos.id"))
    quantidade_necessaria = Column(Float)

class GrupoComplementoModel(Base):
    __tablename__ = "grupos_complementos"
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"))
    nome = Column(String)
    obrigatorio = Column(Boolean, default=False)
    minimo_opcoes = Column(Integer, default=0)
    maximo_opcoes = Column(Integer, default=1)
    itens = relationship("ItemComplementoModel", backref="grupo", cascade="all, delete-orphan")

class ItemComplementoModel(Base):
    __tablename__ = "itens_complementos"
    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos_complementos.id"))
    nome = Column(String)
    preco_adicional = Column(Float, default=0.0)

# === FINANCEIRO ===
class FornecedorModel(Base):
    __tablename__ = "fornecedores"
    id = Column(Integer, primary_key=True, index=True)
    nome_fantasia = Column(String)
    categoria = Column(String, default="Geral")
    contato = Column(String, default="")
    cnpj = Column(String, default="")

class ContaPagarModel(Base):
    __tablename__ = "contas_pagar"
    id = Column(Integer, primary_key=True, index=True)
    fornecedor_id = Column(Integer, ForeignKey("fornecedores.id"), nullable=True)
    descricao = Column(String)
    valor = Column(Float)
    data_vencimento = Column(Date)
    tipo_despesa = Column(String, default="Empresa")
    status = Column(String, default="PENDENTE")

def inicializar_banco():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if not db.query(FuncionarioModel).first():
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        admin = FuncionarioModel(nome="Admin Supremo", usuario="admin", senha_hash=pwd_context.hash("admin123"), cargo_id=1, matricula_cracha="0001")
        db.add(admin)
        config = ConfiguracaoLojaModel()
        db.add(config)
        db.commit()
    db.close()

def cadastrar_insumo(db, nome, unidade, qtd_inicial, qtd_min, custo):
    novo = InsumoModel(nome=nome, unidade_medida=unidade, quantidade_atual=qtd_inicial, quantidade_minima=qtd_min, custo_unitario=custo)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

def processar_baixa_estoque(db, produto_id, quantidade_vendida):
    fichas = db.query(FichaTecnicaModel).filter(FichaTecnicaModel.produto_id == produto_id).all()
    for f in fichas:
        insumo = db.query(InsumoModel).filter(InsumoModel.id == f.insumo_id).first()
        if insumo: insumo.quantidade_atual -= (f.quantidade_necessaria * quantidade_vendida)
    db.commit()
