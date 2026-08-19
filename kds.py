from datetime import datetime
from database import SessionLocal
from vendas_pdv import PedidoModel, ItemPedidoModel, StatusPedido

# ==============================================================================
# 1. ENGENHARIA DE OPERAÇÃO DA COZINHA (Lógica do KDS)
# ==============================================================================

def obter_fila_kds(db):
    """
    Busca todos os pedidos que estão na fila de produção.
    Lógica blindada: Busca tudo no banco e filtra no Python para evitar erros de formato!
    """
    try:
        todos_pedidos = db.query(PedidoModel).all()
        fila = []
        
        for pedido in todos_pedidos:
            # Transforma o status para texto. Assim não dá briga no banco de dados!
            st = str(pedido.status).upper()
            
            # Se o status contiver 'RECEBIDO' ou 'PREPAR', ele vai pra fila!
            if "RECEBIDO" in st or "PREPAR" in st:
                fila.append(pedido)
        
        # Ordena do mais antigo para o mais novo pelo número do ID (Foge do erro de data!)
        fila.sort(key=lambda p: p.id)
        return fila
        
    except Exception as e:
        print(f"❌ Erro KDS (obter_fila): {e}", flush=True)
        return []


def avancar_status_kds(db, pedido_id: int):
    """
    Avança o status do pedido na cozinha de forma segura.
    """
    try:
        pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
        if not pedido:
            return None

        st = str(pedido.status).upper()
        
        if "RECEBIDO" in st:
            # Se estava recebido, vai para PREPARANDO
            pedido.status = StatusPedido.PREPARANDO
            print(f"👨‍🍳 KDS: Pedido #{pedido.id} ENTROU EM PREPARO.", flush=True)
        elif "PREPAR" in st:
            # Se estava preparando, vai para PRONTO
            pedido.status = StatusPedido.PRONTO
            print(f"🔔 KDS: Pedido #{pedido.id} ESTÁ PRONTO!", flush=True)
            
        db.commit()
        db.refresh(pedido)
        return pedido
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erro KDS (avancar_status): {e}", flush=True)
        return None

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
        # Tenta calcular o tempo, mas se a data não existir, não quebra a tela
        try:
            tempo_espera = int((datetime.utcnow() - pedido.data_hora).total_seconds() / 60)
        except:
            tempo_espera = 0
            
        st = str(pedido.status).upper()
        alerta_status = "[FOGO 🔥]" if "PREPAR" in st else "[FILA ⏳]"
        tipo_ped = getattr(pedido, 'tipo_pedido', 'DELIVERY')
        
        print(f"\n📦 PEDIDO #{pedido.id} | Tipo: {tipo_ped} | {alerta_status} ({tempo_espera} min de espera)")
        print("-" * 50)
        
        # Lista os lanches e observações de montagem
        if hasattr(pedido, 'itens'):
            for item in pedido.itens:
                # Tenta pegar o nome do produto
                nome_produto = "Item de Cardápio"
                if hasattr(item, 'produto') and item.produto:
                    nome_produto = getattr(item.produto, 'nome', f"Produto ID {item.produto_id}")
                
                print(f"  • {item.quantidade}x {nome_produto}")
                
                obs = getattr(item, 'observacao', None)
                if obs:
                    print(f"    ⚠️ OBS: {obs}")
                
        print("-" * 50)
    print("="*50 + "\n")


# ==============================================================================
# 3. SIMULAÇÃO PRÁTICA DA COZINHA RUSH HOUR
# ==============================================================================
if __name__ == "__main__":
    db_session = SessionLocal()
    print("--- Cenário 1: Chapeiro olha para o monitor da cozinha ---")
    atualizar_painel_visual_kds(db_session)
    db_session.close()
