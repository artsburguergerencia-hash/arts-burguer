import os
from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, 
    Boolean, ForeignKey, Date, DateTime, text
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
    pool_pre_ping=True,      # Evita erro de conexão fechada pelo SSL do Neon
    pool_recycle=300,        # Recicla as conexões a cada 5 min (ideal para o Neon)
    pool_size=5,             # Seguro para o plano gratuito
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 1. CONFIGURAÇÕES DA LOJA
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


# ==========================================
# 2. CLIENTE UNIFICADO (Fim da Guerra dos Clientes!)
# ==========================================
class ClienteModel(Base):
    """Modelo único de clientes: reúne os campos do PDV e do Cardápio."""
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
    
    # Endereço completo unificado
    cep = Column(String, default="")
    endereco = Column(String, default="")
    logradouro = Column(String, default="")
    numero = Column(String, default="")
    bairro = Column(String, default="")
    complemento = Column(String, default="")
    
    # Carteira de fidelidade
    pontos = Column(Integer, default=0)
    pontos_fidelidade = Column(Integer, default=0)
    cashback = Column(Float, default=0.0)
    saldo_cashback = Column(Float, default=0.0)

    # 🚨 ADICIONE ESTA LINHA:
    pedidos = relationship("PedidoModel", back_populates="cliente", lazy="dynamic")

# Alias para compatibilidade: se algum arquivo importar "Cliente", aponta para o mesmo modelo
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
# 4. INSUMOS, PRODUTOS E CARDÁPIO
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


# ==========================================
# 5. CUPONS, CAIXA E LOGÍSTICA
# ==========================================
def data_infinita_str():
    from datetime import timedelta
    return (datetime.utcnow() + timedelta(days=3650)).strftime("%Y-%m-%d")

class CupomModel(Base):
    """Modelo canônico e oficial de cupons de desconto."""
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
    """Modelo canônico e oficial de turnos do PDV."""
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
# 6. INICIALIZAÇÃO DO BANCO
# ==========================================
def inicializar_banco():
    """Garante que as tabelas e dados mestres existam no boot."""
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
    """
    Deduz os insumos da Ficha Técnica com trava pessimista (with_for_update) no PostgreSQL.
    """
    fichas = db.query(FichaTecnicaModel).filter(FichaTecnicaModel.produto_id == produto_id).all()
    for f in fichas:
        insumo = db.query(InsumoModel).filter(InsumoModel.id == f.insumo_id).with_for_update().first()
        if insumo: 
            qtd_descontar = f.quantidade_necessaria * quantidade_vendida
            insumo.quantidade_atual = round(insumo.quantidade_atual - qtd_descontar, 4)
    db.commit()
