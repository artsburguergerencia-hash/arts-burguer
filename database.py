import os
from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, 
    Boolean, ForeignKey, Date, DateTime, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./banco_v5_master_rh.db")

# Ajuste automático de URL para drivers PostgreSQL modernos
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# MODELOS DE DADOS (BANCO DE DADOS)
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


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    telefone = Column(String, unique=True, index=True)
    senha = Column(String, default="")
    pontos = Column(Integer, default=0)
    cashback = Column(Float, default=0.0)
    bloqueado = Column(Boolean, default=False)
    permite_fiado = Column(Boolean, default=False)
    cpf = Column(String, default="")
    data_nascimento = Column(String, default="")
    cep = Column(String, default="")
    endereco = Column(String, default="")
    numero = Column(String, default="")
    bairro = Column(String, default="")
    complemento = Column(String, default="")
    foto = Column(String, default="")


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


class CupomModel(Base):
    __tablename__ = "cupons_desconto"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True)
    tipo = Column(String, default="PERCENTUAL")
    valor = Column(Float, default=0.0)
    desconto_percentual = Column(Float, default=0.0)
    desconto_fixo = Column(Float, default=0.0)
    data_validade = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)


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
# AUTO-MIGRAÇÕES E INICIALIZAÇÃO
# ==========================================

def inicializar_banco():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    colunas_migracao = [
        "ALTER TABLE cupons_desconto ADD COLUMN tipo VARCHAR DEFAULT 'PERCENTUAL';",
        "ALTER TABLE cupons_desconto ADD COLUMN valor FLOAT DEFAULT 0.0;",
        "ALTER TABLE cupons_desconto ADD COLUMN desconto_percentual FLOAT DEFAULT 0.0;",
        "ALTER TABLE cupons_desconto ADD COLUMN desconto_fixo FLOAT DEFAULT 0.0;",
        "ALTER TABLE cupons_desconto ADD COLUMN ativo BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE configuracoes_loja ADD COLUMN nome_empresa VARCHAR DEFAULT 'Art''s Burguer';",
        "ALTER TABLE configuracoes_loja ADD COLUMN cnpj VARCHAR DEFAULT '';",
        "ALTER TABLE configuracoes_loja ADD COLUMN inscricao_estadual VARCHAR DEFAULT '';",
        "ALTER TABLE configuracoes_loja ADD COLUMN horario_funcionamento VARCHAR DEFAULT '';",
        "ALTER TABLE configuracoes_loja ADD COLUMN endereco VARCHAR DEFAULT '';",
        "ALTER TABLE configuracoes_loja ADD COLUMN telefone VARCHAR DEFAULT '';",
        "ALTER TABLE configuracoes_loja ADD COLUMN logo_url VARCHAR DEFAULT '';",
        "ALTER TABLE configuracoes_loja ADD COLUMN aceita_delivery BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE configuracoes_loja ADD COLUMN aceita_retirada BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE configuracoes_loja ADD COLUMN aceite_automatico BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE configuracoes_loja ADD COLUMN tempo_preparo INTEGER DEFAULT 30;",
        "ALTER TABLE configuracoes_loja ADD COLUMN formas_pagamento VARCHAR DEFAULT 'Pix,Dinheiro,Cartão';",
        "ALTER TABLE configuracoes_loja ADD COLUMN sistema_fidelidade VARCHAR DEFAULT 'CASHBACK';",
        "ALTER TABLE configuracoes_loja ADD COLUMN categorias_cardapio VARCHAR DEFAULT 'Burger Artesanal,Bebidas,Porções';",
        "ALTER TABLE configuracoes_loja ADD COLUMN categorias_fornecedor VARCHAR DEFAULT 'Carnes,Hortifruti,Bebidas,Embalagens';",
        "ALTER TABLE configuracoes_loja ADD COLUMN planos_saude_opcoes VARCHAR DEFAULT 'Nenhum,Amil Básico,Bradesco Odonto,Gympass';",
        "ALTER TABLE configuracoes_loja ADD COLUMN regra_acumulo VARCHAR DEFAULT 'POR_PEDIDO';",
        "ALTER TABLE configuracoes_loja ADD COLUMN fidelidade_ganho FLOAT DEFAULT 0.0;",
        "ALTER TABLE configuracoes_loja ADD COLUMN fidelidade_gasto_minimo FLOAT DEFAULT 0.0;",
        "ALTER TABLE configuracoes_loja ADD COLUMN fidelidade_resgate FLOAT DEFAULT 0.0;",
        "ALTER TABLE configuracoes_loja ADD COLUMN fidelidade_elegibilidade VARCHAR DEFAULT 'TODOS';",
        "ALTER TABLE produtos ADD COLUMN ativo BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE produtos ADD COLUMN participa_fidelidade BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE funcionarios ADD COLUMN foto_3x4 VARCHAR DEFAULT '';",
        "ALTER TABLE funcionarios ADD COLUMN matricula_cracha VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN status_admissao VARCHAR DEFAULT 'PENDENTE_PREENCHIMENTO';",
        "ALTER TABLE info_rh ADD COLUMN aceite_lgpd BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE info_rh ADD COLUMN data_aceite_lgpd VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN telefone VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN email VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN salario FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN escala VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN recebe_comissao BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE info_rh ADD COLUMN tipo_comissao VARCHAR DEFAULT 'PERCENTUAL';",
        "ALTER TABLE info_rh ADD COLUMN valor_comissao FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN valor_vt FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN valor_va FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN diaria_motoboy FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN repasse_por_entrega FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN gorjetas_acumuladas FLOAT DEFAULT 0.0;",
        "ALTER TABLE info_rh ADD COLUMN escala_matriz_json VARCHAR DEFAULT '{}';",
        "ALTER TABLE info_rh ADD COLUMN data_nascimento VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN naturalidade VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN estado_civil VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN rg VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN cpf VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN pis_pasep VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN titulo_eleitor VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN reservista VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN cep VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN endereco_completo VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN banco VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN agencia VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN conta VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN dados_bancarios VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN escolaridade VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN qtd_filhos_menores INTEGER DEFAULT 0;",
        "ALTER TABLE info_rh ADD COLUMN cnh VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN plano_saude_escolhido VARCHAR DEFAULT '';",
        "ALTER TABLE info_rh ADD COLUMN link_pasta_documentos VARCHAR DEFAULT '';",
        "ALTER TABLE cargos ADD COLUMN permissoes VARCHAR DEFAULT 'basico';",
        "ALTER TABLE pontos_rh ADD COLUMN horas_trabalhadas FLOAT DEFAULT 0.0;",
        "ALTER TABLE pontos_rh ADD COLUMN horas_extras FLOAT DEFAULT 0.0;",
        "ALTER TABLE ferias_rh ADD COLUMN tipo VARCHAR DEFAULT 'FERIAS';",
        "ALTER TABLE clientes ADD COLUMN permite_fiado BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE clientes ADD COLUMN cpf VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN cep VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN endereco VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN senha VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN data_nascimento VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN numero VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN bairro VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN complemento VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN pontos INTEGER DEFAULT 0;",
        "ALTER TABLE clientes ADD COLUMN cashback FLOAT DEFAULT 0.0;",
        "ALTER TABLE clientes ADD COLUMN bloqueado BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE clientes ADD COLUMN foto VARCHAR DEFAULT '';"
    ]

    try:
        with engine.connect() as conn:
            # Tenta afrouxar o NOT NULL do Postgres se existir
            try:
                conn.execute(text("ALTER TABLE cupons_desconto ALTER COLUMN data_validade DROP NOT NULL;"))
                conn.commit()
            except Exception:
                pass

            for cmd in colunas_migracao:
                try:
                    conn.execute(text(cmd))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"Aviso na inicialização das migrações: {e}")

    try:
        cargo_admin = db.query(Cargo).filter(Cargo.permissoes == "total").first()
        if not cargo_admin:
            cargo_admin = Cargo(nome="Administrador", permissoes="total")
            db.add(cargo_admin)
            db.flush() 

        if not db.query(FuncionarioModel).first():
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
        print(f"Aviso ao verificar dados padrão: {e}")
        db.rollback()
    finally:
        db.close()


def processar_baixa_estoque(db, produto_id: int, quantidade_vendida: float):
    fichas = db.query(FichaTecnicaModel).filter(FichaTecnicaModel.produto_id == produto_id).all()
    for f in fichas:
        insumo = db.query(InsumoModel).filter(InsumoModel.id == f.insumo_id).first()
        if insumo: 
            insumo.quantidade_atual -= (f.quantidade_necessaria * quantidade_vendida)
    db.commit()
