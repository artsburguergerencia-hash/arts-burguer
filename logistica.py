from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

# Importando a base do nosso sistema
from database import Base, SessionLocal
from vendas_pdv import PedidoModel, StatusPedido

# ==============================================================================
# 1. MODELOS DO BANCO DE DADOS (Logística e Entregadores)
# ==============================================================================

class MotoboyModel(Base):
    """Cadastro da frota de entregadores."""
    __tablename__ = "motoboys"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=False)
    placa_moto = Column(String, nullable=True)
    ativo = Column(Boolean, default=True)
    
    # Modelo de remuneração (ex: R$ 2,00 fixo + valor por KM, ou taxa integral)
    taxa_fixa_por_entrega = Column(Float, default=0.0)
    
    entregas = relationship("EntregaModel", back_populates="motoboy")


class EntregaModel(Base):
    """Registro de cada corrida feita por um motoboy."""
    __tablename__ = "entregas"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), unique=True, nullable=False)
    motoboy_id = Column(Integer, ForeignKey("motoboys.id"), nullable=False)
    
    distancia_km = Column(Float, default=0.0)
    valor_pago_motoboy = Column(Float, nullable=False) # Comissão/Taxa desta corrida
    
    hora_saida = Column(DateTime, default=datetime.utcnow)
    hora_entrega = Column(DateTime, nullable=True)
    
    pedido = relationship("PedidoModel")
    motoboy = relationship("MotoboyModel", back_populates="entregas")

# ==============================================================================
# 2. LÓGICA DE NEGÓCIO E ROTEIRIZAÇÃO
# ==============================================================================

def calcular_distancia_e_taxa(endereco_cliente: dict):
    """
    Simula a integração com a API do Google Maps ou Waze para roteirização.
    Aqui calculamos a distância entre o Art's Burguer e a casa do cliente.
    """
    # Em um cenário real, enviaríamos o endereço da hamburgueria e do cliente para a API.
    # Exemplo mockado de processamento em Fazenda Rio Grande:
    bairro_cliente = endereco_cliente.get("bairro", "").lower()
    
    # Tabela de contingência/raio de entrega (Mock)
    if bairro_cliente == "centro":
        return {"distancia_km": 1.5, "taxa_cobrada_cliente": 5.00}
    elif bairro_cliente == "eucaliptos":
        return {"distancia_km": 3.2, "taxa_cobrada_cliente": 8.00}
    elif bairro_cliente == "nações":
        return {"distancia_km": 5.0, "taxa_cobrada_cliente": 12.00}
    else:
        # Cálculo genérico para outros bairros via API
        distancia_simulada = 4.5
        taxa_base = 3.00
        taxa_por_km = 1.50
        taxa_final = taxa_base + (distancia_simulada * taxa_por_km)
        return {"distancia_km": distancia_simulada, "taxa_cobrada_cliente": round(taxa_final, 2)}


def despachar_pedido(db, pedido_id: int, motoboy_id: int, distancia_km: float):
    """
    Pega o lanche que está 'Pronto' na cozinha e entrega para o motoboy.
    """
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    motoboy = db.query(MotoboyModel).filter(MotoboyModel.id == motoboy_id).first()
    
    if not pedido or not motoboy:
        print("❌ Erro: Pedido ou Motoboy não encontrado.")
        return False
        
    if pedido.status != StatusPedido.PRONTO:
        print(f"⚠️ O pedido #{pedido.id} ainda não está pronto na cozinha!")
        return False

    # 1. Calcula quanto o motoboy vai ganhar nessa corrida
    # (Pode ser a taxa de entrega integral que o cliente pagou, ou um valor fixo seu)
    valor_comissao = motoboy.taxa_fixa_por_entrega
    if valor_comissao == 0.0:
        valor_comissao = pedido.taxa_entrega # Ele ganha a taxa 100%

    # 2. Cria o registro de logística
    nova_entrega = EntregaModel(
        pedido_id=pedido.id,
        motoboy_id=motoboy.id,
        distancia_km=distancia_km,
        valor_pago_motoboy=valor_comissao
    )
    db.add(nova_entrega)
    
    # 3. Atualiza o status do pedido (isso pode disparar um WhatsApp pro cliente!)
    pedido.status = StatusPedido.EM_ROTA
    
    db.commit()
    db.refresh(nova_entrega)
    print(f"🛵 Pedido #{pedido.id} DESPACHADO! Motoboy: {motoboy.nome} | Comissão: R$ {valor_comissao:.2f}")
    return nova_entrega


def fechar_acerto_motoboy(db, motoboy_id: int):
    """
    Gera o relatório de fim de noite para pagar o motoboy.
    """
    entregas_hoje = db.query(EntregaModel).filter(
        EntregaModel.motoboy_id == motoboy_id,
        EntregaModel.hora_saida >= datetime.utcnow().date() # Corridas do dia atual
    ).all()
    
    total_corridas = len(entregas_hoje)
    valor_total_receber = sum(entrega.valor_pago_motoboy for entrega in entregas_hoje)
    
    print("\n" + "="*40)
    print(f"💸 ACERTO DE MOTOBOY - ID: {motoboy_id}")
    print(f"   Corridas realizadas hoje: {total_corridas}")
    print(f"   Valor a ser pago: R$ {valor_total_receber:.2f}")
    print("="*40 + "\n")
    
    return valor_total_receber

# ==============================================================================
# 3. SIMULAÇÃO DO FLUXO DE DELIVERY
# ==============================================================================
if __name__ == "__main__":
    db_session = SessionLocal()
    
    print("--- 1. Roteirização (Cliente finalizando no App) ---")
    endereco_mock = {"logradouro": "Avenida das Araucárias", "bairro": "Centro"}
    dados_rota = calcular_distancia_e_taxa(endereco_mock)
    print(f"📍 Endereço analisado. Distância: {dados_rota['distancia_km']}km. Taxa calculada: R$ {dados_rota['taxa_cobrada_cliente']:.2f}")
    
    # (Em uma operação real, aqui o cliente faria o pedido pagando essa taxa)
    
    print("\n--- 2. Cadastrando Motoboy da casa ---")
    # Cadastrando motoboy que ganha o valor integral da taxa de entrega
    piloto_1 = MotoboyModel(nome="Carlos Silva", telefone="41999999999", placa_moto="ABC-1234", taxa_fixa_por_entrega=0.0)
    db_session.add(piloto_1)
    db_session.commit()
    
    # (Para o teste do despacho funcionar localmente, precisaríamos de um Pedido ID válido no banco 
    # com status PRONTO, o que normalmente vem do kds.py)
    # despachar_pedido(db_session, pedido_id=1, motoboy_id=piloto_1.id, distancia_km=dados_rota['distancia_km'])
    # fechar_acerto_motoboy(db_session, piloto_1.id)
    
    db_session.close()