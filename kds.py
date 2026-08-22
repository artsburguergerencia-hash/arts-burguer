from datetime import datetime
from database import SessionLocal
from vendas_pdv import PedidoModel, ItemPedidoModel, StatusPedido

# ==============================================================================
# 1. ENGENHARIA DE OPERAÇÃO DA COZINHA (Lógica do KDS)
# ==============================================================================

def obter_fila_kds(db):
    """
    Busca todos os pedidos que estão na fila de produção.
    Retorna apenas os pedidos com status 'Recebido' ou 'Preparando'.
    Ordena por data/hora (o mais antigo aparece primeiro na tela).
    """
    status_visiveis = [StatusPedido.RECEBIDO, StatusPedido.PREPARANDO]
    
    pedidos_fila = (
        db.query(PedidoModel)
        .filter(PedidoModel.status.in_(status_visiveis))
        .order_index(PedidoModel.data_hora.asc())
        .all()
    )
    return pedidos_fila


def avancar_status_kds(db, pedido_id: int):
    """
    Controla o fluxo do painel da cozinha.
    - Se o pedido está 'Recebido', ele vai para 'Preparando' (chapeiro iniciou).
    - Se o pedido está 'Preparando', ele vai para 'Pronto' (vai para o balcão/motoboy).
    """
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    
    if not pedido:
        print(f"❌ Erro: Pedido #{pedido_id} não encontrado.")
        return None

    if pedido.status == StatusPedido.RECEBIDO:
        pedido.status = StatusPedido.PREPARANDO
        print(f"👨‍🍳 Art's Burguer KDS: Pedido #{pedido.id} ENTROU EM PREPARO.")
    elif pedido.status == StatusPedido.PREPARANDO:
        pedido.status = StatusPedido.PRONTO
        print(f"🔔 Art's Burguer KDS: Pedido #{pedido.id} ESTÁ PRONTO para entrega/retirada!")
    else:
        print(f"⚠️ Pedido #{pedido.id} já está com status '{pedido.status}' e não é gerenciado pelo KDS.")

    db.commit()
    db.refresh(pedido)
    return pedido


# ==============================================================================
# 2. RENDERIZADOR DE TELA (Simulador Visual do Monitor da Cozinha)
# ==============================================================================

def atualizar_painel_visual_kds(db):
    """Simula o layout visual que o monitor da cozinha do Art's Burguer exibiria."""
    fila = obter_fila_kds(db)
    
    print("\n" + "="*50)
    print(f"📺 MONITOR DE COZINHA - ART'S BURGUER | {datetime.now().strftime('%H:%M:%S')}")
    print("="*50)
    
    if not fila:
        print("\n        🎉 Cozinha limpa! Nenhum pedido na fila.        \n")
        print("="*50)
        return

    for pedido in fila:
        # Calcula o tempo de espera na fila em minutos
        tempo_espera = int((datetime.utcnow() - pedido.data_hora).total_seconds() / 60)
        
        # Cor visual para destacar se o pedido está apenas recebido ou já em preparo
        alerta_status = "[FOGO 🔥]" if pedido.status == StatusPedido.PREPARANDO else "[FILA ⏳]"
        
        print(f"\n📦 PEDIDO #{pedido.id} | Tipo: {pedido.tipo_pedido} | {alerta_status} ({tempo_espera} min de espera)")
        print("-" * 50)
        
        # Lista os lanches e observações de montagem
        for item in pedido.itens:
            # Puxa o nome do produto através do relacionamento que criamos no PDV
            print(f"  • {item.quantidade}x {item.produto.nome}")
            if item.observacao:
                print(f"    ⚠️ OBS: {item.observacao}")
                
        print("-" * 50)
    print("="*50 + "\n")


# ==============================================================================
# 3. SIMULAÇÃO PRÁTICA DA COZINHA RUSH HOUR
# ==============================================================================
if __name__ == "__main__":
    db_session = SessionLocal()
    
    # 1. Exibe a tela da cozinha com os pedidos que o PDV gerou na etapa anterior
    print("--- Cenário 1: Chapeiro olha para o monitor da cozinha ---")
    atualizar_painel_visual_kds(db_session)
    
    # 2. Chapeiro clica na tela (ou teclado numérico) para iniciar o primeiro pedido
    print("--- Cenário 2: Chapeiro assume o Pedido #1 ---")
    avancar_status_kds(db_session, pedido_id=1)
    
    # Atualiza a tela para ver a mudança
    atualizar_painel_visual_kds(db_session)
    
    # 3. Chapeiro finaliza o Pedido #1 (lanche embalado, pronto para o motoboy)
    print("--- Cenário 3: Pedido #1 finalizado na chapa ---")
    avancar_status_kds(db_session, pedido_id=1)
    
    # O pedido #1 some da tela do KDS, restando apenas os próximos da fila
    atualizar_painel_visual_kds(db_session)
    
    db_session.close()