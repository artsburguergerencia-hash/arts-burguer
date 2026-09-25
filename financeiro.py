from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
import enum

# Importando a base e os modelos oficiais do database.py (sem duplicar tabelas)
from database import Base, SessionLocal, FornecedorModel, ContaPagarModel

# ==============================================================================
# 1. ENUMS (Status Financeiros)
# ==============================================================================
class StatusConta(str, enum.Enum):
    PENDENTE = "Pendente"
    PAGA = "Paga"
    VENCIDA = "Vencida"
    CANCELADA = "Cancelada"

class StatusCaixa(str, enum.Enum):
    ABERTO = "Aberto"
    FECHADO = "Fechado"

# ==============================================================================
# 2. MODELO DE CAIXA DIÁRIO
# ==============================================================================
class CaixaDiarioModel(Base):
    __tablename__ = "caixa_diario"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    data_abertura = Column(DateTime, default=datetime.utcnow)
    data_fechamento = Column(DateTime, nullable=True)
    saldo_inicial = Column(Float, default=0.0) 
    total_entradas = Column(Float, default=0.0) 
    total_saidas = Column(Float, default=0.0)  
    saldo_final_esperado = Column(Float, default=0.0)
    status = Column(String, default=StatusCaixa.ABERTO)

# ==============================================================================
# 3. FUNÇÕES DE AUTOMAÇÃO FINANCEIRA
# ==============================================================================
def cadastrar_fornecedor(db, nome: str, cnpj: str, telefone: str, categoria: str):
    novo_fornecedor = FornecedorModel(
        nome_fantasia=nome, 
        cnpj=cnpj, 
        telefone=telefone, 
        categoria=categoria
    )
    db.add(novo_fornecedor)
    db.commit()
    db.refresh(novo_fornecedor)
    return novo_fornecedor

def lancar_conta_pagar(db, fornecedor_id: int, descricao: str, valor: float, vencimento: date, tipo_despesa: str = "Empresa"):
    """Cria uma nova conta a pagar classificando como Empresa ou Casa."""
    nova_conta = ContaPagarModel(
        fornecedor_id=fornecedor_id,
        descricao=descricao,
        valor=valor,
        data_vencimento=vencimento,
        status="Pendente",
        tipo_despesa=tipo_despesa
    )
    db.add(nova_conta)
    db.commit()
    db.refresh(nova_conta)
    return nova_conta

def dar_baixa_conta(db, conta_id: int, caixa_id: int = None):
    conta = db.query(ContaPagarModel).filter(ContaPagarModel.id == conta_id).first()
    if not conta or conta.status == "PAGO":
        return False

    conta.status = "PAGO"
    conta.data_pagamento = datetime.utcnow()

    if caixa_id:
        caixa = db.query(CaixaDiarioModel).filter(CaixaDiarioModel.id == caixa_id).first()
        if caixa and caixa.status == StatusCaixa.ABERTO:
            caixa.total_saidas += conta.valor

    db.commit()
    return True

def gerenciar_caixa_diario(db, acao: str, valor_inicial: float = 0.0, caixa_id: int = None):
    if acao == "abrir":
        novo_caixa = CaixaDiarioModel(saldo_inicial=valor_inicial)
        db.add(novo_caixa)
        db.commit()
        db.refresh(novo_caixa)
        return novo_caixa
        
    elif acao == "fechar" and caixa_id:
        caixa = db.query(CaixaDiarioModel).filter(CaixaDiarioModel.id == caixa_id).first()
        if not caixa or caixa.status == StatusCaixa.FECHADO: 
            return None
            
        caixa.saldo_final_esperado = (caixa.saldo_inicial + caixa.total_entradas) - caixa.total_saidas
        caixa.status = StatusCaixa.FECHADO
        caixa.data_fechamento = datetime.utcnow()
        db.commit()
        return caixa
