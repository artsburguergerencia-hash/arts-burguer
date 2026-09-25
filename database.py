import os
from datetime import datetime, date, timedelta
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, 
    Boolean, ForeignKey, Date, DateTime, text, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./banco_v5_master_rh.db")

# Ajuste automático de prefixo postgres para SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuração de Pool otimizada para o Neon PostgreSQL Serverless
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,             
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 1. CONFIGURAÇÕES DA LOJA & API KEYS
# ==========================================
class ConfiguracaoLojaModel(Base):
    __tablename__ = "configuracoes_loja"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    nome_empresa = Column(String, default="Art's Burguer")
    cnpj = Column(String, default="")
    inscricao_estadual = Column(String, default="")
    horario_funcionamento = Column(String, default="")
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
    planos_saude_opcoes = Column(String, default="Nenhum,Amil Básico,Bradesco Odonto,Gympass") 
    regra_acumulo = Column(String, default="POR_PEDIDO")
    fidelidade_ganho = Column(Float, default=0.0)
    fidelidade_gasto_minimo = Column(Float, default=0.0)
    fidelidade_resgate = Column(Float, default=0.0)
    fidelidade_elegibilidade = Column(String, default="TODOS")

    # API Keys salvas no banco
    mp_access_token = Column(String, default="")
    mp_public_key = Column(String, default="")
    wa_api_url = Column(String, default="")
    wa_token = Column(String, default="")


# ==========================================
# 2. CLIENTE UNIFICADO
# ==========================================
class ClienteModel(Base):
    __tablename__ = "clientes"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=False)
    telefone = Column(String, unique=True, index=True, nullable=False)
    senha = Column(String, default="")
    senha_hash = Column(String, default="")
    cpf = Column(String, default="", nullable=True)
    data_nascimento = Column(String, default="")
    foto = Column(String, default="")
    bloqueado = Column(Boolean, default=False)
    permite_fiado = Column(Boolean, default=False)
    
    cep = Column(String, default="")
    endereco = Column(String, default="")
    logradouro = Column(String, default="")
    numero = Column(String, default="")
    bairro = Column(String, default="")
    complemento = Column(String, default="")
    
    pontos = Column(Integer, default=0)
    pontos_fidelidade = Column(Integer, default=0)
    cashback = Column(Float, default=0.0)
    saldo_cashback = Column(Float, default=0.0)

Cliente = ClienteModel


# ==========================================
# 3. RECURSOS HUMANOS E CARGOS
# ==========================================
class Cargo(Base):
    __tablename__ = "cargos"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    permissoes = Column(String, default="basico") 


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
    email = Column(String, default="")
    salario = Column(Float, default=0.0)
    escala = Column(String, default="")
    recebe_comissao = Column(Boolean, default=False)
    tipo_comissao = Column(String, default="PERCENTUAL") 
    valor_comissao = Column(Float, default=0.0) 
    valor_vt = Column(Float, default=0.0) 
    valor_va = Column(Float, default=0.0) 
    diaria_motoboy = Column(Float, default=0.0)
    repasse_por_entrega = Column(Float, default=0.0)
    gorjetas_acumuladas = Column(Float, default=0.0)
    escala_matriz_json = Column(String, default="{}") 
    data_nascimento = Column(String, default="")
    naturalidade = Column(String, default="")
    estado_civil = Column(String, default="")
    rg = Column(String, default="")
    cpf = Column(String, default="")
    pis_pasep = Column(String, default="")
    titulo_eleitor = Column(String, default="")
    reservista = Column(String, default="")
    cep = Column(String, default="")
    endereco_completo = Column(String, default="")
    banco = Column(String, default="")
    agencia = Column(String, default="")
    conta = Column(String, default="")
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
    tipo = Column(String, default="FERIAS") 
    data_solicitacao = Column(DateTime, default=datetime.utcnow)
    data_inicio = Column(String)
    data_fim = Column(String)
    status = Column(String, default="PENDENTE") 
    observacao_gestor = Column(String, default="")


# ==========================================
# 4. INSUMOS, PRODUTOS E CARDÁPIO (DECLARADOS ANTES DE SORTEIOS)
# ==========================================
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
    ativo = Column(Boolean, default=True)
    participa_fidelidade = Column(Boolean, default=True)
    ordem = Column(Integer, default=0)

    # Relacionamento para o cálculo do CMV no dashboard
    itens_ficha = relationship("FichaTecnicaModel", backref="produto", cascade="all, delete-orphan")


class FichaTecnicaModel(Base):
    __tablename__ = "fichas_tecnicas"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"))
    insumo_id = Column(Integer, ForeignKey("insumos.id", ondelete="CASCADE"))
    quantidade_necessaria = Column(Float)

    insumo = relationship("InsumoModel")


class GrupoComplementoModel(Base):
    __tablename__ = "grupos_complementos"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"))
    nome = Column(String)
    obrigatorio = Column(Boolean, default=False)
    minimo_opcoes = Column(Integer, default=0)
    maximo_opcoes = Column(Integer, default=1)
    itens = relationship("ItemComplementoModel", backref="grupo", cascade="all, delete-orphan")


class ItemComplementoModel(Base):
    __tablename__ = "itens_complementos"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos_complementos.id", ondelete="CASCADE"))
    nome = Column(String)
    preco_adicional = Column(Float, default=0.0)


# ==========================================
# 5. FORNECEDORES & CONTAS A PAGAR
# ==========================================
class FornecedorModel(Base):
    __tablename__ = "fornecedores"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    nome_fantasia = Column(String, nullable=False)
    cnpj = Column(String, nullable=True)
    telefone = Column(String, nullable=True, default="")
    contato = Column(String, nullable=True, default="")
    categoria = Column(String, default="Geral")
    site_pedidos = Column(String, default="")
    representante_nome = Column(String, default="")
    representante_contato = Column(String, default="")


class ContaPagarModel(Base):
    __tablename__ = "contas_pagar"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    fornecedor_id = Column(Integer, ForeignKey("fornecedores.id", ondelete="SET NULL"), nullable=True)
    descricao = Column(String, nullable=False) 
    valor = Column(Float, nullable=False)
    data_vencimento = Column(Date, nullable=False)
    data_pagamento = Column(DateTime, nullable=True)
    status = Column(String, default="Pendente")
    tipo_despesa = Column(String, default="Empresa")


# ==========================================
# 6. SORTEIOS / NÚMEROS DA SORTE (AGORA DEPOIS DE PRODUTOS)
# ==========================================
class SorteioModel(Base):
    __tablename__ = "sorteios_promocoes"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    premio = Column(String, nullable=False)
    produto_id_obrigatorio = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    ativo = Column(Boolean, default=True)
    pedido_vencedor_id = Column(Integer, nullable=True)
    cliente_vencedor_nome = Column(String, nullable=True)
    cliente_vencedor_telefone = Column(String, nullable=True)
    sorteado_em = Column(DateTime, nullable=True)


# ==========================================
# 7. CUPONS, CAIXA E LOGÍSTICA
# ==========================================
def data_infinita_str():
    return (datetime.utcnow() + timedelta(days=3650)).strftime("%Y-%m-%d")

class CupomModel(Base):
    __tablename__ = "cupons_desconto"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True)
    tipo = Column(String, default="PERCENTUAL") 
    valor = Column(Float, default=0.0)
    desconto_percentual = Column(Float, default=0.0)
    desconto_fixo = Column(Float, default=0.0)
    data_validade = Column(String, default=data_infinita_str, nullable=True) 
    ativo = Column(Boolean, default=True)
    qtd_limite = Column(Integer, nullable=True)
    usos_atuais = Column(Integer, default=0)
    publico_alvo = Column(String, default="todos")
    cpf_exclusivo = Column(String, nullable=True)


class CaixaTurnoModel(Base):
    __tablename__ = "caixa_turnos"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    operador = Column(String, default="Admin")
    data_abertura = Column(String) 
    data_fechamento = Column(String, nullable=True)
    saldo_inicial = Column(Float, default=0.0)
    entradas_saidas = Column(Float, default=0.0)
    total_vendas_dinheiro = Column(Float, default=0.0)
    total_vendas_outros = Column(Float, default=0.0)
    saldo_informado = Column(Float, default=0.0)
    status = Column(String, default="ABERTO")


class TaxaEntregaModel(Base):
    __tablename__ = "taxas_entrega"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    bairro = Column(String, unique=True, index=True)
    taxa = Column(Float, default=0.0)


# ==========================================
# 8. INICIALIZAÇÃO DO BANCO & ESTOQUE
# ==========================================
def inicializar_banco():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        cargo_admin = db.query(Cargo).filter(Cargo.permissoes == "total").first()
        if not cargo_admin:
            cargo_admin = Cargo(nome="Administrador", permissoes="total")
            db.add(cargo_admin)
            db.flush() 

        if not db.query(FuncionarioModel).filter(FuncionarioModel.usuario == "admin").first():
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
            admin = FuncionarioModel(
                nome="Admin Supremo", 
                usuario="admin", 
                senha_hash=pwd_context.hash("admin123"), 
                cargo_id=cargo_admin.id, 
                matricula_cracha="0001"
            )
            db.add(admin)
            
        if not db.query(ConfiguracaoLojaModel).first():
            config_base = ConfiguracaoLojaModel(nome_empresa="Art's Burguer")
            db.add(config_base)
            
        db.commit()
    except Exception as e: 
        print(f"Log Inicialização: {e}", flush=True)
        db.rollback()
    finally:
        db.close()


def processar_baixa_estoque(db, produto_id: int, quantidade_vendida: float):
    fichas = db.query(FichaTecnicaModel).filter(FichaTecnicaModel.produto_id == produto_id).all()
    for f in fichas:
        insumo = db.query(InsumoModel).filter(InsumoModel.id == f.insumo_id).with_for_update().first()
        if insumo: 
            qtd_descontar = f.quantidade_necessaria * quantidade_vendida
            insumo.quantidade_atual = round(insumo.quantidade_atual - qtd_descontar, 4)
    db.commit()
