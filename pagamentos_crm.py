import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Session, relationship

# Importando o motor principal do Art's Burguer
from database import Base, SessionLocal
from vendas_pdv import ClienteModel, PedidoModel, StatusPedido

router_pagamentos = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================================================================
# 1. MODELOS DE BANCO DE DADOS (CRM e Fidelidade)
# ==============================================================================

class FidelidadeModel(Base):
    """Carteira de pontos do cliente."""
    __tablename__ = "fidelidade_pontos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), unique=True, nullable=False)
    pontos_acumulados = Column(Integer, default=0)
    
    # Historico de ultima movimentacao
    ultima_atualizacao = Column(DateTime, default=datetime.utcnow)

class CupomModel(Base):
    """Gerenciador de Cupons de Desconto do Art's Burguer."""
    __tablename__ = "cupons_desconto"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, nullable=False, index=True) # Ex: "ARTS10", "FRETEGRATIS"
    desconto_percentual = Column(Float, default=0.0) # Ex: 10 para 10%
    desconto_fixo = Column(Float, default=0.0)       # Ex: 5.00 para R$ 5 off
    ativo = Column(Boolean, default=True)
    data_validade = Column(DateTime, nullable=False)

# ==============================================================================
# 2. INTEGRAÇÃO DE PAGAMENTO (Mock Gateway PagSeguro/MercadoPago)
# ==============================================================================

def gerar_payload_pix(valor: float, pedido_id: int):
    """
    Simula a comunicação com a API de um banco (como PagSeguro ou MercadoPago)
    para gerar um PIX exclusivo para aquele pedido.
    """
    # Em um cenário real, aqui usaríamos a biblioteca requests para chamar a API do banco.
    # Vamos gerar um código PIX Copia e Cola simulado.
    codigo_transacao_banco = str(uuid.uuid4().hex)[:12].upper()
    pix_copia_e_cola = f"0002012636br.gov.bcb.pix0114+55419999999990204{codigo_transacao_banco}5204000053039865405{valor:.2f}5802BR5912Arts Burguer6018Fazenda Rio Grande62070503***6304ABCD"
    
    return {
        "transacao_id": codigo_transacao_banco,
        "pix_copia_e_cola": pix_copia_e_cola,
        "valor_cobrado": valor,
        "status_pagamento": "AGUARDANDO_PAGAMENTO"
    }

@router_pagamentos.get("/api/pagamento/pix/{pedido_id}")
def cobrar_pedido_pix(pedido_id: int, db: Session = Depends(get_db)):
    """Gera a cobrança PIX para o cliente pagar."""
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        
    # Gera o PIX com o valor exato da comanda
    dados_pix = gerar_payload_pix(valor=pedido.total_pago, pedido_id=pedido.id)
    return dados_pix

# ==============================================================================
# 3. LÓGICA DE NEGÓCIO: CRM E FIDELIDADE
# ==============================================================================

@router_pagamentos.post("/api/crm/pontuar/{pedido_id}")
def creditar_pontos_fidelidade(pedido_id: int, db: Session = Depends(get_db)):
    """
    Regra do Art's Burguer: A cada R$ 1,00 gasto, o cliente ganha 1 Ponto.
    Essa função deve ser chamada quando o pagamento do PIX for confirmado.
    """
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido or not pedido.cliente_id:
        raise HTTPException(status_code=400, detail="Pedido inválido ou sem cliente associado.")

    pontos_ganhos = int(pedido.total_pago) # Arredonda para baixo. Ex: R$ 34,90 = 34 pontos.

    carteira = db.query(FidelidadeModel).filter(FidelidadeModel.cliente_id == pedido.cliente_id).first()
    
    if not carteira:
        # Se é a primeira compra, cria a carteira do cliente
        carteira = FidelidadeModel(cliente_id=pedido.cliente_id, pontos_acumulados=pontos_ganhos)
        db.add(carteira)
    else:
        # Soma os pontos à carteira existente
        carteira.pontos_acumulados += pontos_ganhos
        carteira.ultima_atualizacao = datetime.utcnow()

    db.commit()
    db.refresh(carteira)

    return {
        "mensagem": "Pontos creditados com sucesso!",
        "pontos_ganhos_nesta_compra": pontos_ganhos,
        "saldo_total_cliente": carteira.pontos_acumulados
    }

@router_pagamentos.post("/api/crm/criar_cupom")
def criar_cupom_promocional(codigo: str, desconto_pct: float = 0.0, desconto_fixo: float = 0.0, dias_validade: int = 7, db: Session = Depends(get_db)):
    """Cria um cupom para disparar no Instagram ou WhatsApp."""
    novo_cupom = CupomModel(
        codigo=codigo.upper(),
        desconto_percentual=desconto_pct,
        desconto_fixo=desconto_fixo,
        data_validade=datetime.utcnow() + timedelta(days=dias_validade)
    )
    db.add(novo_cupom)
    db.commit()
    return {"mensagem": f"Cupom {novo_cupom.codigo} ativado com sucesso!"}