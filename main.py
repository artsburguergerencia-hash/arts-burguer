import os
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Body, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, Response,FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, Column, Integer, String, Float, Boolean, text, DateTime
from passlib.context import CryptContext

# ==========================================
# 1. IMPORTAÇÕES DOS MÓDULOS DE NEGÓCIO
# ==========================================
from integracao_99food import router_99food
from pagamentos_pagbank import (
    criar_pagamento_pix_mp, 
    criar_link_pagamento_mp, 
    criar_pagamento_cartao_mp
)
from vendas_pdv import (
    PedidoModel, 
    ItemPedidoModel, 
    registrar_venda_pdv, 
    TipoPedido,
    StatusPedido
)
from financeiro import (
    FornecedorModel, 
    ContaPagarModel, 
    lancar_conta_pagar
)
from dashboard import router_dashboard
from pagamentos_crm import router_pagamentos
from whatsapp_ia import notificar_status_pedido

# ==========================================
# 2. IMPORTAÇÕES DO BANCO DE DADOS (CANÔNICAS)
# ==========================================
from database import (
    SessionLocal, 
    engine, 
    Base, 
    inicializar_banco, 
    processar_baixa_estoque,
    ConfiguracaoLojaModel, 
    Cargo, 
    FuncionarioModel, 
    InfoRHModel, 
    PontoModel,
    OcorrenciaRHModel, 
    SolicitacaoFeriasModel, 
    InsumoModel, 
    ProdutoModel, 
    FichaTecnicaModel, 
    GrupoComplementoModel, 
    ItemComplementoModel,
    ClienteModel,
    Cliente,
    CupomModel,
    CaixaTurnoModel,
    TaxaEntregaModel,
    data_infinita_str
)

# ==========================================
# 3. SEGURANÇA E AUTENTICAÇÃO JWT
# ==========================================
from auth_security import (
    criar_token_acesso, 
    obter_usuario_logado, 
    exigir_administrador
)

# ==========================================
# 4. CONFIGURAÇÃO DO SERVIDOR FASTAPI
# ==========================================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
app = FastAPI(title="API - Art's Burguer ERP Corporativo V5", version="5.0.0")

# Inicializa banco e tabelas no Neon
inicializar_banco()
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# ROTA DE SAÚDE / KEEP-ALIVE (RENDER & NEON)
# ==========================================
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Rota leve para manter o Render e o Neon sempre aquecidos."""
    try:
        # Testa a conexão com o Neon em milissegundos
        db.execute(text("SELECT 1;"))
        return {"status": "ok", "app": "online", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503, 
            content={"status": "degraded", "erro": str(e)}
        )
        
# Memória temporária única para telemetria de entregadores
POSICOES_MOTOBOYS_AO_VIVO = {}
rastreio_ao_vivo = {}

# ==========================================
# 5. SCHEMAS (MODELOS DE DADOS - PYDANTIC)
# ==========================================
class ItemCompSchema(BaseModel):
    nome: str
    preco_adicional: float

class GrupoCompSchema(BaseModel):
    produto_id: int
    nome: str
    obrigatorio: bool = False
    minimo_opcoes: int = 0
    maximo_opcoes: int = 1
    itens: List[ItemCompSchema]

class ItemCarrinho(BaseModel):
    produto_id: int
    quantidade: int
    observacao: str = ""

class CheckoutPedido(BaseModel):
    telefone_cliente: str
    nome_cliente: str
    itens: List[ItemCarrinho]
    endereco_cliente:str = ""
    cpf: str = ""
    token_cartao: Optional[str] = None
    payment_method_id: Optional[str] = None
    parcelas: Optional[int] = 1

class NovoInsumo(BaseModel):
    nome: str
    unidade: str
    quantidade: float
    minimo: float
    custo: float

class FichaItem(BaseModel):
    insumo_id: int
    quantidade: float

class NovoProduto(BaseModel):
    nome: str
    descricao: str = ""
    preco: float
    categoria: str
    imagem_url: str = ""
    ordem: int = 0
    fichas: List[FichaItem] = []

class CheckoutPDV(BaseModel):
    nome_cliente: str
    telefone_cliente: str = "BALCAO"
    forma_pagamento: str
    itens: List[ItemCarrinho]
    usar_saldo_cashback: float = 0.0
    usar_pontos: bool = False

class NovaConta(BaseModel):
    descricao: str
    valor: float
    vencimento: str 
    tipo_despesa: str = "Empresa"
    fornecedor_id: Optional[int] = None

class DespachoMotoboy(BaseModel):
    nome_motoboy: str    

class AtualizarStatus(BaseModel):
    status: str

class LoginData(BaseModel):
    usuario: str
    senha: str

class NovoFornecedor(BaseModel):
    nome_fantasia: str
    categoria: str = "Geral"
    contato: str = ""
    cnpj: str = ""

class LoginClienteData(BaseModel):
    telefone: str
    senha: str

class RegistroClienteData(BaseModel):
    nome: str
    telefone: str
    senha: str
    cpf: str = ""
    data_nascimento: str = ""
    cep: str = ""
    logradouro: str = ""
    numero: str = ""
    bairro: str = ""
    complemento: str = ""

class NovoCargo(BaseModel):
    nome: str
    permissoes: str = "basico"

class NovoFuncionario(BaseModel):
    nome: str
    usuario: str
    senha: str
    cargo_id: int
    whatsapp: str = ""
    email: str = ""
    cpf: str = ""

class RegistroPonto(BaseModel):
    funcionario_id: int
    tipo: str 

class NovaOcorrencia(BaseModel):
    funcionario_id: int
    data_ocorrencia: str
    tipo: str
    motivo: str
    horas_abonadas: float = 0.0
    horas_descontadas: float = 0.0
    anexo_url: str = ""

class NovaFerias(BaseModel):
    funcionario_id: int
    tipo: str = "FERIAS"
    data_inicio: str
    data_fim: str

class FormularioAdmissao(BaseModel):
    cpf: str = ""
    data_nascimento: str = ""
    naturalidade: str = ""
    estado_civil: str = ""
    rg: str = ""
    pis_pasep: str = ""
    titulo_eleitor: str = ""
    reservista: str = ""
    cep: str = ""
    endereco_completo: str = ""
    banco: str = ""
    agencia: str = ""
    conta: str = ""
    escolaridade: str = ""
    qtd_filhos_menores: int = 0
    cnh: str = ""
    email: str = ""
    plano_saude_escolhido:str = ""
    aceite_lgpd: bool = True
    foto_3x4: str = ""

class AjusteFinanceiroRH(BaseModel):
    salario: float
    recebe_comissao: bool
    tipo_comissao: str
    valor_comissao: float
    valor_vt: float
    valor_va: float
    diaria_motoboy: float
    repasse_por_entrega: float
    escala_matriz_json: str

class CoordenadasGPS(BaseModel):
    pedido_id: int
    lat: float
    lng: float

class TaxaEntregaSchema(BaseModel):
    bairro: str
    taxa: float

class AbrirCaixaSchema(BaseModel):
    operador: str
    saldo_inicial: float

class MovimentacaoCaixaSchema(BaseModel):
    valor: float
    tipo: str
    descricao: str

class FecharCaixaSchema(BaseModel):
    saldo_informado: float

class AtualizarPerfilCliente(BaseModel):
    nome: str
    telefone: str = ""
    cep: str = ""
    endereco: str = ""
    numero: str = ""
    bairro: str = ""
    complemento: str = ""
    senha: str = ""  
    foto: str = ""

class EditarPerfilColaborador(BaseModel):
    nome: str
    telefone: str
    email: str
    cep: str
    endereco_completo: str
    qtd_filhos_menores: int
    foto_3x4: str

class ItemComboSchema(BaseModel):
    nome: str
    preco_adicional: float = 0.0

class EtapaComboSchema(BaseModel):
    nome: str
    obrigatorio: bool = True
    minimo_opcoes: int = 1
    maximo_opcoes: int = 1
    itens: List[ItemComboSchema]

class NovoComboFastFood(BaseModel):
    nome: str
    descricao: str = ""
    preco: float
    imagem_url: str = ""
    categoria: str = "Combos Promocionais"
    etapas: List[EtapaComboSchema]

class ExtItemSchema(BaseModel):
    name: str
    quantity: int
    price: float
    options: Optional[str] = ""

class ExtWebhookSchema(BaseModel):
    displayId: str 
    type: str 
    customerName: str
    customerPhone: str
    deliveryAddress: Optional[str] = "Não informado"
    paymentMethod: str
    totalPrice: float
    items: List[ExtItemSchema]

class ConfirmacaoZerarDados(BaseModel):
    palavra_seguranca: str


# ==========================================
# 6. FUNÇÕES UTILITÁRIAS
# ==========================================
def gerar_senha_diaria(db: Session):
    hoje = datetime.utcnow().date()
    try:
        ultimo = db.query(PedidoModel).order_by(PedidoModel.id.desc()).first()
        if not ultimo: 
            return "001"
        
        data_ultimo = getattr(ultimo, 'data_pedido', None)
        if not data_ultimo:
            dh = getattr(ultimo, 'data_hora', None)
            if dh and hasattr(dh, 'date'): 
                data_ultimo = dh.date()
                
        if data_ultimo == hoje:
            try:
                return str(int(ultimo.senha_diaria) + 1).zfill(3)
            except Exception: 
                return str(ultimo.id + 1).zfill(3)
        else:return "001"
    except Exception: 
        return "001"

def pegar_modelo_banco(tabela: str):
    mapeamento = {
        "insumos": InsumoModel,
        "fornecedores": FornecedorModel,
        "financeiro": ContaPagarModel,
        "funcionarios": FuncionarioModel,
        "cupons": CupomModel,
        "clientes": ClienteModel
    }
    return mapeamento.get(tabela)


# ==========================================
# 7. GESTÃO DE MESAS (SALÃO)
# ==========================================
@app.get("/api/gestao/mesas")
def listar_mesas_ocupadas(db: Session = Depends(get_db)):
    try:
        pedidos_ativos = db.query(PedidoModel).order_by(desc(PedidoModel.id)).all()
        mesas_ocupadas = []
        for p in pedidos_ativos:
            status_atual = str(p.status).split('.')[-1].upper()
            if status_atual in ["ENTREGUE", "CANCELADO", "CONCLUIDO"]:
                continue
                
            nome_cli = p.cliente.nome.upper() if p.cliente else "CLIENTE AVULSO"
            if "MESA" in nome_cli:
                numero = nome_cli.replace("MESA", "").replace("-", "").strip()
                total = getattr(p, 'total_pago', getattr(p, 'subtotal', 0.0))
                mesas_ocupadas.append({
                    "pedido_id": p.id,
                    "numero_mesa": numero,
                    "status": status_atual,
                    "total": float(total)
                })
        return mesas_ocupadas
    except Exception as e:
        print(f"Erro no radar de mesas: {e}")
        return []

@app.get("/mesas", response_class=HTMLResponse)
def abrir_tela_mesas(): 
    if Path("templates/mesas.html").exists():
        return Path("templates/mesas.html").read_text(encoding="utf-8")
    return "Erro: Arquivo mesas.html não encontrado."


# ==========================================
# 8. FORNECEDORES
# ==========================================
@app.get("/api/gestao/fornecedores")
def listar_fornecedores(db: Session = Depends(get_db)):
    fornecedores = db.query(FornecedorModel).all()
    return [{
        "id": f.id, 
        "nome_fantasia": f.nome_fantasia, 
        "categoria": f.categoria, 
        "contato": getattr(f, 'contato', ''), 
        "cnpj": getattr(f, 'cnpj', '')
    } for f in fornecedores]

@app.post("/api/gestao/fornecedores")
def cadastrar_fornecedor(dados: NovoFornecedor, db: Session = Depends(get_db)):
    try:
        cnpj_limpo = dados.cnpj.strip() if dados.cnpj and dados.cnpj.strip() != "" else None
        novo_fornecedor = FornecedorModel(
            nome_fantasia=dados.nome_fantasia,categoria=dados.categoria, 
            contato=dados.contato,
            cnpj=cnpj_limpo
        )
        if hasattr(novo_fornecedor, 'telefone'):
            novo_fornecedor.telefone = dados.contato
            
        db.add(novo_fornecedor)
        db.commit()
        db.refresh(novo_fornecedor)
        return {"status": "sucesso", "id": novo_fornecedor.id, "mensagem": "Fornecedor cadastrado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Falha ao salvar no banco: {str(e)}")

@app.put("/api/fornecedores/{fornecedor_id}")
def atualizar_fornecedor(fornecedor_id: int, dados: dict, db: Session = Depends(get_db)):
    try:
        fornecedor = db.query(FornecedorModel).filter(FornecedorModel.id == fornecedor_id).first()
        if not fornecedor:
            raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
        
        for key, value in dados.items():
            if hasattr(fornecedor, key):
                setattr(fornecedor, key, value)
                
        db.commit()
        return {"status": "sucesso", "mensagem": "Fornecedor atualizado!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/fornecedores/{fornecedor_id}")
def excluir_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    try:
        fornecedor = db.query(FornecedorModel).filter(FornecedorModel.id == fornecedor_id).first()
        if not fornecedor:
            raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
            
        db.delete(fornecedor)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        if "IntegrityError" in str(type(e)) or "Foreign Key" in str(e):
            raise HTTPException(status_code=400, detail="Não é possível excluir: existem contas a pagar vinculadas a este fornecedor.")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


# ==========================================
# 9. CLIENTES & CRM
# ==========================================
@app.post("/api/cliente/registrar")
def cadastrar_novo_cliente(dados: dict = Body(...), db: Session = Depends(get_db)):
    try:
        telefone_cliente = dados.get("telefone")
        if not telefone_cliente:
            raise HTTPException(status_code=400, detail="O telefone é obrigatório.")

        cliente_existente = db.query(ClienteModel).filter(ClienteModel.telefone == telefone_cliente).first()
        if cliente_existente:
            raise HTTPException(status_code=400, detail="Este telefone já está cadastrado. Faça o login.")

        cpf_recebido = dados.get("cpf", "").strip()
        cpf_final = cpf_recebido if cpf_recebido != "" else None

        novo_cliente = ClienteModel(
            nome=dados.get("nome", "Cliente Visitante"),
            telefone=telefone_cliente,
            senha=dados.get("senha", ""),
            cpf=cpf_final,
            data_nascimento=dados.get("data_nascimento", ""),
            cep=dados.get("cep", ""),
            endereco=dados.get("endereco", dados.get("logradouro", "")),
            logradouro=dados.get("logradouro", dados.get("endereco", "")),
            numero=dados.get("numero", ""),
            bairro=dados.get("bairro", ""),
            complemento=dados.get("complemento", ""),
            pontos=0,
            pontos_fidelidade=0,
            cashback=0.0,
            saldo_cashback=0.0,
            bloqueado=False
        )
        
        if "foto" in dados and hasattr(novo_cliente, "foto"):
            novo_cliente.foto = dados["foto"]
        
        db.add(novo_cliente)
        db.commit()
        db.refresh(novo_cliente)
        return {"mensagem": "Conta criada com sucesso!", "cliente_id": novo_cliente.id}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno ao criar conta: {str(e)}")

@app.post("/api/cliente/login")
def login_cliente_cardapio(dados: LoginClienteData, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == dados.telefone).first()
    senha_salva = getattr(cliente, 'senha', None)
    if not cliente or not senha_salva:
        raise HTTPException(status_code=401, detail="Telefone ou senha incorretos.")
        
    senha_valida = False
    try:
        if pwd_context.verify(dados.senha, senha_salva):
            senha_valida = True
    except Exception:
        pass
        
    if dados.senha == senha_salva: 
        senha_valida = True
        
    if not senha_valida:
        raise HTTPException(status_code=401, detail="Telefone ou senha incorretos.")
    
    endereco_formatado = f"{getattr(cliente, 'endereco', '')}, {getattr(cliente, 'numero', '')} - {getattr(cliente, 'bairro', '')} ({getattr(cliente, 'complemento', '')})"
    
    return {
        "status": "sucesso",
        "cliente": {
            "id": cliente.id,
            "nome": cliente.nome or 'Visitante',
            "telefone": cliente.telefone,
            "cpf": getattr(cliente,'cpf', ''),
            "foto": getattr(cliente, 'foto', ''),
            "endereco_completo": endereco_formatado,
            "cep": getattr(cliente, 'cep', ''),
            "endereco": getattr(cliente, 'endereco', ''),
            "numero": getattr(cliente, 'numero', ''),
            "bairro": getattr(cliente, 'bairro', ''),
            "complemento": getattr(cliente, 'complemento', ''),
            "pontos": getattr(cliente, 'pontos', 0),
            "cashback": getattr(cliente, 'cashback', 0.0)
        }
    }

@app.get("/api/cliente/{cliente_id}/pedidos")
def historico_pedidos_cliente(cliente_id: int, db: Session = Depends(get_db)):
    pedidos = db.query(PedidoModel).filter(
        PedidoModel.cliente_id == cliente_id
    ).order_by(desc(PedidoModel.id)).limit(10).all()
    
    historico = []
    for p in pedidos:
        resumo_itens = []
        for item in p.itens:
            prod = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
            nome_prod = prod.nome if prod else "Produto Indisponível"
            resumo_itens.append(f"{item.quantidade}x {nome_prod}")
        
        historico.append({
            "id": p.id,
            "senha_diaria": getattr(p, 'senha_diaria', str(p.id).zfill(3)),
            "status": str(p.status).split('.')[-1].upper(),
            "total": p.total_pago,
            "itens_resumo": ", ".join(resumo_itens)
        })
    return historico

@app.get("/api/gestao/clientes")
def listar_clientes_gestao(db: Session = Depends(get_db)):
    clientes = db.query(ClienteModel).all()
    return [{
        "id": c.id,
        "nome": c.nome or "Visitante",
        "telefone": c.telefone or "Sem Contato",
        "pontos": c.pontos or 0,
        "cashback": c.cashback or 0.0,
        "bloqueado": bool(c.bloqueado),
        "cpf": c.cpf or "",
        "cep": c.cep or "",
        "endereco": c.endereco or "",
        "data_nascimento": c.data_nascimento or "",
        "foto": c.foto or ""
    } for c in clientes]

@app.put("/api/gestao/clientes/{cliente_id}")
def atualizar_dossie_cliente(cliente_id: int, dados: dict = Body(...), db: Session = Depends(get_db)):
    try:
        cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado na base.")
        
        for campo in ["nome", "telefone", "cpf","cep", "endereco", "pontos", "cashback", "bloqueado"]:
            if campo in dados:
                setattr(cliente, campo, dados[campo])
                if campo == "pontos": cliente.pontos_fidelidade = dados[campo]
                if campo == "cashback": cliente.saldo_cashback = dados[campo]
        
        db.commit()
        return {"status": "sucesso", "mensagem": "Dossiê do cliente atualizado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gestao/clientes/{cliente_id}/pedidos")
def historico_pedidos_cliente_gestao(cliente_id: int, db: Session = Depends(get_db)):
    try:
        cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
        if not cliente: return []
        
        pedidos = db.query(PedidoModel).filter(PedidoModel.cliente_id == cliente_id).order_by(PedidoModel.id.desc()).limit(10).all()
        return [{
            "id": p.id,
            "data": getattr(p, "data_hora", None).strftime("%d/%m/%Y %H:%M") if getattr(p, "data_hora", None) else "N/A",
            "valor": getattr(p, "total_pago", 0.0),
            "status": str(getattr(p, "status", "N/A")).split('.')[-1].upper(),
            "pagamento": getattr(p, "forma_pagamento", "Balcão")
        } for p in pedidos]
    except Exception as e:
        print(f"Erro no histórico: {e}")
        return []

@app.put("/api/gestao/clientes/{cliente_id}/editar")
def editar_cliente(cliente_id: int, dados: dict, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente: 
        raise HTTPException(status_code=404)
        
    cliente.nome = dados.get("nome", cliente.nome)
    cliente.telefone = dados.get("telefone", cliente.telefone)
    cliente.pontos = int(dados.get("pontos", cliente.pontos))
    cliente.pontos_fidelidade = cliente.pontos
    cliente.cashback = float(dados.get("cashback", cliente.cashback))
    cliente.saldo_cashback = cliente.cashback
    
    db.commit()
    return {"status": "sucesso"}

@app.put("/api/gestao/clientes/{cliente_id}/bloqueio")
def alternar_bloqueio_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente: 
        raise HTTPException(status_code=404)
        
    cliente.bloqueado = not getattr(cliente, 'bloqueado', False)
    db.commit()
    return {"status": "sucesso", "bloqueado": cliente.bloqueado}

@app.delete("/api/gestao/clientes/{cliente_id}")
def deletar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    try:
        cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
        if not cliente: 
            raise HTTPException(status_code=404)
            
        db.query(PedidoModel).filter(PedidoModel.cliente_id == cliente_id).update({"cliente_id": None})
        db.execute(text("DELETE FROM fidelidade_pontos WHERE cliente_id = :id"), {"id": cliente_id})
        db.delete(cliente)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cliente/{cliente_id}/perfil")
def obter_perfil_cliente(cliente_id: int, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not c: raise HTTPException(status_code=404)
    return {
        "nome": c.nome, 
        "telefone": c.telefone,
        "cep": getattr(c, 'cep', ''), 
        "endereco": getattr(c, 'endereco', ''),
        "numero": getattr(c, 'numero', ''), 
        "bairro": getattr(c, 'bairro', ''), 
        "complemento": getattr(c, 'complemento', '')
    }

@app.put("/api/cliente/{cliente_id}/perfil")
def atualizar_perfil_cliente(cliente_id: int, dados: AtualizarPerfilCliente, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not c: raise HTTPException(status_code=404)
        
    c.nome = dados.nome
    if dados.telefone and dados.telefone.strip() != "":
        c.telefone = dados.telefone.strip()
        
    c.cep = dados.cep
    c.endereco = dados.endereco
    c.numero = dados.numero
    if dados.bairro: c.bairro = dados.bairro
    c.complemento = dados.complemento
    
    if dados.senha and dados.senha.strip() != "":
        c.senha = dados.senha.strip()
    if dados.foto and dados.foto.strip() != "":
        c.foto = dados.foto
    
    db.commit()
    return {"status": "sucesso"}

@app.put("/api/gestao/clientes/{cliente_id}/fiado")
def alternar_fiado_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente: 
        raise HTTPException(status_code=404)
        
    cliente.permite_fiado = not getattr(cliente, 'permite_fiado', False)
    db.commit()
    return {"status": "sucesso"}


# ==========================================
# 10. WEBHOOKS DE PAGAMENTO
# ==========================================
@app.post("/api/webhooks/mercadopago")
async def webhook_mercadopago(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        return {"status": "ok"}
    except Exception:
        return {"status": "erro"}

@app.post("/api/webhooks/asaas")
async def webhook_do_asaas(payload: dict, db: Session = Depends(get_db)):
    try:
        evento = payload.get("event")
        if evento in ["PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"]:
            pagamento = payload.get("payment", {})
            descricao = pagamento.get("description", "")
            if "#" in descricao:
                pedido_id_str = descricao.split("#")[1].split(" ")[0]
                pedido = db.query(PedidoModel).filter(PedidoModel.id == int(pedido_id_str)).first()
                if pedido and str(pedido.status).split('.')[-1].upper() != "RECEBIDO":
                    pedido.status = "RECEBIDO" 
                    db.commit()
        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Erro Webhook Asaas: {e}")
        return {"status": "erro"}


# ==========================================
# 11. CHECKOUT & VENDAS (ONLINE E PDV)
# ==========================================
@app.post("/api/pedidos/online")
def receber_pedido_site(pedido_web: CheckoutPedido, forma_pagamento: str = Query("entrega"), db: Session = Depends(get_db)):
    try:
        config = db.query(ConfiguracaoLojaModel).first()
        cliente = db.query(ClienteModel).filter(ClienteModel.telefone == pedido_web.telefone_cliente).first()
        
        if not cliente:
            cliente = ClienteModel(
                nome=pedido_web.nome_cliente, 
                telefone=pedido_web.telefone_cliente
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
            
        itens_carrinho = [{"produto_id": i.produto_id, "quantidade": i.quantidade, "observacao": i.observacao} for i in pedido_web.itens]
        
        if getattr(pedido_web, 'endereco_cliente', None) and len(itens_carrinho) > 0:
            obs_atual = itens_carrinho[0].get("observacao", "") or ""
            itens_carrinho[0]["observacao"] = f"Endereço: {pedido_web.endereco_cliente} | {obs_atual}"

        novo_pedido = registrar_venda_pdv(
            db=db, 
            tipo=TipoPedido.DELIVERY, 
            itens_carrinho=itens_carrinho, 
            cliente_id=cliente.id
        )

        novo_pedido_real = db.query(PedidoModel).filter(PedidoModel.id == novo_pedido.id).first()
        if novo_pedido_real:
            novo_pedido_real.senha_diaria = gerar_senha_diaria(db)
            novo_pedido_real.origem = "SITE (Online)"
            db.commit()

        aceite_auto = getattr(config, 'aceite_automatico', False) if config else False

        if forma_pagamento in ["pix", "credito", "vr"]:
            if novo_pedido_real:
                novo_pedido_real.status = "AGUARDANDO_PAGAMENTO"
                db.commit()
        else:
            if novo_pedido_real:
                novo_pedido_real.status = "EM_PREPARO" if aceite_auto else "RECEBIDO"
                db.commit()
            try:
                notificar_status_pedido(cliente.telefone, cliente.nome, novo_pedido_real.senha_diaria, novo_pedido_real.status)
            except Exception as err_wpp:
                print(f"WhatsApp ignorado: {err_wpp}", flush=True)

        if forma_pagamento == "pix":
            if not getattr(pedido_web, 'cpf', None):
                raise HTTPException(status_code=400, detail="CPF é obrigatório para gerar o Pix.")
            
            valor_pagar = getattr(novo_pedido_real, 'total_pago', getattr(novo_pedido_real, 'subtotal', 0))
            resultado_pix = criar_pagamento_pix_mp(novo_pedido_real.id, float(valor_pagar), cliente.nome, pedido_web.cpf)
            
            if isinstance(resultado_pix, dict) and "qr_code" in resultado_pix:
                return {"status": "checkout_transparente", "copia_e_cola": resultado_pix["qr_code"], "senha_diaria": novo_pedido_real.senha_diaria}
            else:
                if novo_pedido_real:
                    novo_pedido_real.status = "CANCELADO"
                    db.commit()
                erro_msg = resultado_pix.get("erro", "Recusado pelo MP") if isinstance(resultado_pix, dict) else "Recusado"
                raise HTTPException(status_code=400, detail=f"Mercado Pago recusou: {erro_msg}")
                
        elif forma_pagamento == "credito" or forma_pagamento == "vr":
            if not getattr(pedido_web, 'token_cartao', None) or not getattr(pedido_web, 'cpf', None):
                raise HTTPException(status_code=400, detail="Faltam dados do cartão ou CPF.")
                
            valor_pagar = getattr(novo_pedido_real, 'total_pago', getattr(novo_pedido_real, 'subtotal', 0))
            resposta_pagamento = criar_pagamento_cartao_mp(
                pedido_id=novo_pedido_real.id, 
                valor_total=float(valor_pagar), 
                token_cartao=pedido_web.token_cartao, 
                email_cliente=f"cliente{cliente.id}@artsburguer.com",
                payment_method_id=getattr(pedido_web, 'payment_method_id', "master"), 
                parcelas=getattr(pedido_web, 'parcelas', 1), 
                cpf_cliente=pedido_web.cpf
            )
            
            if resposta_pagamento and isinstance(resposta_pagamento, dict) and resposta_pagamento.get("status") in ["approved", "in_process"]:
                if novo_pedido_real:
                    novo_pedido_real.status = "EM_PREPARO" if aceite_auto else "RECEBIDO"
                    db.commit()
                try:
                    notificar_status_pedido(cliente.telefone, cliente.nome, novo_pedido_real.senha_diaria, novo_pedido_real.status)
                except Exception:
                    pass
                return {"status": "sucesso", "mensagem": "Pagamento aprovado!", "senha_diaria": novo_pedido_real.senha_diaria}
            else:
                if novo_pedido_real:
                    novo_pedido_real.status = "CANCELADO"
                    db.commit()
                raise HTTPException(status_code=400, detail="Pagamento recusado pelo banco emissor.")
                
        return {"status": "entrega", "mensagem": "Pedido confirmado para pagamento na entrega!", "senha_diaria": novo_pedido_real.senha_diaria}
        
    except HTTPException:
        raise
    except Exception as global_e:
        print(f"ERRO CRÍTICO NO CHECKOUT: {global_e}", flush=True)
        raise HTTPException(status_code=400, detail=f"Falha ao registrar pedido: {str(global_e)}")

@app.get("/api/pdv/cliente/{telefone}")
def buscar_cliente_pdv(telefone: str, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == telefone).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    return {
        "nome": cliente.nome,
        "pontos": getattr(cliente, 'pontos', 0),
        "cashback": getattr(cliente, 'cashback', 0.0),
        "bloqueado": getattr(cliente, 'bloqueado', False),
        "permite_fiado": getattr(cliente, 'permite_fiado', False) 
    }

@app.post("/api/pedidos/pdv")
def receber_pedido_balcao(pedido_caixa: CheckoutPDV, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == pedido_caixa.telefone_cliente).first()
    if not cliente:
        cliente = ClienteModel(nome=pedido_caixa.nome_cliente, telefone=pedido_caixa.telefone_cliente)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    if getattr(cliente, 'bloqueado', False):
        raise HTTPException(status_code=403, detail="⚠️ Cliente está bloqueado por inadimplência!")

    itens_carrinho = [{"produto_id": i.produto_id, "quantidade": i.quantidade, "observacao": i.observacao} for i in pedido_caixa.itens]
    
    try:
        novo_pedido = registrar_venda_pdv(
            db=db, 
            tipo=TipoPedido.BALCAO, 
            itens_carrinho=itens_carrinho, 
            cliente_id=cliente.id
        )
        
        novo_pedido_real = db.query(PedidoModel).filter(PedidoModel.id == novo_pedido.id).first()
        novo_pedido_real.senha_diaria = gerar_senha_diaria(db)
        novo_pedido_real.origem = "PDV (Balcão)"
        novo_pedido_real.forma_pagamento = pedido_caixa.forma_pagamento
        
        config = db.query(ConfiguracaoLojaModel).first()
        
        if cliente.telefone != "BALCAO":
            sis_fidelidade = getattr(config, 'sistema_fidelidade', 'CASHBACK')
            if sis_fidelidade == "PONTOS":
                if pedido_caixa.usar_pontos and getattr(cliente, 'pontos', 0) >= 10:
                    cliente.pontos -= 10
                    cliente.pontos_fidelidade = cliente.pontos
                else:
                    cliente.pontos = getattr(cliente, 'pontos', 0) + 1 
                    cliente.pontos_fidelidade = cliente.pontos
            elif sis_fidelidade == "CASHBACK":
                saldo_atual = getattr(cliente, 'cashback', 0.0)
                if pedido_caixa.usar_saldo_cashback > 0 and saldo_atual >= pedido_caixa.usar_saldo_cashback:
                    cliente.cashback -= pedido_caixa.usar_saldo_cashback
                    cliente.saldo_cashback = cliente.cashback
                
                valor_real_pago = novo_pedido_real.total_pago - pedido_caixa.usar_saldo_cashback
                if valor_real_pago > 0:
                    ganho = (valor_real_pago * 0.05)
                    cliente.cashback = getattr(cliente, 'cashback', 0.0) + ganho
                    cliente.saldo_cashback = cliente.cashback

        db.commit()
        return {
            "status": "sucesso", 
            "pedido_id": novo_pedido.id, 
            "senha_diaria": novo_pedido_real.senha_diaria
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro no PDV: {str(e)}")


# ==========================================
# 12. RH & DEPARTAMENTO PESSOAL
# ==========================================
@app.get("/api/gestao/cargos")
def listar_cargos(db: Session = Depends(get_db)):
    return db.query(Cargo).all()

@app.post("/api/gestao/cargos")
def criar_cargo_dinamico(dados: NovoCargo, db: Session = Depends(get_db)):
    cargo_existente = db.query(Cargo).filter(Cargo.nome == dados.nome).first()
    if cargo_existente:
        raise HTTPException(status_code=400, detail="Este cargo já existe na empresa.")
    
    novo_cargo = Cargo(nome=dados.nome, permissoes=dados.permissoes)
    db.add(novo_cargo)
    db.commit()
    return {"status": "sucesso", "mensagem":"Cargo criado com sucesso e disponível para uso."}

@app.get("/api/gestao/funcionarios")
def listar_funcionarios_rh(db: Session = Depends(get_db)):
    funcionarios = db.query(FuncionarioModel).all()
    hoje = datetime.utcnow().date().strftime("%Y-%m-%d")
    lista = []
    
    for f in funcionarios:
        cargo = db.query(Cargo).filter(Cargo.id == f.cargo_id).first()
        rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == f.id).first()
        ponto_hoje = db.query(PontoModel).filter(PontoModel.funcionario_id == f.id, PontoModel.data == hoje).first()
        
        lista.append({
            "id": f.id, 
            "nome": f.nome, 
            "usuario": f.usuario,
            "cargo": cargo.nome if cargo else "Sem Cargo", 
            "permissoes": cargo.permissoes if cargo else "basico",
            "cargo_id": f.cargo_id,
            "matricula": f.matricula_cracha,
            "status_admissao": rh.status_admissao if rh else "DESCONHECIDO",
            "telefone": rh.telefone if rh else "", 
            "email": rh.email if rh else "",
            "cpf": rh.cpf if rh else "",
            "foto_3x4": f.foto_3x4 if f.foto_3x4 else "",
            "salario": rh.salario if rh else 0.0,
            "escala": rh.escala if rh else "", 
            "ponto_entrada": ponto_hoje.entrada if ponto_hoje else "",
            "ponto_saida": ponto_hoje.saida if ponto_hoje else ""
        })
    return lista

@app.post("/api/gestao/funcionarios")
def cadastrar_funcionario_base(dados: NovoFuncionario, db: Session = Depends(get_db)):
    try:
        existe = db.query(FuncionarioModel).filter(FuncionarioModel.usuario == dados.usuario).first()
        if existe:
            raise HTTPException(status_code=400, detail="Usuário de sistema já em uso.")
            
        novo_func = FuncionarioModel(
            nome=dados.nome, 
            usuario=dados.usuario, 
            senha_hash=pwd_context.hash(dados.senha), 
            cargo_id=dados.cargo_id
        )
        db.add(novo_func)
        db.flush() 
        
        novo_func.matricula_cracha = f"ART-{novo_func.id:04d}"
        info_rh = InfoRHModel(
            funcionario_id=novo_func.id, 
            telefone=dados.whatsapp, 
            email=dados.email,
            cpf=dados.cpf,
            status_admissao="PENDENTE_PREENCHIMENTO" 
        )
        db.add(info_rh)
        db.commit()
        return {"status": "sucesso", "mensagem": f"Pré-Cadastro criado! Matrícula: {novo_func.matricula_cracha}."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/gestao/funcionarios/{func_id}")
def atualizar_funcionario_basico(func_id: int, dados: dict, db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not func:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
        
    if 'nome' in dados and dados['nome']: func.nome = dados['nome']
    if 'matricula' in dados: func.matricula_cracha = dados['matricula']
    if 'cargo_id' in dados and dados['cargo_id'] is not None:
        try: func.cargo_id = int(dados['cargo_id'])
        except ValueError: pass
    if 'senha' in dados and dados['senha'] and dados['senha'].strip() != "":
        func.senha_hash = pwd_context.hash(dados['senha'].strip())
        
    db.commit()
    db.refresh(func)
    return {"status": "sucesso", "mensagem": "Colaborador atualizado!"}

@app.put("/api/gestao/funcionarios/admissao")
def preencher_form_admissao(dados: FormularioAdmissao, db: Session = Depends(get_db)):
    try:
        rh = db.query(InfoRHModel).filter(InfoRHModel.cpf == dados.cpf).first()
        if not rh:
            raise HTTPException(status_code=404, detail="CPF não encontrado. Solicite o cadastro no RH.")
            
        if rh.status_admissao == "ATIVO":
            raise HTTPException(status_code=400, detail="Sua admissão já foi concluída!")

        rh.data_nascimento = dados.data_nascimento
        rh.naturalidade = dados.naturalidade
        rh.estado_civil = dados.estado_civil
        rh.rg = dados.rg
        rh.pis_pasep = dados.pis_pasep
        rh.titulo_eleitor = dados.titulo_eleitor
        rh.reservista = dados.reservista
        rh.cep = dados.cep
        rh.endereco_completo = dados.endereco_completo
        rh.banco = dados.banco
        rh.agencia = dados.agencia
        rh.conta = dados.conta
        rh.escolaridade = dados.escolaridade
        rh.qtd_filhos_menores = dados.qtd_filhos_menores
        rh.cnh = dados.cnh
        rh.email = dados.email
        rh.plano_saude_escolhido = dados.plano_saude_escolhido
        rh.aceite_lgpd = dados.aceite_lgpd
        rh.data_aceite_lgpd = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
        rh.status_admissao = "ATIVO" 

        func = db.query(FuncionarioModel).filter(FuncionarioModel.id == rh.funcionario_id).first()
        if func:
            func.foto_3x4 = dados.foto_3x4
            
        db.commit()
        return {"status": "sucesso", "mensagem": "Admissão oficial concluída com sucesso! Bem-vindo(a) à equipe."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gestao/funcionarios/{func_id}/dossie")
def obter_dossie_rh(func_id: int, db: Session = Depends(get_db)):
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not rh:
        raise HTTPException(status_code=404, detail="Dossiê não encontrado.")
    return {
        "cpf": rh.cpf,
        "rg": rh.rg,
        "pis_pasep": rh.pis_pasep,
        "data_nascimento": rh.data_nascimento,
        "estado_civil": rh.estado_civil,
        "titulo_eleitor": rh.titulo_eleitor,
        "reservista": rh.reservista,
        "cep": rh.cep,
        "endereco_completo": rh.endereco_completo,
        "banco": rh.banco,
        "agencia": rh.agencia,
        "conta": rh.conta,
        "naturalidade": rh.naturalidade,
        "escolaridade": rh.escolaridade,
        "qtd_filhos_menores": rh.qtd_filhos_menores,
        "cnh": rh.cnh,
        "email": rh.email,
        "plano_saude_escolhido": rh.plano_saude_escolhido,
        "salario": rh.salario,
        "recebe_comissao": rh.recebe_comissao,
        "tipo_comissao": rh.tipo_comissao,
        "valor_comissao": rh.valor_comissao,
        "valor_vt": rh.valor_vt,
        "valor_va": rh.valor_va,
        "diaria_motoboy": rh.diaria_motoboy,
        "repasse_por_entrega": rh.repasse_por_entrega,
        "escala_matriz_json": rh.escala_matriz_json,
        "foto_3x4": func.foto_3x4 if func else ""
    }

@app.put("/api/gestao/funcionarios/{func_id}/dossie")
def atualizar_dossie_rh(func_id: int, dados: FormularioAdmissao, db: Session = Depends(get_db)):
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not rh:
        raise HTTPException(status_code=404)
        
    for campo in [
        "cpf", "rg", "pis_pasep", "data_nascimento", "estado_civil", "titulo_eleitor",
        "reservista", "cep", "endereco_completo", "banco", "agencia", "conta",
        "naturalidade", "escolaridade", "qtd_filhos_menores", "cnh", "email", "plano_saude_escolhido"
    ]:
        setattr(rh, campo, getattr(dados, campo))
        
    if func:
        func.foto_3x4 = dados.foto_3x4
    if rh.status_admissao == "PENDENTE_PREENCHIMENTO":
        rh.status_admissao = "ATIVO"
        
    db.commit()
    return {"status": "sucesso", "mensagem": "Documentos do Dossiê atualizados com sucesso."}

@app.put("/api/gestao/funcionarios/{func_id}/financeiro")
def atualizar_financeiro_rh(func_id: int, dados: AjusteFinanceiroRH, db: Session = Depends(get_db)):
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    if not rh:
        raise HTTPException(status_code=404)
    
    rh.salario = dados.salario
    rh.recebe_comissao = dados.recebe_comissao
    rh.tipo_comissao = dados.tipo_comissao
    rh.valor_comissao = dados.valor_comissao
    rh.valor_vt = dados.valor_vt
    rh.valor_va = dados.valor_va
    rh.diaria_motoboy = dados.diaria_motoboy
    rh.repasse_por_entrega = dados.repasse_por_entrega
    rh.escala_matriz_json = dados.escala_matriz_json
    
    db.commit()
    return {"status": "sucesso", "mensagem": "Configurações de Remuneração e Escala salvas com sucesso."}

@app.delete("/api/gestao/funcionarios/{func_id}")
def demitir_funcionario(func_id: int, db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not func: 
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
        
    cargo = db.query(Cargo).filter(Cargo.id == func.cargo_id).first()
    if cargo and cargo.permissoes == "total": 
        raise HTTPException(status_code=403, detail="Não é possível demitir o Administrador Supremo.")
        
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    if rh: 
        rh.status_admissao = "DEMITIDO"
    else:
        novo_rh = InfoRHModel(funcionario_id=func_id, status_admissao="DEMITIDO")
        db.add(novo_rh)
        
    func.senha_hash = "REVOGADO" 
    db.commit()
    return {"status": "sucesso", "mensagem": "Acesso revogado com sucesso."}

@app.delete("/api/gestao/funcionarios/{func_id}/excluir")
def excluir_funcionario_definitivo(func_id: int, db: Session = Depends(get_db)):
    try:
        func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
        if not func:
            raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
            
        db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).delete()
        db.query(PontoModel).filter(PontoModel.funcionario_id == func_id).delete()
        db.query(OcorrenciaRHModel).filter(OcorrenciaRHModel.funcionario_id == func_id).delete()
        db.query(SolicitacaoFeriasModel).filter(SolicitacaoFeriasModel.funcionario_id == func_id).delete()
        db.delete(func)
        db.commit()
        return {"status": "sucesso", "mensagem": "Funcionário apagado do sistema."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/gestao/funcionarios/{func_id}/readmitir")
def readmitir_funcionario(func_id: int, senha_nova: str = Query(...), db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not func:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    if rh:
        rh.status_admissao = "ATIVO"
    else:
        novo_rh = InfoRHModel(funcionario_id=func_id, status_admissao="ATIVO")
        db.add(novo_rh)
    func.senha_hash = pwd_context.hash(senha_nova)
    db.commit()
    return {"status": "sucesso", "mensagem": "Funcionário readmitido com sucesso!"}

@app.post("/api/gestao/ponto")
def bater_ponto_rh(dados: RegistroPonto, db: Session = Depends(get_db)):
    hoje = datetime.utcnow().date().strftime("%Y-%m-%d")
    hora = datetime.utcnow().strftime("%H:%M")
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == dados.funcionario_id).first()
    if not rh or rh.status_admissao != "ATIVO":
        return {"status": "erro", "detail": "Acesso negado. Funcionário pendente ou demitido."}
        
    ponto = db.query(PontoModel).filter(
        PontoModel.funcionario_id == dados.funcionario_id,
        PontoModel.data == hoje
    ).first()
    if not ponto:
        ponto = PontoModel(funcionario_id=dados.funcionario_id, data=hoje)
        db.add(ponto)
        db.flush()
        
    if dados.tipo == "entrada":
        if ponto.entrada:
            return {"status": "erro", "detail": "Entrada já registrada no sistema."}
        ponto.entrada = hora
    else:
        if not ponto.entrada:
            return {"status": "erro", "detail": "Bata a Entrada antes de registrar a saída."}
        if ponto.saida:
            return {"status": "erro", "detail": "Saída já registrada no sistema."}
        ponto.saida = hora
        fmt = "%H:%M"
        try:
            t1 = datetime.strptime(ponto.entrada, fmt)
            t2 = datetime.strptime(ponto.saida, fmt)
            ponto.horas_trabalhadas = round((t2 - t1).total_seconds() / 3600.0, 2)
        except Exception:
            pass
            
    db.commit()
    return {"status": "sucesso", "mensagem": f"Ponto de {dados.tipo.upper()} registrado com sucesso às {hora}!"}
    
@app.post("/api/gestao/rh/ocorrencias")
def registrar_ocorrencia(dados: NovaOcorrencia, db: Session = Depends(get_db)):
    try:
        nova_oc = OcorrenciaRHModel(
            funcionario_id=dados.funcionario_id,
            data_ocorrencia=dados.data_ocorrencia, 
            tipo=dados.tipo, 
            motivo=dados.motivo, 
            horas_abonadas=dados.horas_abonadas, 
            horas_descontadas=dados.horas_descontadas, 
            anexo_url=dados.anexo_url
        )
        db.add(nova_oc)
        db.commit()
        return {"status": "sucesso", "mensagem": "Ocorrência registrada no sistema de RH."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gestao/rh/ferias")
def solicitar_ferias(dados: NovaFerias, db: Session = Depends(get_db)):
    try:
        nova_solicitacao = SolicitacaoFeriasModel(
            funcionario_id=dados.funcionario_id, 
            tipo=dados.tipo,
            data_inicio=dados.data_inicio, 
            data_fim=dados.data_fim, 
            status="PENDENTE"
        )
        db.add(nova_solicitacao)
        db.commit()
        return {"status": "sucesso", "mensagem": "Solicitação enviada para aprovação do Gestor."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gestao/rh/solicitacoes")
def listar_solicitacoes_rh(db: Session = Depends(get_db)):
    ferias = db.query(SolicitacaoFeriasModel).all()
    ocorrencias = db.query(OcorrenciaRHModel).filter(OcorrenciaRHModel.anexo_url != "").all()
    resultado = []
    
    for f in ferias:
        func = db.query(FuncionarioModel).filter(FuncionarioModel.id == f.funcionario_id).first()
        resultado.append({
            "id": f.id, 
            "tipo_req": f.tipo, 
            "funcionario": func.nome if func else "Colaborador Desconhecido",
            "data_inicio": f.data_inicio, 
            "data_fim": f.data_fim, 
            "status": f.status, 
            "categoria": "FERIAS_FOLGA"
        })
        
    for o in ocorrencias:
        func = db.query(FuncionarioModel).filter(FuncionarioModel.id == o.funcionario_id).first()
        resultado.append({
            "id": o.id, 
            "tipo_req": o.tipo, 
            "funcionario": func.nome if func else "Colaborador Desconhecido",
            "data_inicio": o.data_ocorrencia, 
            "data_fim": o.data_ocorrencia, 
            "status": "REGISTRADO", 
            "motivo": o.motivo, 
            "anexo": o.anexo_url, 
            "categoria": "OCORRENCIA"
        })
    return resultado

@app.put("/api/gestao/rh/ferias/{id_ferias}")
def aprovar_rejeitar_ferias(id_ferias: int, status: str, observacao: str = "", db: Session = Depends(get_db)):
    ferias = db.query(SolicitacaoFeriasModel).filter(SolicitacaoFeriasModel.id == id_ferias).first()
    if not ferias:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
        
    ferias.status = status.upper()
    ferias.observacao_gestor = observacao
    db.commit()
    return {"status": "sucesso"}

@app.get("/api/gestao/rh/colaborador/{func_id}/holerite/{mes_ano}")
def gerar_holerite_dinamico(func_id: int, mes_ano: str, db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    config = db.query(ConfiguracaoLojaModel).first()
    
    if not func or not rh: 
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")

    ocorrencias = db.query(OcorrenciaRHModel).filter(
        OcorrenciaRHModel.funcionario_id == func_id, 
        OcorrenciaRHModel.data_ocorrencia.startswith(mes_ano)
    ).all()
    
    pontos = db.query(PontoModel).filter(
        PontoModel.funcionario_id == func_id, 
        PontoModel.data.startswith(mes_ano)
    ).all()

    salario_base = rh.salario
    vt = rh.valor_vt
    va = rh.valor_va
    gorjetas = rh.gorjetas_acumuladas
    comissao = rh.valor_comissao if rh.recebe_comissao and rh.tipo_comissao == "FIXO" else 0.0 
    diaria = rh.diaria_motoboy * len(pontos) if rh.diaria_motoboy > 0 else 0.0

    horas_descontadas = sum(o.horas_descontadas for o in ocorrencias)
    valor_hora = (salario_base / 220) if salario_base > 0 else 0
    descontos = horas_descontadas * valor_hora

    total_proventos = salario_base + vt + va + comissao + gorjetas + diaria
    salario_liquido = total_proventos - descontos
    horas_trab = sum((p.horas_trabalhadas or 0) for p in pontos)

    return {
        "colaborador": func.nome, 
        "matricula": func.matricula_cracha, 
        "mes_referencia": mes_ano,
        "empresa": {
            "nome": config.nome_empresa, 
            "cnpj": config.cnpj, 
            "inscricao_estadual": getattr(config, 'inscricao_estadual', ''), 
            "endereco": config.endereco
        },
        "proventos": { 
            "salario_base": salario_base, "vale_transporte": vt, "vale_alimentacao": va, 
            "comissoes": comissao, "gorjetas": gorjetas, "diarias": diaria 
        },
        "descontos": { 
            "horas_nao_trabalhadas": descontos, "horas_quantidade": horas_descontadas 
        },
        "totais": { 
            "total_bruto": total_proventos, "total_descontos": descontos, "liquido_a_pagar": salario_liquido 
        },
        "horas_trabalhadas_mes": round(horas_trab, 2),"dias_trabalhados": len(pontos)
    }

@app.put("/api/colaborador/{func_id}/perfil")
def atualizar_perfil_colaborador(func_id: int, dados: EditarPerfilColaborador, db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    
    if not func or not rh:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
        
    func.nome = dados.nome
    if dados.foto_3x4:
        func.foto_3x4 = dados.foto_3x4
        
    rh.telefone = dados.telefone
    rh.email = dados.email
    rh.cep = dados.cep
    rh.endereco_completo = dados.endereco_completo
    rh.qtd_filhos_menores = dados.qtd_filhos_menores
    
    db.commit()
    return {"status": "sucesso"}


# ==========================================
# 13. CARDÁPIO & COMPLEMENTOS
# ==========================================
@app.get("/api/cardapio")
def listar_cardapio_digital(db: Session = Depends(get_db)): 
    produtos = db.query(ProdutoModel).filter(ProdutoModel.categoria != "Integrações").order_by(ProdutoModel.ordem.asc()).all()
    return [{
        "id": p.id,
        "nome": p.nome,
        "descricao": getattr(p, "descricao", ""),
        "preco_venda": p.preco_venda,
        "categoria": p.categoria,
        "imagem_url": getattr(p, "imagem_url", ""),
        "ordem": getattr(p, "ordem", 0),
        "ativo": p.ativo
    } for p in produtos]

@app.post("/api/gestao/produto")
def receber_novo_produto(produto: NovoProduto, db: Session = Depends(get_db)):
    try:
        novo_produto = ProdutoModel(
            nome=produto.nome, 
            descricao=produto.descricao,
            preco_venda=produto.preco, 
            categoria=produto.categoria,
            imagem_url=produto.imagem_url,
            ordem=produto.ordem
        )
        db.add(novo_produto)
        db.flush()
        
        for f in produto.fichas:
            db.add(FichaTecnicaModel(
                produto_id=novo_produto.id, 
                insumo_id=f.insumo_id, 
                quantidade_necessaria=f.quantidade
            ))
            
        db.commit()
        return {"status": "sucesso", "mensagem": "Produto criado com sucesso no cardápio!"}
    except Exception as e: 
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/gestao/produto/{produto_id}")
def atualizar_produto(produto_id: int, dados: dict, db: Session = Depends(get_db)):
    produto = db.query(ProdutoModel).filter(ProdutoModel.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404,detail="Produto não encontrado")
    
    if 'nome' in dados: produto.nome = dados['nome']
    if 'descricao' in dados: produto.descricao = dados['descricao']
    if 'imagem_url' in dados: produto.imagem_url = dados['imagem_url']
    if 'categoria' in dados: produto.categoria = dados['categoria']
    if 'ativo' in dados: produto.ativo = dados['ativo']
    if 'preco' in dados: produto.preco_venda = dados['preco']
    if 'ordem' in dados: produto.ordem = int(dados['ordem'])
    
    if 'fichas' in dados:
        db.query(FichaTecnicaModel).filter(FichaTecnicaModel.produto_id == produto_id).delete()
        for f in dados['fichas']:
            db.add(FichaTecnicaModel(
                produto_id=produto_id, 
                insumo_id=f["insumo_id"], 
                quantidade_necessaria=f["quantidade"]
            ))
        
    db.commit()
    return {"status": "sucesso", "mensagem": "Produto e Ficha atualizados!"}

@app.delete("/api/gestao/produto/{produto_id}")
def deletar_produto(produto_id: int, db: Session = Depends(get_db)):
    try:
        produto = db.query(ProdutoModel).filter(ProdutoModel.id == produto_id).first()
        if not produto:
            raise HTTPException(status_code=404)
            
        db.delete(produto)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e: 
        db.rollback()
        raise HTTPException(status_code=500)

@app.get("/api/gestao/produto/{produto_id}/fichas")
def obter_fichas_produto(produto_id: int, db: Session = Depends(get_db)):
    fichas = db.query(FichaTecnicaModel).filter(FichaTecnicaModel.produto_id == produto_id).all()
    resultado = []
    for f in fichas:
        insumo = db.query(InsumoModel).filter(InsumoModel.id == f.insumo_id).first()
        if insumo:
            resultado.append({
                "insumo_id": f.insumo_id,
                "quantidade": f.quantidade_necessaria,
                "nome": insumo.nome
            })
    return resultado

@app.post("/api/gestao/complementos")
def criar_grupo_complemento(payload: GrupoCompSchema, db: Session = Depends(get_db)):
    try:
        grupo = GrupoComplementoModel(
            produto_id=payload.produto_id, 
            nome=payload.nome,
            obrigatorio=payload.obrigatorio, 
            minimo_opcoes=payload.minimo_opcoes, 
            maximo_opcoes=payload.maximo_opcoes
        )
        db.add(grupo)
        db.flush() 
        
        for item in payload.itens:
            db.add(ItemComplementoModel(
                grupo_id=grupo.id, 
                nome=item.nome, 
                preco_adicional=item.preco_adicional
            ))
            
        db.commit()
        return {"status":"sucesso", "mensagem": "Complementos ativados no cardápio!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/produtos/{produto_id}/complementos")
def listar_complementos(produto_id: int, db: Session = Depends(get_db)):
    grupos = db.query(GrupoComplementoModel).filter(GrupoComplementoModel.produto_id == produto_id).all()
    resultado = []
    for g in grupos:
        itens = [{"id": i.id, "nome": i.nome, "preco": i.preco_adicional} for i in g.itens]
        resultado.append({
            "id": g.id, 
            "nome": g.nome, 
            "obrigatorio": g.obrigatorio,
            "min": g.minimo_opcoes, 
            "max": g.maximo_opcoes, 
            "itens": itens
        })
    return resultado

@app.post("/api/gestao/combo-maker")
def criar_combo_fast_food(combo: NovoComboFastFood, db: Session = Depends(get_db)):
    try:
        novo_produto = ProdutoModel(
            nome=combo.nome, 
            descricao=combo.descricao,
            preco_venda=combo.preco, 
            categoria=combo.categoria,
            imagem_url=combo.imagem_url,
            ativo=True
        )
        db.add(novo_produto)
        db.flush() 
        
        for etapa in combo.etapas:
            novo_grupo = GrupoComplementoModel(
                produto_id=novo_produto.id, 
                nome=etapa.nome,
                obrigatorio=etapa.obrigatorio, 
                minimo_opcoes=etapa.minimo_opcoes, 
                maximo_opcoes=etapa.maximo_opcoes
            )
            db.add(novo_grupo)
            db.flush() 
            
            for item in etapa.itens:
                db.add(ItemComplementoModel(
                    grupo_id=novo_grupo.id, 
                    nome=item.nome, 
                    preco_adicional=item.preco_adicional
                ))
                
        db.commit()
        return {"status": "sucesso", "mensagem": "Combo criado com sucesso!"}
    except Exception as e: 
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 14. INSUMOS & ESTOQUE
# ==========================================
@app.get("/api/gestao/insumos")
def listar_insumos_disp(db: Session = Depends(get_db)):
    insumos = db.query(InsumoModel).order_by(InsumoModel.nome.asc()).all()
    return [{
        "id": i.id, 
        "nome": i.nome, 
        "unidade": i.unidade_medida, 
        "quantidade_atual": i.quantidade_atual, 
        "quantidade_minima": i.quantidade_minima, 
        "custo": i.custo_unitario
    } for i in insumos]

@app.post("/api/gestao/insumo")
def receber_novo_insumo(insumo: NovoInsumo, db:Session = Depends(get_db)):
    try:
        novo = InsumoModel(
            nome=insumo.nome, 
            unidade_medida=insumo.unidade, 
            quantidade_atual=insumo.quantidade, 
            quantidade_minima=insumo.minimo, 
            custo_unitario=insumo.custo
        )
        db.add(novo)
        db.commit()
        db.refresh(novo)
        return {"status": "sucesso", "insumo_id": novo.id}
    except Exception as e: 
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/gestao/insumo/{insumo_id}")
def atualizar_insumo(insumo_id: int, dados: dict, db: Session = Depends(get_db)):
    insumo = db.query(InsumoModel).filter(InsumoModel.id == insumo_id).first()
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo não encontrado")

    if 'nome' in dados: insumo.nome = dados['nome']
    if 'unidade' in dados: insumo.unidade_medida = dados['unidade']
    if 'quantidade' in dados: insumo.quantidade_atual = dados['quantidade']
    if 'minimo' in dados: insumo.quantidade_minima = dados['minimo']
    if 'custo' in dados: insumo.custo_unitario = dados['custo']

    db.commit()
    return {"status": "sucesso", "mensagem": "Insumo atualizado!"}

@app.delete("/api/gestao/insumo/{insumo_id}")
def deletar_insumo(insumo_id: int, db: Session = Depends(get_db)):
    insumo = db.query(InsumoModel).filter(InsumoModel.id == insumo_id).first()
    if not insumo:
        raise HTTPException(status_code=404)
        
    db.delete(insumo)
    db.commit()
    return {"status": "sucesso"}


# ==========================================
# 15. FINANCEIRO E DRE
# ==========================================
@app.post("/api/gestao/conta")
def receber_nova_conta(conta: NovaConta, db: Session = Depends(get_db)):
    try:
        fornecedor_id = conta.fornecedor_id
        if not fornecedor_id:
            fornecedor = db.query(FornecedorModel).filter(FornecedorModel.nome_fantasia == "Diversos").first()
            if not fornecedor:
                fornecedor = FornecedorModel(nome_fantasia="Diversos", categoria="Geral")
                db.add(fornecedor)
                db.commit()
                db.refresh(fornecedor)
            fornecedor_id = fornecedor.id
            
        data_venc = datetime.strptime(conta.vencimento, "%Y-%m-%d").date()
        lancar_conta_pagar(
            db=db, 
            fornecedor_id=fornecedor_id, 
            descricao=conta.descricao, 
            valor=conta.valor, 
            vencimento=data_venc, 
            tipo_despesa=conta.tipo_despesa
        )
        return {"status": "sucesso"}
    except Exception as e: 
        db.rollback()
        raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/contas_pagar/{conta_id}")
def atualizar_conta(conta_id: int, dados: dict, db: Session = Depends(get_db)):
    try:
        conta = db.query(ContaPagarModel).filter(ContaPagarModel.id == conta_id).first()
        if not conta:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
        
        for key, value in dados.items():
            if hasattr(conta, key):
                setattr(conta, key, value)
                
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/contas_pagar/{conta_id}")
def excluir_conta(conta_id: int, db: Session = Depends(get_db)):
    try:
        conta = db.query(ContaPagarModel).filter(ContaPagarModel.id == conta_id).first()
        if not conta:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
            
        db.delete(conta)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/gestao/contas/{conta_id}/pagar")
def pagar_conta(conta_id: int, db: Session = Depends(get_db)):
    conta = db.query(ContaPagarModel).filter(ContaPagarModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
        
    conta.status = "PAGO"
    db.commit()
    return {"status": "sucesso", "mensagem": "Conta paga e baixada do caixa com sucesso!"}

@app.get("/api/gestao/financeiro/resumo")
def resumo_financeiro(db: Session = Depends(get_db)):
    contas = db.query(ContaPagarModel).order_by(ContaPagarModel.data_vencimento.asc()).all()
    total_empresa = sum(c.valor for c in contas if c.tipo_despesa == "Empresa")
    total_casa = sum(c.valor for c in contas if c.tipo_despesa == "Casa")
    
    lista = [{
        "id": c.id, 
        "descricao": c.descricao, 
        "valor": c.valor, 
        "vencimento": c.data_vencimento.strftime("%d/%m/%Y"), 
        "tipo": c.tipo_despesa, 
        "status": c.status
    } for c in contas]
    return {"total_empresa": total_empresa, "total_casa": total_casa, "contas": lista}

@app.get("/api/gestao/financeiro/lucratividade")
def obter_relatorio_lucratividade(data_inicio: str = None, data_fim: str = None, db: Session = Depends(get_db)):
    query_pedidos = db.query(PedidoModel).filter(PedidoModel.status != "CANCELADO")
    query_contas = db.query(ContaPagarModel)
    
    if data_inicio and data_fim and data_inicio != "undefined" and data_fim != "undefined":
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            df = datetime.strptime(data_fim, "%Y-%m-%d").date()
            query_pedidos = query_pedidos.filter(PedidoModel.data_pedido >= di, PedidoModel.data_pedido <= df)
            query_contas = query_contas.filter(ContaPagarModel.data_vencimento >= di, ContaPagarModel.data_vencimento <= df)
        except Exception: 
            pass
        
    pedidos = query_pedidos.all()
    contas = query_contas.all()
    
    faturamento_total = sum(p.total_pago for p in pedidos)
    despesas_empresa = sum(c.valor for c in contas if c.tipo_despesa == "Empresa")
    despesas_casa = sum(c.valor for c in contas if c.tipo_despesa == "Casa")
    
    lucro_operacional = faturamento_total - despesas_empresa
    lucro_liquido_real = lucro_operacional - despesas_casa
    margem_lucro = (lucro_operacional / faturamento_total * 100) if faturamento_total > 0 else 0
    
    return { 
        "faturamento": faturamento_total, 
        "despesas_empresa": despesas_empresa, 
        "despesas_casa": despesas_casa, 
        "lucro_operacional": lucro_operacional, 
        "lucro_liquido": lucro_liquido_real, 
        "margem_lucro": round(margem_lucro, 2) 
    }

@app.get("/api/gestao/relatorios/curva-abc")
def obter_relatorio_curva_abc(data_inicio: str = None, data_fim: str = None, db: Session = Depends(get_db)):
    query = db.query(PedidoModel).filter(PedidoModel.status != "CANCELADO")
    if data_inicio and data_fim and data_inicio != "undefined" and data_fim != "undefined":
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            df = datetime.strptime(data_fim, "%Y-%m-%d").date()
            query = query.filter(PedidoModel.data_pedido >= di, PedidoModel.data_pedido <= df)
        except Exception: 
            pass
            
    ranking = {}
    for pedido in query.all():
        for item in pedido.itens:
            if item.produto_id not in ranking:
                produto = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
                if produto: 
                    ranking[item.produto_id] = {
                        "nome": produto.nome, 
                        "categoria": produto.categoria, 
                        "quantidade_vendida": 0, 
                        "faturamento_gerado": 0.0, 
                        "preco": produto.preco_venda
                    }
            if item.produto_id in ranking:
                ranking[item.produto_id]["quantidade_vendida"] += item.quantidade
                ranking[item.produto_id]["faturamento_gerado"] += (item.quantidade * ranking[item.produto_id]["preco"])
                
    lista = list(ranking.values())
    lista.sort(key=lambda x: x["faturamento_gerado"], reverse=True)
    return lista[:10]

@app.get("/api/pedidos/{pedido_id}/recibo")
def obter_recibo_pedido(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    
    cliente = pedido.cliente
    itens_formatados = []
    for item in pedido.itens:
        prod = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
        nome_prod = prod.nome if prod else "Produto Indisponível"
        preco_unit = prod.preco_venda if prod else 0.0
        itens_formatados.append({
            "quantidade": item.quantidade,
            "nome": nome_prod,
            "preco_unitario": preco_unit,
            "subtotal": item.quantidade * preco_unit,
            "observacao": item.observacao or ""
        })
    
    endereco = "Retirada no Balcão"
    tipo_pedido = str(pedido.tipo_pedido).split('.')[-1].upper()
    
    if tipo_pedido == "DELIVERY":
        if itens_formatados and "Endereço:" in itens_formatados[0]["observacao"]:
            partes = itens_formatados[0]["observacao"].split(" | ")
            for p in partes:
                if "Endereço:" in p:
                    endereco = p.replace("Endereço:", "").strip()
                    break
        elif cliente and getattr(cliente, 'logradouro', ''):
            endereco = f"{cliente.logradouro}, {cliente.numero} - {cliente.bairro}"

    return {
        "id": pedido.id,
        "senha_diaria": getattr(pedido, 'senha_diaria', str(pedido.id).zfill(3)),
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo": tipo_pedido,
        "cliente_nome": cliente.nome if cliente else "Cliente Avulso",
        "cliente_telefone": cliente.telefone if cliente else "",
        "endereco": endereco,
        "itens": itens_formatados,
        "total": pedido.total_pago,
        "forma_pagamento": str(pedido.forma_pagamento).replace('_', ' ').upper()
    }


# ==========================================
# 16. LOGÍSTICA & KITCHEN DISPLAY (KDS)
# ==========================================
@app.get("/api/logistica/pedidos")
def listar_pedidos_logistica(db: Session = Depends(get_db)):
    try:
        pedidos = db.query(PedidoModel).order_by(PedidoModel.id.desc()).all()
        prontos, em_rota = [], []
        
        for p in pedidos:
            try:
                status_atual = str(p.status).split('.')[-1].upper()
                tipo_atual = str(p.tipo_pedido).split('.')[-1].upper()
                
                if tipo_atual not in ["DELIVERY", "RETIRADA"]: 
                    continue
                
                endereco_completo = 'Retirada no Balcão' if tipo_atual == 'RETIRADA' else 'Endereço não informado'
                for item in p.itens:
                    obs = item.observacao or ""
                    if obs and "Endereço: " in obs:
                        for parte in obs.split(" | "):
                            if "Endereço: " in parte:
                                endereco_completo = parte.replace("Endereço: ", "").strip()
                                break
                        break
                
                telefone_seguro = p.cliente.telefone if p.cliente else "Não informado"
                dados_pedido = { 
                    "id": p.id,  
                    "senha_diaria": getattr(p, 'senha_diaria', str(p.id).zfill(3)),
                    "origem": getattr(p, 'origem', 'SITE'),
                    "cliente": p.cliente.nome if p.cliente else "Cliente", 
                    "telefone": telefone_seguro, 
                    "status": status_atual,  
                    "endereco": endereco_completo,
                    "tipo": tipo_atual
                }
                
                if status_atual == "PRONTO": 
                    prontos.append(dados_pedido)
                elif status_atual in ["SAIU_PARA_ENTREGA", "EM_ROTA"]: 
                    em_rota.append(dados_pedido)
            except Exception:
                continue
                
        return {"prontos": prontos, "em_rota": em_rota}
    except Exception:
        return {"prontos": [], "em_rota": []}

@app.put("/api/logistica/pedidos/{pedido_id}/despachar")
def despachar_pedido(pedido_id: int, payload: dict, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido: 
        raise HTTPException(status_code=404)
        
    pedido.status = "SAIU_PARA_ENTREGA"
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', str(pedido.id).zfill(3))
        try:
            notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, "SAIU_PARA_ENTREGA")
        except Exception:
            pass
    return {"status": "sucesso"}

@app.put("/api/logistica/pedidos/{pedido_id}/entregar")
def concluir_entrega_final(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido:raise HTTPException(status_code=404, detail="Pedido não encontrado")
    
    pedido.status = "ENTREGUE"
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', str(pedido.id).zfill(3))
        try:
            notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, "ENTREGUE")
        except Exception:
            pass
    return {"status": "sucesso", "mensagem": "Baixa realizada e cliente notificado!"}

@app.get("/api/kds/pedidos")
def listar_pedidos_cozinha(db: Session = Depends(get_db)):
    pedidos_ativos = db.query(PedidoModel).order_by(PedidoModel.id.asc()).all()
    recebidos, preparando = [], []
    
    for pedido in pedidos_ativos:
        status_atual = str(pedido.status).split('.')[-1].upper()
        if status_atual not in ["RECEBIDO", "EM_PREPARO", "PREPARANDO"]: 
            continue
            
        tipo_atual = str(pedido.tipo_pedido).split('.')[-1].upper()
        itens = []
        for item in pedido.itens:
            produto = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
            itens.append({
                "quantidade": item.quantidade, 
                "nome": produto.nome if produto else "Item Editado",
                "observacao": item.observacao or ""
            })
            
        obj_pedido = {
            "id": pedido.id, 
            "senha_diaria": getattr(pedido, 'senha_diaria', str(pedido.id).zfill(3)),
            "origem": getattr(pedido, 'origem', 'SITE'),
            "tipo": tipo_atual, 
            "status": status_atual, 
            "itens": itens
        }

        if status_atual == "RECEBIDO":
            recebidos.append(obj_pedido)
        else:
            preparando.append(obj_pedido)
            
    return {"recebidos": recebidos, "preparando": preparando}

@app.put("/api/kds/pedidos/{pedido_id}/status")
def mudar_status_pedido(pedido_id: int, payload: AtualizarStatus, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido: 
        raise HTTPException(status_code=404)
    
    novo_status = payload.status.upper()
    pedido.status = novo_status
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', str(pedido.id).zfill(3))
        try:
            background_tasks.add_task(notificar_status_pedido, pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, novo_status)
        except Exception: 
            pass
        
    return {"mensagem":"Status atualizado"}


# ==========================================
# 17. TELEMETRIA GPS & RASTREIO
# ==========================================
@app.post("/api/logistica/gps")
def atualizar_gps_motoboy(dados: CoordenadasGPS):
    POSICOES_MOTOBOYS_AO_VIVO[dados.pedido_id] = {
        "lat": dados.lat, 
        "lng": dados.lng, 
        "atualizado_em": datetime.now().isoformat()
    }
    return {"status": "ok"}

@app.get("/api/logistica/gps/{pedido_id}")
def buscar_posicao_motoboy(pedido_id: int, db: Session = Depends(get_db)):
    coord_padrao = {"lat": -25.6600, "lng": -49.3100}
    try:
        pedido = db.query(PedidoModel).filter(
            (PedidoModel.id == pedido_id) | (PedidoModel.senha_diaria == str(pedido_id))
        ).order_by(desc(PedidoModel.id)).first()
        
        if not pedido:
            return {"status": "online", "posicao": coord_padrao}
            
        real_id = pedido.id
        posicao = POSICOES_MOTOBOYS_AO_VIVO.get(real_id) or POSICOES_MOTOBOYS_AO_VIVO.get(pedido_id)

        if not posicao and pedido.entregador_lat and pedido.entregador_lng:
            posicao = {"lat": float(pedido.entregador_lat), "lng": float(pedido.entregador_lng)}

        if posicao:
            return {"status": "online", "posicao": {"lat": float(posicao["lat"]), "lng": float(posicao["lng"])}}
        return {"status": "online", "posicao": coord_padrao}
    except Exception as e:
        print(f"Erro ao processar GPS: {e}")
        return {"status": "online", "posicao": coord_padrao}

@app.post("/api/logistica/gps/{pedido_id}/atualizar")
def atualizar_posicao_motoboy_endpoint(pedido_id: int, payload: dict):
    try:
        lat = payload.get("lat")
        lng = payload.get("lng")
        if lat and lng:
            POSICOES_MOTOBOYS_AO_VIVO[pedido_id] = {
                "lat": float(lat),
                "lng": float(lng),
                "status": "online",
                "ultima_atualizacao": datetime.utcnow()
            }
            return {"ok": True}
        return {"ok": False, "erro": "Coordenadas não enviadas"}
    except Exception as e:
        return {"ok": False, "erro": str(e)}

@app.get("/api/rastreio/{busca}")
def rastrear_pedido_cliente(busca: str, db: Session = Depends(get_db)):
    try:
        busca_limpa = "".join(filter(str.isdigit, busca))
        pedido = None
        if busca_limpa:
            num = int(busca_limpa)
            pedido = db.query(PedidoModel).filter((PedidoModel.id == num) | (PedidoModel.senha_diaria == str(num))).first()
            
        if not pedido:
            telefone = busca.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("+", "")
            pedido = db.query(PedidoModel).join(ClienteModel).filter(ClienteModel.telefone == telefone).order_by(desc(PedidoModel.id)).first()
            
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
            
        status_atual = str(pedido.status).split('.')[-1].upper()
        progresso = 20
        if status_atual in ["EM_PREPARO", "PREPARANDO"]: progresso = 50
        elif status_atual in ["PRONTO", "SAIU_PARA_ENTREGA", "EM_ROTA"]: progresso = 80
        elif status_atual in ["ENTREGUE", "FINALIZADO", "CONCLUIDO"]: progresso = 100
        elif status_atual == "CANCELADO": progresso = 0
        
        return {
            "id": pedido.id,
            "senha": getattr(pedido, 'senha_diaria', str(pedido.id).zfill(3)),
            "status": status_atual,
            "progresso": progresso,
            "tipo": str(pedido.tipo_pedido).split('.')[-1].upper(),
            "total": float(pedido.total_pago or 0.0)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Erro no Rastreio: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no servidor")


# ==========================================
# 18. CONFIGURAÇÕES DA LOJA & SETUP
# ==========================================
@app.get("/api/gestao/configuracoes")
def ler_configuracoes(db: Session = Depends(get_db)):
    config = db.query(ConfiguracaoLojaModel).first()
    if not config:
        config = ConfiguracaoLojaModel()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

@app.put("/api/gestao/configuracoes")
def salvar_configuracoes(dados: dict, db: Session = Depends(get_db)):
    try:
        config = db.query(ConfiguracaoLojaModel).first()
        if not config: 
            config = ConfiguracaoLojaModel()
            db.add(config)
            db.commit()
            db.refresh(config)

        for key, value in dados.items():
            if hasattr(config, key):
                setattr(config, key, value)
                
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 19. CUPONS DE DESCONTO
# ==========================================
@app.get("/api/gestao/cupons")
def listar_cupons(db: Session = Depends(get_db)):
    return db.query(CupomModel).all()

@app.post("/api/gestao/cupons")
@app.post("/api/cupons-pro/criar")
def criar_cupom_pro(dados: dict, db: Session = Depends(get_db)):
    try:
        codigo = str(dados.get("codigo", "")).upper().strip()
        if not codigo:
            raise HTTPException(status_code=400, detail="O código do cupom é obrigatório.")
            
        existe = db.query(CupomModel).filter(CupomModel.codigo == codigo).first()
        if existe:
            raise HTTPException(status_code=400, detail="Este código de cupom já existe.")
            
        tipo_cupom = dados.get("tipo", "PERCENTUAL")
        val_cupom = float(dados.get("valor", 0.0))
        data_val = dados.get("validade") or data_infinita_str()
        
        cpf_excl = dados.get("cpf_exclusivo", "")
        cpf_excl_limpo = str(cpf_excl).replace(".", "").replace("-", "").strip() if cpf_excl else None

        novo = CupomModel(
            codigo=codigo,
            tipo=tipo_cupom,
            valor=val_cupom,
            desconto_percentual=val_cupom if tipo_cupom == "PERCENTUAL" else 0.0,
            desconto_fixo=val_cupom if tipo_cupom == "VALOR_FIXO" else 0.0,
            data_validade=data_val,
            ativo=True,
            qtd_limite=dados.get("qtd_limite"),
            usos_atuais=0,
            publico_alvo=dados.get("publico_alvo", "todos"),
            cpf_exclusivo=cpf_excl_limpo
        )
        db.add(novo)
        db.commit()
        return {"status": "sucesso", "mensagem": f"Cupom {codigo} criado com sucesso!"}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno no Banco de Dados: {str(e)}")

@app.delete("/api/gestao/cupons/{cupom_id}")
def excluir_cupom(cupom_id: int, db: Session = Depends(get_db)):
    cupom = db.query(CupomModel).filter(CupomModel.id == cupom_id).first()
    if not cupom:
        raise HTTPException(status_code=404, detail="Cupom não encontrado.")
    db.delete(cupom)
    db.commit()
    return {"status": "sucesso", "mensagem": "Cupom excluído!"}

@app.post("/api/carrinho/validar-cupom")
def validar_cupom(dados: dict, db: Session = Depends(get_db)):
    try:
        codigo = str(dados.get("codigo", "")).upper().strip()
        cpf_cliente = str(dados.get("cpf", "")).replace(".", "").replace("-", "").strip()
        is_cadastrado = dados.get("is_cadastrado", False)
        
        cupom = db.query(CupomModel).filter(CupomModel.codigo == codigo, CupomModel.ativo == True).first()
        if not cupom:
            raise HTTPException(status_code=404, detail="Cupom inválido ou não existe.")

        if cupom.data_validade:
            data_val_str = str(cupom.data_validade)
            if not data_val_str.startswith("203"):
                try:
                    val_date = datetime.strptime(data_val_str[:10], "%Y-%m-%d").date()
                    if datetime.utcnow().date() > val_date:
                        raise HTTPException(status_code=400, detail=f"Este cupom venceu no dia {val_date.strftime('%d/%m/%Y')}.")
                except ValueError:
                    pass

        if cupom.qtd_limite and cupom.qtd_limite > 0:
            if (cupom.usos_atuais or 0) >= cupom.qtd_limite:
                raise HTTPException(status_code=400, detail="Esgotado! Limite de usos deste cupom já foi atingido.")

        publico = cupom.publico_alvo or "todos"
        if publico == "cadastrados" and not is_cadastrado:
            raise HTTPException(status_code=400, detail="Cupom exclusivo para clientes com conta/login.")
        if publico == "visitantes" and is_cadastrado:
            raise HTTPException(status_code=400, detail="Cupom válido apenas para a primeira compra (visitantes).")

        if cupom.cpf_exclusivo and cpf_cliente != cupom.cpf_exclusivo:
            raise HTTPException(status_code=400, detail="Este cupom é nominal e intransferível.")

        subtotal = float(dados.get("subtotal", 0.0))
        desconto = subtotal * (cupom.valor / 100.0) if cupom.tipo == "PERCENTUAL" else cupom.valor
        desconto = min(desconto, subtotal)
            
        return {"status": "sucesso", "codigo": cupom.codigo, "tipo": cupom.tipo, "valor_desconto": round(desconto, 2)}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao validar cupom: {str(e)}")
        
# ==========================================
# 20. CONTROLE DE TURNOS DO CAIXA
# ==========================================
@app.get("/api/pdv/caixa/atual")
def obter_caixa_atual(db: Session = Depends(get_db)):
    caixa = db.query(CaixaTurnoModel).filter(CaixaTurnoModel.status == "ABERTO").order_by(CaixaTurnoModel.id.desc()).first()
    if not caixa:
        return {"status": "fechado"}
        
    data_hoje = datetime.utcnow().date()
    vendas_hoje = db.query(PedidoModel).filter(PedidoModel.data_pedido == data_hoje, PedidoModel.status != "CANCELADO").all()
    
    total_dinheiro = sum(p.total_pago for p in vendas_hoje if "dinheiro" in str(p.forma_pagamento).lower() and p.origem != "SITE (Online)")
    total_outros = sum(p.total_pago for p in vendas_hoje if "dinheiro" not in str(p.forma_pagamento).lower() and p.origem != "SITE (Online)")
    
    caixa.total_vendas_dinheiro = total_dinheiro
    caixa.total_vendas_outros = total_outros
    db.commit()
    
    saldo_esperado = caixa.saldo_inicial + caixa.entradas_saidas + total_dinheiro
    return {
        "status": "aberto",
        "caixa_id": caixa.id,
        "operador": caixa.operador,
        "data_abertura": caixa.data_abertura,
        "saldo_inicial": caixa.saldo_inicial,
        "entradas_saidas": caixa.entradas_saidas,
        "total_vendas_dinheiro": total_dinheiro,
        "total_vendas_outros": total_outros,
        "saldo_esperado_gaveta": saldo_esperado
    }

# ==========================================
# 21. TAXAS DE ENTREGA (LOGÍSTICA)
# ==========================================
@app.get("/api/taxas/listar")
def listar_taxas(db: Session = Depends(get_db)):
    try:
        return db.query(TaxaEntregaModel).order_by(TaxaEntregaModel.bairro.asc()).all()
    except Exception as e:
        print(f"Erro ao listar taxas:{e}")
        return []

@app.post("/api/taxas/salvar")
def criar_taxa(dados: TaxaEntregaSchema, db: Session = Depends(get_db)):
    try:
        tx = db.query(TaxaEntregaModel).filter(TaxaEntregaModel.bairro == dados.bairro).first()
        if tx:
            tx.taxa = dados.taxa
        else:
            novo = TaxaEntregaModel(bairro=dados.bairro, taxa=dados.taxa)
            db.add(novo)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao salvar taxa: {str(e)}")

@app.delete("/api/taxas/{id}")
def deletar_taxa(id: int, db: Session = Depends(get_db)):
    try:
        tx = db.query(TaxaEntregaModel).filter(TaxaEntregaModel.id == id).first()
        if tx:
            db.delete(tx)
            db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao excluir taxa: {str(e)}")


# ==========================================
# 22. MOTOR UNIVERSAL DE GESTÃO (CRUD GENÉRICO)
# ==========================================
@app.put("/api/gestao/{tabela}/{item_id}")
def atualizar_item_generico(tabela: str, item_id: int, dados: dict, db: Session = Depends(get_db)):
    try:
        modelo = pegar_modelo_banco(tabela)
        if not modelo: raise HTTPException(status_code=404, detail="Tabela não encontrada no Motor.")
        
        item = db.query(modelo).filter(modelo.id == item_id).first()
        if not item: raise HTTPException(status_code=404, detail="Item não encontrado no banco.")
        
        for chave, valor in dados.items():
            if hasattr(item, chave) and chave != "id":
                setattr(item, chave, valor)
                
        db.commit()
        return {"status": "ok", "mensagem": "Atualizado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gestao/{tabela}")
def criar_item_generico(tabela: str, dados: dict, db: Session = Depends(get_db)):
    try:
        modelo = pegar_modelo_banco(tabela)
        if not modelo: raise HTTPException(status_code=404)
        
        novo_item = modelo(**dados)
        db.add(novo_item)
        db.commit()
        return {"status": "ok", "mensagem": "Criado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/gestao/{tabela}/{item_id}")
def deletar_item_generico(tabela: str, item_id: int, db: Session = Depends(get_db)):
    try:
        modelo = pegar_modelo_banco(tabela)
        if not modelo:raise HTTPException(status_code=404)
        
        if tabela == "clientes":
            db.query(PedidoModel).filter(PedidoModel.cliente_id == item_id).update({"cliente_id": None})
            db.execute(text("DELETE FROM fidelidade_pontos WHERE cliente_id = :id"), {"id": item_id})
        
        db.query(modelo).filter(modelo.id == item_id).delete()
        db.commit()
        return {"status": "ok", "mensagem": "Apagado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 23. ROTAS VISUAIS (TEMPLATES HTML)
# ==========================================
@app.get("/portal", response_class=HTMLResponse)
def abrir_portal_central(): 
    if Path("templates/portal.html").exists():
        return Path("templates/portal.html").read_text(encoding="utf-8")
    return "Erro: Arquivo portal.html não encontrado."
    
@app.get("/login", response_class=HTMLResponse)
def abrir_tela_login(): 
    if Path("templates/login.html").exists():
        return Path("templates/login.html").read_text(encoding="utf-8")
    return "Erro: Arquivo login.html não encontrado."

@app.get("/", response_class=HTMLResponse)
def abrir_cardapio(): 
    if Path("templates/cardapio.html").exists():
        return Path("templates/cardapio.html").read_text(encoding="utf-8")
    return "Erro: Arquivo cardapio.html não encontrado."

@app.get("/admin", response_class=HTMLResponse)
def abrir_admin(): 
    if Path("templates/dashboard.html").exists():
        return Path("templates/dashboard.html").read_text(encoding="utf-8")
    return "Erro: Arquivo dashboard.html não encontrado."

@app.get("/gestao", response_class=HTMLResponse)
def abrir_gestao(): 
    if Path("templates/gestao.html").exists():
        return Path("templates/gestao.html").read_text(encoding="utf-8")
    return "Erro: Arquivo gestao.html não encontrado."

@app.get("/pdv", response_class=HTMLResponse)
def abrir_pdv(): 
    if Path("templates/pdv.html").exists():
        return Path("templates/pdv.html").read_text(encoding="utf-8")
    return "Erro: Arquivo pdv.html não encontrado."

@app.get("/logistica", response_class=HTMLResponse)
def abrir_logistica(): 
    if Path("templates/logistica.html").exists():
        return Path("templates/logistica.html").read_text(encoding="utf-8")
    return "Erro: Arquivo logistica.html não encontrado."

@app.get("/tv", response_class=HTMLResponse)
def abrir_tv_senhas(): 
    if Path("templates/tv.html").exists():return Path("templates/tv.html").read_text(encoding="utf-8")
    return "Erro: Arquivo tv.html não encontrado."
    
@app.get("/kds", response_class=HTMLResponse)
def abrir_kds(): 
    if Path("templates/kds.html").exists():
        return Path("templates/kds.html").read_text(encoding="utf-8")
    return "Erro: Arquivo kds.html não encontrado."

@app.get("/totem", response_class=HTMLResponse)
def abrir_totem(): 
    if Path("templates/totem.html").exists():
        return Path("templates/totem.html").read_text(encoding="utf-8")
    return "Erro: Arquivo totem.html não encontrado."

@app.get("/admissao", response_class=HTMLResponse)
def abrir_admissao(): 
    if Path("templates/admissao.html").exists():
        return Path("templates/admissao.html").read_text(encoding="utf-8")
    return "Erro: Arquivo admissao.html não encontrado."

@app.get("/portal_colaborador", response_class=HTMLResponse)
def abrir_portal_colaborador(): 
    if Path("templates/portal_colaborador.html").exists():
        return Path("templates/portal_colaborador.html").read_text(encoding="utf-8")
    return "Erro: Arquivo portal_colaborador.html não encontrado."

@app.get("/mapa", response_class=HTMLResponse)
def tela_rastreio_mapa(request: Request):
    return FileResponse(os.path.join("templates", "mapa.html"))

@app.get("/motoboy", response_class=HTMLResponse)
def tela_app_motoboy(request: Request):
    return FileResponse(os.path.join("templates", "motoboy.html"))


# ==========================================
# 24. TV DO SALÃO & PAINEL DE SENHAS
# ==========================================
@app.get("/api/tv/pedidos")
def obter_pedidos_tv(db: Session = Depends(get_db)):
    try:
        pedidos = db.query(PedidoModel).all()
        em_preparo, prontos = [], []
        for p in pedidos:
            st = str(p.status).upper()
            obj = {
                "id": p.id,
                "senha_diaria": getattr(p, 'senha_diaria', str(p.id).zfill(3)),
                "cliente_nome": p.cliente.nome if p.cliente else "Cliente"
            }
            if "RECEBIDO" in st or "PREPAR" in st:
                em_preparo.append(obj)
            elif "PRONTO" in st:
                prontos.append(obj)
        return {"em_preparo": em_preparo, "prontos": prontos}
    except Exception: 
        return {"em_preparo": [], "prontos": []}


# ==========================================
# 25. LIMPEZA SEGURA DO BANCO (COM SENHA E JWT)
# ==========================================
@app.delete("/api/sistema/zerar-dados")
def limpar_banco_dados(
    payload:ConfirmacaoZerarDados, 
    admin: FuncionarioModel = Depends(exigir_administrador), 
    db: Session = Depends(get_db)
):
    if payload.palavra_seguranca != "CONFIRMAR":
        raise HTTPException(status_code=400, detail="Palavra de segurança incorreta.")

    try:
        db.execute(text("DELETE FROM itens_complementos;"))
        db.execute(text("DELETE FROM grupos_complementos;"))
        db.execute(text("DELETE FROM fichas_tecnicas;"))
        db.query(ItemPedidoModel).delete()
        db.query(PedidoModel).delete()
        db.query(ProdutoModel).delete()
        db.query(InsumoModel).delete()
        db.query(ContaPagarModel).delete()
        db.query(FornecedorModel).delete()
        db.query(PontoModel).delete()
        db.query(OcorrenciaRHModel).delete()
        db.query(SolicitacaoFeriasModel).delete()
        db.query(InfoRHModel).delete()
        db.query(FuncionarioModel).filter(FuncionarioModel.id != admin.id).delete()
        db.commit()
        return {"mensagem": "Banco de dados higienizado com sucesso pelo administrador."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 26. INCLUSÃO DE ROUTERS EXTRAS E PWA
# ==========================================
app.include_router(router_dashboard)
app.include_router(router_pagamentos)
app.include_router(router_99food)

@app.get("/api/gestao/notificacoes")
def checar_novos_pedidos(db: Session = Depends(get_db)):
    qtd_novos = db.query(PedidoModel).filter(PedidoModel.status == "RECEBIDO").count()
    return {"pendentes": qtd_novos}

@app.post("/api/webhooks/ifood")
async def webhook_ifood(request: Request): 
    return {"status": "ok"}

@app.post("/api/webhooks/99food")
async def webhook_99food(request: Request): 
    return {"status": "ok"}

@app.post("/api/webhooks/redes-sociais")
async def webhook_social(request: Request): 
    return {"status": "ok"}

@app.post("/api/webhooks/whatsapp-receber")
def receber_mensagem_cliente(payload: dict): 
    return {"status": "sucesso"}

@app.get("/manifest.json")
def get_manifest():
    manifest = {
        "name": "Art's Burguer",
        "short_name": "Art's Burguer",
        "description": "O melhor burger da cidade no seu celular!",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#ff4757",
        "icons": [
            {"src": "/static/img/icon-192x192.png", "sizes": "192x192", "type": "image/png"},{"src": "/static/img/icon-512x512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }
    return JSONResponse(content=manifest)

@app.get("/sw.js")
def get_service_worker():
    sw_content = """
    const CACHE_NAME = "arts-burguer-v1";
    self.addEventListener("install", (event) => {
        self.skipWaiting();
    });
    self.addEventListener("fetch", (event) => {
        event.respondWith(
            fetch(event.request).catch(() => new Response("Você está offline. Conecte-se à internet."))
        );
    });
    """
    return Response(content=sw_content, media_type="application/javascript")

if __name__ == "__main__":
    print("🚀 Servidor Art's Burguer V5 iniciando...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
