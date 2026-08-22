from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

# Importando as peças do nosso motor
from database import SessionLocal, ProdutoModel
from vendas_pdv import PedidoModel, StatusPedido

# ==============================================================================
# 1. CONFIGURAÇÃO DA API DE RELATÓRIOS
# ==============================================================================
router_dashboard = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================================================================
# 2. INTELIGÊNCIA DE CUSTOS (CMV e Margem de Lucro)
# ==============================================================================

@router_dashboard.get("/api/dashboard/cmv")
def relatorio_custos_e_lucro(db: Session = Depends(get_db)):
    """
    O Raio-X Financeiro: Calcula quanto custa montar cada lanche e o lucro real.
    """
    produtos = db.query(ProdutoModel).filter(ProdutoModel.ativo == 1).all()
    relatorio = []

    for produto in produtos:
        custo_total_producao = 0.0
        
        # O sistema abre a ficha técnica e soma o custo de cada ingrediente
        for item_ficha in produto.itens_ficha:
            # Multiplica a quantidade usada (ex: 40g) pelo custo unitário (ex: R$ 0,04/g)
            custo_ingrediente = item_ficha.quantidade_necessaria * item_ficha.insumo.custo_unitario
            custo_total_producao += custo_ingrediente
            
        lucro_bruto = produto.preco_venda - custo_total_producao
        
        # Prevenção de erro de divisão por zero
        margem_lucro = 0.0
        if produto.preco_venda > 0:
            margem_lucro = (lucro_bruto / produto.preco_venda) * 100

        relatorio.append({
            "lanche": produto.nome,
            "preco_venda": round(produto.preco_venda, 2),
            "custo_montagem": round(custo_total_producao, 2),
            "lucro_reais": round(lucro_bruto, 2),
            "margem_porcentagem": round(margem_lucro, 1)
        })
        
    return relatorio

# ==============================================================================
# 3. MÉTRICAS DE OPERAÇÃO E VENDAS
# ==============================================================================

@router_dashboard.get("/api/dashboard/metricas")
def relatorio_vendas_gerais(db: Session = Depends(get_db)):
    """
    Termômetro do Negócio: Vendas totais e Ticket Médio.
    """
    # Conta apenas pedidos que não foram cancelados
    pedidos_validos = db.query(PedidoModel).filter(PedidoModel.status != StatusPedido.CANCELADO).all()
    
    total_pedidos = len(pedidos_validos)
    faturamento_bruto = sum(pedido.total_pago for pedido in pedidos_validos)
    
    ticket_medio = 0.0
    if total_pedidos > 0:
        ticket_medio = faturamento_bruto / total_pedidos

    return {
        "total_pedidos_realizados": total_pedidos,
        "faturamento_bruto_reais": round(faturamento_bruto, 2),
        "ticket_medio_reais": round(ticket_medio, 2)
    }