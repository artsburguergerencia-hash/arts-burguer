import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Session

# Importamos a base, a sessão e o Cupom oficial do database.py
from database import Base, SessionLocal, CupomModel
from vendas_pdv import ClienteModel, PedidoModel, StatusPedido

router_pagamentos = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================================================================
# 1. MODELOS DE BANCO DE DADOS (Carteira de Fidelidade)
# ==============================================================================
class FidelidadeModel(Base):
    """Carteira de pontos do cliente."""
    __tablename__ = "fidelidade_pontos"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), unique=True, nullable=False)
    pontos_acumulados = Column(Integer, default=0)
    ultima_atualizacao = Column(DateTime, default=datetime.utcnow)


# ==============================================================================
# 2. INTEGRAÇÃO DE PAGAMENTO (Payload Pix Local)
# ==============================================================================
def gerar_payload_pix(valor: float, pedido_id: int):
    """
    Gera o payload de Pix local simulado para contingência.
    """
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
        
    dados_pix = gerar_payload_pix(valor=pedido.total_pago, pedido_id=pedido.id)
    return dados_pix


# ==============================================================================
# 3. LÓGICA DE NEGÓCIO: CRM E FIDELIDADE
# ==============================================================================
@router_pagamentos.post("/api/crm/pontuar/{pedido_id}")
def creditar_pontos_fidelidade(pedido_id: int, db: Session = Depends(get_db)):
    """
    Regra do Art's Burguer: A cada R$ 1,00 gasto, o cliente ganha 1 Ponto.
    """
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido or not pedido.cliente_id:
        raise HTTPException(status_code=400, detail="Pedido inválido ou sem cliente associado.")

    pontos_ganhos = int(pedido.total_pago)

    carteira = db.query(FidelidadeModel).filter(FidelidadeModel.cliente_id == pedido.cliente_id).first()
    
    if not carteira:
        carteira = FidelidadeModel(cliente_id=pedido.cliente_id, pontos_acumulados=pontos_ganhos)
        db.add(carteira)
    else:
        carteira.pontos_acumulados += pontos_ganhos
        carteira.ultima_atualizacao = datetime.utcnow()

    # Sincroniza também no cadastro do cliente unificado
    cliente = db.query(ClienteModel).filter(ClienteModel.id == pedido.cliente_id).first()
    if cliente:
        cliente.pontos = carteira.pontos_acumulados
        cliente.pontos_fidelidade = carteira.pontos_acumulados

    db.commit()
    db.refresh(carteira)

    return {
        "mensagem": "Pontos creditados com sucesso!",
        "pontos_ganhos_nesta_compra": pontos_ganhos,
        "saldo_total_cliente": carteira.pontos_acumulados
    }

@router_pagamentos.post("/api/crm/criar_cupom")
def criar_cupom_promocional(codigo: str, desconto_pct: float = 0.0, desconto_fixo: float = 0.0, dias_validade: int = 7, db: Session = Depends(get_db)):
    """Cria um cupom no padrão unificado."""
    data_val = (datetime.utcnow() + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
    val = desconto_pct if desconto_pct > 0 else desconto_fixo
    tipo = "PERCENTUAL" if desconto_pct > 0 else "VALOR_FIXO"
    
    novo_cupom = CupomModel(
        codigo=codigo.upper(),
        tipo=tipo,
        valor=val,
        desconto_percentual=desconto_pct,
        desconto_fixo=desconto_fixo,
        data_validade=data_val,
        ativo=True
    )
    db.add(novo_cupom)
    db.commit()
    return {"mensagem": f"Cupom {novo_cupom.codigo} ativado com sucesso!"}
