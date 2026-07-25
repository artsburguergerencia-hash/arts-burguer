from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./banco_v5_master_rh.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# === CONFIGURAÇÕES DA LOJA ===
class ConfiguracaoLojaModel(Base):
    __tablename__ = "configuracoes_loja"
    __table_args__ = {'extend_existing': True}
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
    planos_saude_opcoes = Column(String, default="Nenhum,Amil Básico,Bradesco Odonto") 

# === CARGOS DINÂMICOS ===
class Cargo(Base):
    __tablename__ = "cargos"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    permissoes = Column(String, default="basico") 

# === FUNCIONÁRIOS E RH ===
class FuncionarioModel(Base):
    __tablename__ = "funcionarios"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    usuario = Column(String, unique=True, index=True)
    senha_hash = Column(String)
    cargo_id = Column(Integer, ForeignKey("cargos.id"))
    foto_3x4 = Column(String, default="") 
    matricula_cracha = Column(String, unique=True, index=True, nullable=True) 

class InfoRHModel(Base):
    __tablename__ = "info_rh"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer, unique=True)
    status_admissao = Column(String, default="PENDENTE_PREENCHIMENTO") 
    aceite_lgpd = Column(Boolean, default=False)
    data_aceite_lgpd = Column(String, default="")
    telefone = Column(String, default="")
    salario = Column(Float, default=0.0)
    escala = Column(String, default="")
    
    # Benefícios e Finanças do Funcionário
    recebe_comissao = Column(Boolean, default=False)
    tipo_comissao = Column(String, default="PERCENTUAL") 
    valor_comissao = Column(Float, default=0.0) 
    valor_vt = Column(Float, default=0.0) 
    valor_va = Column(Float, default=0.0) 
    diaria_motoboy = Column(Float, default=0.0)
    repasse_por_entrega = Column(Float, default=0.0)
    gorjetas_acumuladas = Column(Float, default=0.0)
    escala_matriz_json = Column(String, default="{}") 
    
    # Documentos Oficiais
    data_nascimento = Column(String, default="")
    naturalidade = Column(String, default="")
    estado_civil = Column(String, default="")
    rg = Column(String, default="")
    cpf = Column(String, default="")
    pis_pasep = Column(String, default="")
    titulo_eleitor = Column(String, default="")
    reservista = Column(String, default="")
    endereco_completo = Column(String, default="")
    dados_bancarios = Column(String, default="") 
    escolaridade = Column(String, default="")
    qtd_filhos_menores = Column(Integer, default=0)
    cnh = Column(String, default="")
    plano_saude_escolhido = Column(String, default="")
    link_pasta_documentos = Column(String, default="")

class PontoModel(Base):
    __tablename__ = "pontos_rh"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer)
    data = Column(String) 
    entrada = Column(String, default="")
    saida = Column(String, default="")
    horas_trabalhadas = Column(Float, default=0.0) 
    horas_extras = Column(Float, default=0.0) 

class OcorrenciaRHModel(Base):
    __tablename__ = "ocorrencias_rh"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer, ForeignKey("funcionarios.id"))
    data_registro = Column(DateTime, default=datetime.utcnow)
    data_ocorrencia = Column(String)
    tipo = Column(String) 
    motivo = Column(String, default="")
    horas_abonadas = Column(Float, default=0.0) 
    horas_descontadas = Column(Float, default=0.0) 
    anexo_url = Column(String, default="") 

class SolicitacaoFeriasModel(Base):
    __tablename__ = "ferias_rh"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer, ForeignKey("funcionarios.id"))
    data_solicitacao = Column(DateTime, default=datetime.utcnow)
    data_inicio = Column(String)
    data_fim = Column(String)
    status = Column(String, default="PENDENTE") 
    observacao_gestor = Column(String, default="")

# === CARDÁPIO E ESTOQUE ===
class InsumoModel(Base):
    __tablename__ = "insumos"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    unidade_medida = Column(String)
    quantidade_atual = Column(Float, default=0.0)
    quantidade_minima = Column(Float, default=0.0)
    custo_unitario = Column(Float, default=0.0)

class ProdutoModel(Base):
    __tablename__ = "produtos"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    descricao = Column(String, default="")
    preco_venda = Column(Float)
    categoria = Column(String)
    imagem_url = Column(String, default="")

class FichaTecnicaModel(Base):
    __tablename__ = "fichas_tecnicas"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"))
    insumo_id = Column(Integer, ForeignKey("insumos.id"))
    quantidade_necessaria = Column(Float)

class GrupoComplementoModel(Base):
    __tablename__ = "grupos_complementos"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"))
    nome = Column(String)
    obrigatorio = Column(Boolean, default=False)
    minimo_opcoes = Column(Integer, default=0)
    maximo_opcoes = Column(Integer, default=1)
    itens = relationship("ItemComplementoModel", backref="grupo", cascade="all, delete-orphan")

class ItemComplementoModel(Base):
    __tablename__ = "itens_complementos"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos_complementos.id"))
    nome = Column(String)
    preco_adicional = Column(Float, default=0.0)


# 🚨 SCRIPT DE AUTO-MIGRAÇÃO E RECUPERAÇÃO DO BANCO 🚨
def inicializar_banco():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    colunas_novas = [
        "ALTER TABLE funcionarios ADD COLUMN foto_3x4 VARCHAR DEFAULT '';",
        "ALTER TABLE funcionarios ADD COLUMN matricula_cracha VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN escala VARCHAR DEFAULT '';",
        "ALTER TABLE cargos ADD COLUMN permissoes VARCHAR DEFAULT 'basico';",
        "ALTER TABLE info_rh ADD COLUMN recebe_comissao BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE info_rh ADD COLUMN tipo_comissao VARCHAR DEFAULT 'PERCENTUAL';",
        "ALTER TABLE info_rh ADD COLUMN valor_comissao FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN valor_vt FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN valor_va FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN diaria_motoboy FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN repasse_por_entrega FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN gorjetas_acumuladas FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN escala_matriz_json VARCHAR DEFAULT '{}';",
        "ALTER TABLE pontos_rh ADD COLUMN horas_trabalhadas FLOAT DEFAULT 0.0;",
        "ALTER TABLE pontos_rh ADD COLUMN horas_extras FLOAT DEFAULT 0.0;",
        "ALTER TABLE configuracoes_loja ADD COLUMN planos_saude_opcoes VARCHAR DEFAULT 'Nenhum,Amil Básico,Bradesco Odonto';"
    ]
    
    for sql in colunas_novas:
        try:
            db.execute(text(sql))
            db.commit()
        except Exception:
            db.rollback() 

    try:
        cargo_admin = db.query(Cargo).filter(Cargo.nome == "Administrador").first()
        if not cargo_admin:
            cargo_admin = Cargo(nome="Administrador", permissoes="total")
            db.add(cargo_admin)
            db.flush() 

        if not db.query(FuncionarioModel).first():
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
            admin = FuncionarioModel(nome="Admin Supremo", usuario="admin", senha_hash=pwd_context.hash("admin123"), cargo_id=cargo_admin.id, matricula_cracha="0001")
            db.add(admin)
            config = ConfiguracaoLojaModel()
            db.add(config)
            db.commit()
    except Exception as e:
        db.rollback()
        
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
