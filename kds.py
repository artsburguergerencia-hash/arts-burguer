from datetime import datetime
from database import SessionLocal

# Importamos com segurança para evitar erros de ciclo
try:
    from vendas_pdv import PedidoModel, ItemPedidoModel
except ImportError:
    pass

# ==============================================================================
# 1. ENGENHARIA DE OPERAÇÃO DA COZINHA (Lógica do KDS)
# ==============================================================================

def obter_fila_kds(db):
    """
    Busca todos os pedidos que estão na fila de produção.
    Retorna apenas os pedidos com status 'RECEBIDO' ou 'EM_PREPARO'.
    Ordena por ID (o mais antigo aparece primeiro na tela).
    """
    # 🚨 CORREÇÃO 1: Usando as palavras exatas que o main.py salva no banco!
    status_visiveis = ["RECEBIDO", "EM_PREPARO"]
    
    try:
        pedidos_fila = (
            db.query(PedidoModel)
            .filter(PedidoModel.status.in_(status_visiveis))
            # 🚨 CORREÇÃO 2: order_by no lugar de order_index, e usando ID para fugir da data inexistente!
            .order_by(PedidoModel.id.asc())
            .all()
        )
        return pedidos_fila
    except Exception as e:
        print(f"❌ Erro ao buscar fila do KDS: {e}", flush=True)
        return []


def avancar_status_kds(db, pedido_id: int):
    """
    Controla o fluxo do painel da cozinha.
    - Se o pedido está 'RECEBIDO', ele vai para 'EM_PREPARO' (chapeiro iniciou).
    - Se o pedido está 'EM_PREPARO', ele vai para 'PRONTO' (vai para o balcão/motoboy).
    """
    try:
        pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
        
        if not pedido:
            print(f"❌ Erro: Pedido #{pedido_id} não encontrado.")
            return None

        # Trabalhando com as strings exatas para não dar conflito
        if pedido.status == "RECEBIDO":
            pedido.status = "EM_PREPARO"
            print(f"👨‍🍳 Art's Burguer KDS: Pedido #{pedido.id} ENTROU EM PREPARO.")
        elif pedido.status == "EM_PREPARO":
            pedido.status = "PRONTO"
            print(f"🔔 Art's Burguer KDS: Pedido #{pedido.id} ESTÁ PRONTO para entrega/retirada!")
        else:
            print(f"⚠️ Pedido #{pedido.id} já está com status '{pedido.status}' e não é gerenciado pelo KDS.")

        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception as e:
        print(f"❌ Erro ao avançar status: {e}", flush=True)
        db.rollback()
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
        # 🚨 CORREÇÃO 3: Proteção caso a data não exista
        try:
            tempo_espera = int((datetime.utcnow() - pedido.data_hora).total_seconds() / 60)
        except:
            tempo_espera = "?" # Se a coluna de data não existir, não quebra a tela!
        
        # Cor visual para destacar se o pedido está apenas recebido ou já em preparo
        alerta_status = "[FOGO 🔥]" if pedido.status == "EM_PREPARO" else "[FILA ⏳]"
        
        # Proteção caso a coluna tipo_pedido não exista
        tipo = getattr(pedido, 'tipo_pedido', 'DELIVERY')
        
        print(f"\n📦 PEDIDO #{pedido.id} | Tipo: {tipo} | {alerta_status} ({tempo_espera} min de espera)")
        print("-" * 50)
        
        # Lista os lanches e observações de montagem
        if hasattr(pedido, 'itens'):
            for item in pedido.itens:
                nome_produto = item.produto.nome if hasattr(item, 'produto') and item.produto else f"Produto ID {item.produto_id}"
                print(f"  • {item.quantidade}x {nome_produto}")
                if getattr(item, 'observacao', None):
                    print(f"    ⚠️ OBS: {item.observacao}")
                
        print("-" * 50)
    print("="*50 + "\n")


# ==============================================================================
# 3. SIMULAÇÃO PRÁTICA DA COZINHA RUSH HOUR
# ==============================================================================
if __name__ == "__main__":
    db_session = SessionLocal()
    
    print("--- Cenário 1: Chapeiro olha para o monitor da cozinha ---")
    atualizar_painel_visual_kds(db_session)
    
    print("--- Cenário 2: Chapeiro assume o Pedido #1 ---")
    avancar_status_kds(db_session, pedido_id=1)
    
    atualizar_painel_visual_kds(db_session)
    
    print("--- Cenário 3: Pedido #1 finalizado na chapa ---")
    avancar_status_kds(db_session, pedido_id=1)
    
    atualizar_painel_visual_kds(db_session)
    
    db_session.close()
