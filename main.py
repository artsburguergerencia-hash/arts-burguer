from fastapi import FastAPI, Depends, HTTPException, Query, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from datetime import datetime, date
from sqlalchemy import desc, Column, Integer, String, Float, Boolean, text
import uvicorn
from passlib.context import CryptContext

# ==========================================
# IMPORTAÇÕES DOS MÓDULOS (ART'S BURGUER)
# ==========================================
from integracao_99food import router_99food
from pagamentos_pagbank import (
    criar_pagamento_pix_mp, 
    criar_link_pagamento_mp, 
    criar_pagamento_cartao_mp
)
from vendas_pdv import (
    ClienteModel, 
    PedidoModel, 
    ItemPedidoModel, 
    registrar_venda_pdv, 
    TipoPedido
)
from financeiro import (
    FornecedorModel, 
    ContaPagarModel, 
    lancar_conta_pagar
)
from dashboard import router_dashboard
from pagamentos_crm import router_pagamentos
from whatsapp_ia import notificar_status_pedido

# IMPORTAÇÕES EXCLUSIVAS DO BANCO DE DADOS
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
    Cliente
)

# ==========================================
# CONFIGURAÇÃO DO SERVIDOR FASTAPI
# ==========================================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
app = FastAPI(title="API - Art's Burguer ERP Corporativo V5", version="5.0.0")

# Cria as tabelas e roda as migrações automáticas do banco de dados
inicializar_banco()
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# SCHEMAS (MODELOS DE DADOS - PYDANTIC)
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
    endereco_cliente: str = ""
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

# --- SCHEMAS DE RECURSOS HUMANOS (V5 CORPORATIVO) ---

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
    
    # Endereço
    cep: str = ""
    endereco_completo: str = ""
    
    # Dados Bancários Separados
    banco: str = ""
    agencia: str = ""
    conta: str = ""
    
    # Pessoais
    escolaridade: str = ""
    qtd_filhos_menores: int = 0
    cnh: str = ""
    email: str = ""
    plano_saude_escolhido: str = ""
    
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


# ==========================================
# FUNÇÕES GERAIS E ÚTEIS
# ==========================================

def gerar_senha_diaria(db: Session):
    hoje = datetime.utcnow().date()
    ultimo_pedido = db.query(PedidoModel).filter(
        PedidoModel.data_pedido == hoje
    ).order_by(desc(PedidoModel.senha_diaria)).first()
    
    if ultimo_pedido and ultimo_pedido.senha_diaria:
        return ultimo_pedido.senha_diaria + 1
    
    return 1 

# ==========================================
# GESTÃO DE MESAS (SALÃO)
# ==========================================
@app.get("/api/gestao/mesas")
def listar_mesas_ocupadas(db: Session = Depends(get_db)):
    try:
        pedidos_ativos = db.query(PedidoModel).order_by(desc(PedidoModel.id)).all()
        
        mesas_ocupadas = []
        for p in pedidos_ativos:
            # 1. Checa o status de forma segura
            status_atual = str(p.status).split('.')[-1].upper()
            if status_atual in ["ENTREGUE", "CANCELADO", "CONCLUIDO"]:
                continue # Pula os pedidos que já foram finalizados
                
            # 2. Puxa o nome do cofre correto (p.cliente.nome)
            nome_cli = p.cliente.nome.upper() if p.cliente else "CLIENTE AVULSO"
            
            # 3. O Radar: Se a palavra MESA estiver no nome
            if "MESA" in nome_cli:
                numero = nome_cli.replace("MESA", "").replace("-", "").strip()
                total = getattr(p, 'total_pago', getattr(p, 'valor_total', 0.0))
                
                mesas_ocupadas.append({
                    "pedido_id": p.id,
                    "numero_mesa": numero,
                    "status": status_atual,
                    "total": float(total)
                })
                
        return mesas_ocupadas
    except Exception as e:
        print(f"Erro no radar de mesas: {e}")
        return [] # Se der erro, retorna vazio para não quebrar a tela visual

@app.get("/mesas", response_class=HTMLResponse)
def abrir_tela_mesas(): 
    if Path("templates/mesas.html").exists():
        return Path("templates/mesas.html").read_text(encoding="utf-8")
    return "Erro: Arquivo mesas.html não encontrado."
    
# ==========================================
# ROTAS DE FORNECEDORES
# ==========================================

@app.get("/api/gestao/fornecedores")
def listar_fornecedores(db: Session = Depends(get_db)):
    fornecedores = db.query(FornecedorModel).all()
    lista_formatada = []
    
    for f in fornecedores:
        lista_formatada.append({
            "id": f.id, 
            "nome_fantasia": f.nome_fantasia, 
            "categoria": f.categoria, 
            "contato": getattr(f, 'contato', ''), 
            "cnpj": getattr(f, 'cnpj', '')
        })
        
    return lista_formatada


@app.post("/api/gestao/fornecedores")
def cadastrar_fornecedor(dados: NovoFornecedor, db: Session = Depends(get_db)):
    try:
        # Tratamento do CNPJ: Se vier vazio, salva como nulo no banco
        cnpj_limpo = dados.cnpj.strip() if dados.cnpj and dados.cnpj.strip() != "" else None
        
        novo_fornecedor = FornecedorModel(
            nome_fantasia=dados.nome_fantasia, 
            categoria=dados.categoria, 
            contato=dados.contato,
            telefone=dados.contato, # Salva nos dois para garantir retrocompatibilidade
            cnpj=cnpj_limpo
        )
        db.add(novo_fornecedor)
        db.commit()
        db.refresh(novo_fornecedor)
        
        return {
            "status": "sucesso", 
            "id": novo_fornecedor.id, 
            "mensagem": "Fornecedor cadastrado com sucesso!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# ROTAS DE CLIENTES
# ==========================================

@app.post("/api/cliente/registrar")
def cadastrar_novo_cliente(dados: dict = Body(...), db: Session = Depends(get_db)):
    try:
        telefone_cliente = dados.get("telefone")
        if not telefone_cliente:
            raise HTTPException(status_code=400, detail="O telefone é obrigatório.")

        # Verifica se o cliente já existe para não duplicar
        cliente_existente = db.query(Cliente).filter(Cliente.telefone == telefone_cliente).first()
        if cliente_existente:
            raise HTTPException(status_code=400, detail="Este telefone já está cadastrado. Faça o login.")

        # Cria o novo cliente capturando todos os campos novos do Cardápio (incluindo número e foto)
        novo_cliente = Cliente(
            nome=dados.get("nome", "Cliente Visitante"),
            telefone=telefone_cliente,
            senha=dados.get("senha", ""),
            cpf=dados.get("cpf", ""),
            data_nascimento=dados.get("data_nascimento", ""),
            cep=dados.get("cep", ""),
            endereco=dados.get("endereco", ""),
            numero=dados.get("numero", ""),
            bairro=dados.get("bairro", ""),
            complemento=dados.get("complemento", ""),
            pontos=0,
            cashback=0.0,
            bloqueado=False
        )
        
        # Garante a vinculação da foto caso enviada
        if "foto" in dados and hasattr(novo_cliente, "foto"):
            novo_cliente.foto = dados["foto"]
        
        db.add(novo_cliente)
        db.commit()
        db.refresh(novo_cliente)
        
        return {"mensagem": "Conta criada com sucesso!", "cliente_id": novo_cliente.id}
        
    except HTTPException as he:
        raise he # Repassa os erros 400 conhecidos
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno ao criar conta: {str(e)}")


@app.post("/api/cliente/login")
def login_cliente_cardapio(dados: LoginClienteData, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == dados.telefone).first()
    
    # Blindagem 1: Puxa a senha de forma segura
    senha_salva = getattr(cliente, 'senha', None)
    if not cliente or not senha_salva:
        raise HTTPException(status_code=401, detail="Telefone ou senha incorretos.")
        
    # Blindagem 2: Verifica a senha com ou sem hash
    senha_valida = False
    try:
        if pwd_context.verify(dados.senha, senha_salva):
            senha_valida = True
    except:
        pass
        
    if dados.senha == senha_salva: 
        senha_valida = True
        
    if not senha_valida:
        raise HTTPException(status_code=401, detail="Telefone ou senha incorretos.")
    
    # Blindagem 3: Puxa os dados com getattr e fallback para nunca enviar nulo (evitando quebrar o JS!)
    endereco_formatado = f"{getattr(cliente, 'endereco', '')}, {getattr(cliente, 'numero', '')} - {getattr(cliente, 'bairro', '')} ({getattr(cliente, 'complemento', '')})"
    
    return {
        "status": "sucesso",
        "cliente": {
            "id": getattr(cliente, 'id', 0),
            "nome": getattr(cliente, 'nome', 'Visitante') or 'Visitante',
            "telefone": getattr(cliente, 'telefone', ''),
            "cpf": getattr(cliente, 'cpf', ''),
            "foto": getattr(cliente, 'foto', ''),
            "endereco_completo": endereco_formatado,
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
        for item in getattr(p, 'itens', getattr(p, 'itens_pedido', [])):
            prod = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
            nome_prod = prod.nome if prod else "Produto Indisponível"
            resumo_itens.append(f"{item.quantidade}x {nome_prod}")
        
        historico.append({
            "id": p.id,
            "senha_diaria": getattr(p, 'senha_diaria', p.id),
            "status": str(p.status).split('.')[-1].upper(),
            "total": p.total_pago,
            "itens_resumo": ", ".join(resumo_itens)
        })
        
    return historico


# ==========================================
# WEBHOOKS DE PAGAMENTO
# ==========================================

@app.post("/api/webhooks/mercadopago")
async def webhook_mercadopago(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        if payload.get("type") == "payment" or payload.get("action") == "payment.created":
            payment_id = payload.get("data", {}).get("id")
            pass
        return {"status": "ok"}
    except Exception as e:
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
                pedido_id = int(pedido_id_str)
                pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
                
                if pedido and str(pedido.status).split('.')[-1].upper() != "RECEBIDO":
                    pedido.status = "RECEBIDO" 
                    db.commit()
                    print(f"✅ PAGAMENTO ASAAS CONFIRMADO! Pedido #{pedido_id} liberado.")
                    
        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Erro Webhook Asaas: {e}")
        return {"status": "erro"}


# ==========================================
# VENDAS ONLINE E PDV (CAIXA)
# ==========================================

@app.post("/api/pedidos/online")
def receber_pedido_site(pedido_web: CheckoutPedido, forma_pagamento: str = Query("entrega"), db: Session = Depends(get_db)):
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
        
    itens_carrinho = []
    for i in pedido_web.itens:
        itens_carrinho.append({
            "produto_id": i.produto_id, 
            "quantidade": i.quantidade, 
            "observacao": i.observacao
        })
    
    if pedido_web.endereco_cliente and len(itens_carrinho) > 0:
        obs_atual = itens_carrinho[0]["observacao"]
        itens_carrinho[0]["observacao"] = f"Endereço: {pedido_web.endereco_cliente} | {obs_atual}"

    novo_pedido = registrar_venda_pdv(
        db=db, 
        tipo=TipoPedido.DELIVERY, 
        itens_carrinho=itens_carrinho, 
        cliente_id=cliente.id
    )

    novo_pedido_real = db.query(PedidoModel).filter(PedidoModel.id == novo_pedido.id).first()
    novo_pedido_real.senha_diaria = gerar_senha_diaria(db)
    novo_pedido_real.origem = "SITE (Online)"
    novo_pedido_real.data_pedido = datetime.utcnow().date()

    for item in itens_carrinho:
        processar_baixa_estoque(
            db, 
            produto_id=item["produto_id"], 
            quantidade_vendida=item["quantidade"]
        )
    
    if forma_pagamento in ["pix", "credito", "vr"]:
        novo_pedido_real.status = "AGUARDANDO_PAGAMENTO"
        db.commit()
    else:
        novo_pedido_real.status = "EM_PREPARO" if getattr(config, 'aceite_automatico', False) else "RECEBIDO"
        db.commit()
        notificar_status_pedido(cliente.telefone, cliente.nome, novo_pedido_real.senha_diaria, novo_pedido_real.status)

    if forma_pagamento == "pix":
        if not pedido_web.cpf:
            raise HTTPException(status_code=400, detail="CPF é obrigatório para gerar o Pix.")
        
        resultado_pix = criar_pagamento_pix_mp(
            novo_pedido_real.id, 
            novo_pedido_real.total_pago, 
            cliente.nome, 
            pedido_web.cpf
        )
        
        if type(resultado_pix) is dict and "qr_code" in resultado_pix:
            return {"status": "checkout_transparente", "copia_e_cola": resultado_pix["qr_code"]}
        else:
            novo_pedido_real.status = "CANCELADO"
            db.commit()
            raise HTTPException(status_code=400, detail="Mercado Pago recusou a transação.")
            
    elif forma_pagamento == "credito" or forma_pagamento == "vr":
        if not pedido_web.token_cartao or not pedido_web.cpf:
            raise HTTPException(status_code=400, detail="Faltam dados do cartão ou CPF para processar o pagamento.")
            
        resposta_pagamento = criar_pagamento_cartao_mp(
            pedido_id=novo_pedido_real.id, 
            valor_total=novo_pedido_real.total_pago, 
            token_cartao=pedido_web.token_cartao, 
            email_cliente=f"cliente{cliente.id}@artsburguer.com",
            payment_method_id=pedido_web.payment_method_id, 
            parcelas=pedido_web.parcelas, 
            cpf_cliente=pedido_web.cpf
        )
        
        if resposta_pagamento and resposta_pagamento.get("status") in ["approved", "in_process"]:
            novo_pedido_real.status = "EM_PREPARO" if getattr(config, 'aceite_automatico', False) else "RECEBIDO"
            db.commit()
            notificar_status_pedido(cliente.telefone, cliente.nome, novo_pedido_real.senha_diaria, novo_pedido_real.status)
            return {"status": "sucesso", "mensagem": "Pagamento aprovado!"}
        else:
            novo_pedido_real.status = "CANCELADO"
            db.commit()
            raise HTTPException(status_code=400, detail="Pagamento recusado pelo banco.")
            
    return {"status": "entrega", "mensagem": "Pedido confirmado para pagamento na entrega!"}


@app.get("/api/pdv/cliente/{telefone}")
def buscar_cliente_pdv(telefone: str, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == telefone).first()
    
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    return {
        "nome": cliente.nome,
        "pontos": getattr(cliente, 'pontos_fidelidade', 0),
        "cashback": getattr(cliente, 'saldo_cashback', 0.0),
        "bloqueado": getattr(cliente, 'bloqueado', False),
        "permite_fiado": getattr(cliente, 'permite_fiado', False) 
    }


@app.post("/api/pedidos/pdv")
def receber_pedido_balcao(pedido_caixa: CheckoutPDV, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == pedido_caixa.telefone_cliente).first()
    
    if not cliente:
        cliente = ClienteModel(
            nome=pedido_caixa.nome_cliente, 
            telefone=pedido_caixa.telefone_cliente
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    if getattr(cliente, 'bloqueado', False):
        raise HTTPException(status_code=403, detail="⚠️ Cliente está bloqueado por inadimplência!")

    itens_carrinho = []
    for i in pedido_caixa.itens:
        itens_carrinho.append({
            "produto_id": i.produto_id, 
            "quantidade": i.quantidade, 
            "observacao": i.observacao
        })
    
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
        novo_pedido_real.data_pedido = datetime.utcnow().date()
        
        config = db.query(ConfiguracaoLojaModel).first()
        
        if cliente.telefone != "BALCAO":
            sis_fidelidade = getattr(config, 'sistema_fidelidade', 'CASHBACK')
            
            if sis_fidelidade == "PONTOS":
                if pedido_caixa.usar_pontos and getattr(cliente, 'pontos_fidelidade', 0) >= 10:
                    cliente.pontos_fidelidade -= 10
                else:
                    cliente.pontos_fidelidade = getattr(cliente, 'pontos_fidelidade', 0) + 1 
            elif sis_fidelidade == "CASHBACK":
                saldo_atual = getattr(cliente, 'saldo_cashback', 0.0)
                if pedido_caixa.usar_saldo_cashback > 0 and saldo_atual >= pedido_caixa.usar_saldo_cashback:
                    cliente.saldo_cashback -= pedido_caixa.usar_saldo_cashback
                
                valor_real_pago = novo_pedido_real.total_pago - pedido_caixa.usar_saldo_cashback
                if valor_real_pago > 0:
                    cliente.saldo_cashback = getattr(cliente, 'saldo_cashback', 0.0) + (valor_real_pago * 0.05)

        for item in itens_carrinho:
            processar_baixa_estoque(
                db, 
                produto_id=item["produto_id"], 
                quantidade_vendida=item["quantidade"]
            )
            
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
# DEPARTAMENTO PESSOAL E RH CORPORATIVO (V5)
# ==========================================

@app.get("/api/gestao/cargos")
def listar_cargos(db: Session = Depends(get_db)):
    return db.query(Cargo).all()


@app.post("/api/gestao/cargos")
def criar_cargo_dinamico(dados: NovoCargo, db: Session = Depends(get_db)):
    cargo_existente = db.query(Cargo).filter(Cargo.nome == dados.nome).first()
    
    if cargo_existente:
        raise HTTPException(status_code=400, detail="Este cargo já existe na empresa.")
    
    novo_cargo = Cargo(
        nome=dados.nome, 
        permissoes=dados.permissoes
    )
    db.add(novo_cargo)
    db.commit()
    
    return {"status": "sucesso", "mensagem": "Cargo criado com sucesso e disponível para uso."}


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
        
        return {
            "status": "sucesso", 
            "mensagem": f"Pré-Cadastro criado! Matrícula: {novo_func.matricula_cracha}."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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
    
    rh.cpf = dados.cpf
    rh.rg = dados.rg
    rh.pis_pasep = dados.pis_pasep
    rh.data_nascimento = dados.data_nascimento
    rh.estado_civil = dados.estado_civil
    rh.titulo_eleitor = dados.titulo_eleitor
    rh.reservista = dados.reservista
    rh.cep = dados.cep
    rh.endereco_completo = dados.endereco_completo
    rh.banco = dados.banco
    rh.agencia = dados.agencia
    rh.conta = dados.conta
    rh.naturalidade = dados.naturalidade
    rh.escolaridade = dados.escolaridade
    rh.qtd_filhos_menores = dados.qtd_filhos_menores
    rh.cnh = dados.cnh
    rh.email = dados.email
    rh.plano_saude_escolhido = dados.plano_saude_escolhido
    
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
        
    func.senha_hash = "REVOGADO" 
    db.commit()
    
    return {"status": "sucesso", "mensagem": "Acesso revogado com sucesso."}

@app.put("/api/gestao/funcionarios/{func_id}/readmitir")
def readmitir_funcionario(func_id: int, senha_nova: str = Query(...), db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    
    if not func or not rh: 
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
        
    rh.status_admissao = "ATIVO"
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
        
        # Calcula horas trabalhadas
        fmt = "%H:%M"
        try:
            t1 = datetime.strptime(ponto.entrada, fmt)
            t2 = datetime.strptime(ponto.saida, fmt)
            diff = (t2 - t1).total_seconds() / 3600.0
            ponto.horas_trabalhadas = round(diff, 2)
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
        "horas_trabalhadas_mes": round(horas_trab, 2), 
        "dias_trabalhados": len(pontos)
    }


# ==========================================
# ROTAS GERAIS DE CARDÁPIO E COMPLEMENTOS
# ==========================================

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
        return {"status": "sucesso", "mensagem": "Complementos ativados no cardápio!"}
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


@app.post("/api/login")
def fazer_login(dados: LoginData, db: Session = Depends(get_db)):
    funcionario = db.query(FuncionarioModel).filter(FuncionarioModel.usuario == dados.usuario).first()
    
    if not funcionario or not pwd_context.verify(dados.senha, funcionario.senha_hash):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos!")
    
    cargo = db.query(Cargo).filter(Cargo.id == funcionario.cargo_id).first()
    
    return { 
        "status": "sucesso", 
        "nome": funcionario.nome, 
        "cargo_id": funcionario.cargo_id, 
        "cargo_nome": cargo.nome if cargo else "Indefinido" 
    }


@app.get("/api/cardapio")
def listar_cardapio_digital(db: Session = Depends(get_db)): 
    # Filtro Mágico: Traz tudo, MENOS a categoria "Integrações"
    produtos = db.query(ProdutoModel).filter(ProdutoModel.categoria != "Integrações").all()
    lista_formatada = []
    
    for p in produtos:
        lista_formatada.append({
            "id": p.id,
            "nome": p.nome,
            "descricao": getattr(p, "descricao", ""),
            "preco_venda": p.preco_venda,
            "categoria": p.categoria,
            "imagem_url": getattr(p, "imagem_url", "")
        })
        
    return lista_formatada


@app.post("/api/gestao/produto")
def receber_novo_produto(produto: NovoProduto, db: Session = Depends(get_db)):
    try:
        novo_produto = ProdutoModel(
            nome=produto.nome, 
            descricao=produto.descricao,
            preco_venda=produto.preco, 
            categoria=produto.categoria,
            imagem_url=produto.imagem_url
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
    try:
        produto = db.query(ProdutoModel).filter(ProdutoModel.id == produto_id).first()
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado.")
        
        if "nome" in dados: produto.nome = dados["nome"]
        if "descricao" in dados: produto.descricao = dados["descricao"]
        if "preco" in dados: produto.preco_venda = dados["preco"]
        if "imagem_url" in dados: produto.imagem_url = dados["imagem_url"]
        if "categoria" in dados: produto.categoria = dados["categoria"]
        if "ativo" in dados: produto.ativo = dados["ativo"]
        if "participa_fidelidade" in dados: produto.participa_fidelidade = dados["participa_fidelidade"]
        
        db.commit()
        return {"mensagem": "Produto atualizado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gestao/insumos")
def listar_insumos_disp(db: Session = Depends(get_db)):
    insumos = db.query(InsumoModel).order_by(InsumoModel.nome.asc()).all()
    lista_formatada = []
    
    for i in insumos:
        lista_formatada.append({
            "id": i.id, 
            "nome": i.nome, 
            "unidade": i.unidade_medida, 
            "quantidade_atual": i.quantidade_atual, 
            "quantidade_minima": i.quantidade_minima, 
            "custo": i.custo_unitario
        })
        
    return lista_formatada


@app.post("/api/gestao/insumo")
def receber_novo_insumo(insumo: NovoInsumo, db: Session = Depends(get_db)):
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


@app.delete("/api/gestao/insumo/{insumo_id}")
def deletar_insumo(insumo_id: int, db: Session = Depends(get_db)):
    insumo = db.query(InsumoModel).filter(InsumoModel.id == insumo_id).first()
    if not insumo:
        raise HTTPException(status_code=404)
        
    db.delete(insumo)
    db.commit()
    return {"status": "sucesso"}


# ==========================================
# ROTAS FINANCEIRAS E RELATÓRIOS DRE
# ==========================================

@app.post("/api/gestao/conta")
def receber_nova_conta(conta: NovaConta, db: Session = Depends(get_db)):
    try:
        fornecedor_id = conta.fornecedor_id
        if not fornecedor_id:
            fornecedor = db.query(FornecedorModel).first()
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
    
    lista = []
    for c in contas:
        lista.append({
            "id": c.id, 
            "descricao": c.descricao, 
            "valor": c.valor, 
            "vencimento": c.data_vencimento.strftime("%d/%m/%Y"), 
            "tipo": c.tipo_despesa, 
            "status": c.status
        })
    
    return {"total_empresa": total_empresa, "total_casa": total_casa, "contas": lista}


@app.get("/api/gestao/financeiro/lucratividade")
def obter_relatorio_lucratividade(data_inicio: str = None, data_fim: str = None, db: Session = Depends(get_db)):
    query_pedidos = db.query(PedidoModel).filter(PedidoModel.status != "CANCELADO")
    query_contas = db.query(ContaPagarModel)
    
    if data_inicio and data_fim:
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
    
    # Tratamento contra o bug de datas "undefined" do frontend
    if data_inicio and data_fim and data_inicio != "undefined" and data_fim != "undefined":
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            df = datetime.strptime(data_fim, "%Y-%m-%d").date()
            query = query.filter(PedidoModel.data_pedido >= di, PedidoModel.data_pedido <= df)
        except Exception: 
            pass
            
    ranking = {}
    
    for pedido in query.all():
        for item in getattr(pedido, 'itens', getattr(pedido, 'itens_pedido', [])):
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
    
    for item in getattr(pedido, 'itens', getattr(pedido, 'itens_pedido', [])):
        prod = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
        nome_prod = prod.nome if prod else "Produto Indisponível"
        preco_unit = prod.preco_venda if prod else 0.0
        obs = getattr(item, 'observacao', getattr(item, 'observacoes', ''))
        
        itens_formatados.append({
            "quantidade": item.quantidade,
            "nome": nome_prod,
            "preco_unitario": preco_unit,
            "subtotal": item.quantidade * preco_unit,
            "observacao": obs
        })
    
    endereco = "Retirada no Balcão"
    tipo_pedido = str(getattr(pedido, 'tipo_pedido', getattr(pedido, 'tipo', ''))).split('.')[-1].upper()
    
    if tipo_pedido == "DELIVERY":
        if itens_formatados and "Endereço:" in itens_formatados[0]["observacao"]:
            partes = itens_formatados[0]["observacao"].split(" | ")
            for p in partes:
                if "Endereço:" in p:
                    endereco = p.replace("Endereço:", "").strip()
                    itens_formatados[0]["observacao"] = itens_formatados[0]["observacao"].replace(p, "").replace("|", "").strip()
                    break
        elif cliente and getattr(cliente, 'logradouro', ''):
            endereco = f"{cliente.logradouro}, {cliente.numero} - {cliente.bairro}"

    return {
        "id": pedido.id,
        "senha_diaria": getattr(pedido, 'senha_diaria', pedido.id),
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
# ROTAS DE LOGÍSTICA E KDS
# ==========================================

@app.get("/api/logistica/pedidos")
def listar_pedidos_logistica(db: Session = Depends(get_db)):
    pedidos = db.query(PedidoModel).order_by(desc(PedidoModel.id)).all()
    prontos, em_rota = [], []
    
    for p in pedidos:
        status_atual = str(p.status).split('.')[-1].upper()
        tipo_atual = str(getattr(p, 'tipo_pedido', getattr(p, 'tipo', ''))).split('.')[-1].upper()
        
        if tipo_atual not in ["DELIVERY", "RETIRADA"]: 
            continue
        
        endereco_completo = 'Retirada no Balcão' if tipo_atual == 'RETIRADA' else 'Endereço não informado'
        
        for item in getattr(p, 'itens', getattr(p, 'itens_pedido', [])):
            obs = getattr(item, 'observacao', getattr(item, 'observacoes', ''))
            if obs and "Endereço: " in obs:
                partes = obs.split(" | ")
                for parte in partes:
                    if "Endereço: " in parte:
                        endereco_completo = parte.replace("Endereço: ", "").strip()
                        break
                break
                
        dados_pedido = { 
            "id": p.id,  
            "senha_diaria": getattr(p, 'senha_diaria', p.id),
            "origem": getattr(p, 'origem', 'SITE'),
            "cliente": p.cliente.nome if p.cliente else "Cliente", 
            "telefone": p.telefone_cliente, # <--- ESSA É A LINHA MÁGICA QUE FALTAVA
            "status": status_atual,  
            "endereco": endereco_completo,
            "tipo": tipo_atual
        }
        
        if status_atual == "PRONTO": 
            prontos.append(dados_pedido)
        elif status_atual == "SAIU_PARA_ENTREGA": 
            em_rota.append(dados_pedido)
            
    return {"prontos": prontos, "em_rota": em_rota}


@app.put("/api/logistica/pedidos/{pedido_id}/despachar")
def despachar_pedido(pedido_id: int, payload: DespachoMotoboy, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    
    if not pedido: 
        raise HTTPException(status_code=404)
        
    pedido.status = "SAIU_PARA_ENTREGA"
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', pedido.id)
        notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, "SAIU_PARA_ENTREGA")
        
    return {"status": "sucesso"}


@app.put("/api/logistica/pedidos/{pedido_id}/entregar")
def concluir_entrega_final(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    
    if not pedido: 
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    
    pedido.status = "ENTREGUE"
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', pedido.id)
        notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, "ENTREGUE")
        
    return {"status": "sucesso", "mensagem": "Baixa realizada e cliente notificado!"}


@app.get("/api/kds/pedidos")
def listar_pedidos_cozinha(db: Session = Depends(get_db)):
    pedidos_ativos = db.query(PedidoModel).order_by(PedidoModel.id.asc()).all()
    lista_kds = []
    
    for pedido in pedidos_ativos:
        status_atual = str(pedido.status).split('.')[-1].upper()
        if status_atual not in ["RECEBIDO", "EM_PREPARO", "PRONTO"]: 
            continue
            
        tipo_atual = str(getattr(pedido, 'tipo_pedido', getattr(pedido, 'tipo', ''))).split('.')[-1].upper()
        
        itens = []
        for item in getattr(pedido, 'itens', getattr(pedido, 'itens_pedido', [])):
            produto = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
            obs = getattr(item, 'observacao', getattr(item, 'observacoes', ''))
            itens.append({
                "quantidade": item.quantidade, 
                "nome_produto": produto.nome if produto else "Removido", 
                "observacao": obs
            })
            
        lista_kds.append({
            "id": pedido.id, 
            "senha_diaria": getattr(pedido, 'senha_diaria', pedido.id),
            "origem": getattr(pedido, 'origem', 'SITE'),
            "tipo": tipo_atual, 
            "status": status_atual, 
            "itens": itens
        })
        
    return lista_kds


@app.put("/api/kds/pedidos/{pedido_id}/status")
def mudar_status_pedido(pedido_id: int, payload: AtualizarStatus, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido: 
        raise HTTPException(status_code=404)
    
    novo_status = payload.status.upper()
    pedido.status = novo_status
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', pedido.id)
        notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, novo_status)
        
    return {"mensagem": "Status atualizado"}

        # ==========================================
# MÓDULO DE RASTREIO GPS AO VIVO (ESTILO UBER)
# ==========================================
# Dicionário em memória: Rápido, não trava o servidor e zera o custo de banco de dados!
rastreio_ao_vivo = {}

class CoordenadasGPS(BaseModel):
    pedido_id: int
    lat: float
    lng: float

@app.post("/api/logistica/gps")
def atualizar_gps_motoboy(dados: CoordenadasGPS):
    # O celular do motoboy "grita" as coordenadas a cada 5 segundos
    rastreio_ao_vivo[dados.pedido_id] = {
        "lat": dados.lat, 
        "lng": dados.lng, 
        "atualizado_em": datetime.now().isoformat()
    }
    return {"status": "ok"}

@app.get("/api/logistica/gps/{pedido_id}")
def obter_gps_motoboy(pedido_id: int):
    # O mapa do cliente pergunta onde o motoboy está
    if pedido_id in rastreio_ao_vivo:
        return {"status": "online", "posicao": rastreio_ao_vivo[pedido_id]}
    return {"status": "offline"}

# ------------------------------------------
# ROTAS VISUAIS DO RASTREIO
# ------------------------------------------
@app.get("/motoboy", response_class=HTMLResponse)
def abrir_tela_motoboy(): 
    if Path("templates/motoboy.html").exists():
        return Path("templates/motoboy.html").read_text(encoding="utf-8")
    return "Erro: Arquivo motoboy.html não encontrado."

@app.get("/mapa", response_class=HTMLResponse)
def abrir_mapa_cliente(): 
    if Path("templates/mapa.html").exists():
        return Path("templates/mapa.html").read_text(encoding="utf-8")
    return "Erro: Arquivo mapa.html não encontrado."

# ==========================================
# ROTAS DE CONFIGURAÇÃO DA LOJA (SETUP CENTRAL)
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
        # Busca a configuração no banco
        config = db.query(ConfiguracaoLojaModel).first()
        
        # Se não existir, cria a primeira
        if not config: 
            config = ConfiguracaoLojaModel()
            db.add(config)
            db.commit()
            db.refresh(config)

        # O Laço Mágico
        for key, value in dados.items():
            if hasattr(config, key):
                setattr(config, key, value)
                
        db.commit()
        return {"status": "sucesso"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gestao/clientes")
def listar_clientes_gestao(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        
        # Acesso Direto (Raw SQL) - Ignora qualquer erro de coluna faltando
        resultado = db.execute(text("SELECT * FROM clientes")).mappings().all()
        
        lista_blindada = []
        for c in resultado:
            lista_blindada.append({
                "id": c.get("id"),
                "nome": c.get("nome") or "Visitante",
                "telefone": c.get("telefone") or "Sem Contato",
                "pontos": c.get("pontos") or 0,
                "cashback": c.get("cashback") or 0.0,
                "bloqueado": bool(c.get("bloqueado")),
                
                # O .get() protege o sistema. Se a coluna não existir, ele envia em branco sem travar!
                "cpf": c.get("cpf", ""),
                "cep": c.get("cep", ""),
                "endereco": c.get("endereco", ""),
                "data_nascimento": c.get("data_nascimento", "") # <--- AGORA PUXANDO O ANIVERSÁRIO!
            })
            
        return lista_blindada
    except Exception as e:
        print("Erro Crítico no GET Clientes:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

        # ==========================================
# MOTOR UNIVERSAL DE GESTÃO (CRUD FASE 4)
# ==========================================
def pegar_modelo_banco(tabela: str):
    # Traduz o nome da URL para a tabela real do banco
    if tabela == "insumos": return InsumoModel
    if tabela == "fornecedores": return FornecedorModel
    if tabela == "financeiro": return ContaPagarModel
    if tabela == "funcionarios": return FuncionarioModel
    if tabela == "cupons": return CupomModel 
    return None

# ROTA PARA EDITAR (QUALQUER COISA)
@app.put("/api/gestao/{tabela}/{item_id}")
def atualizar_item_generico(tabela: str, item_id: int, dados: dict, db: Session = Depends(get_db)):
    try:
        modelo = pegar_modelo_banco(tabela)
        if not modelo: raise HTTPException(status_code=404, detail="Tabela não encontrada no Motor.")
        
        item = db.query(modelo).filter(modelo.id == item_id).first()
        if not item: raise HTTPException(status_code=404, detail="Item não encontrado no banco.")
        
        # O Mágico: Atualiza apenas as colunas que vieram do painel!
        for chave, valor in dados.items():
            if hasattr(item, chave) and chave != "id":
                setattr(item, chave, valor)
                
        db.commit()
        return {"status": "ok", "mensagem": "Atualizado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ROTA PARA CRIAR (QUALQUER COISA)
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

# ROTA PARA DELETAR SEM ERRO (QUALQUER COISA)
@app.delete("/api/gestao/{tabela}/{item_id}")
def deletar_item_generico(tabela: str, item_id: int, db: Session = Depends(get_db)):
    try:
        modelo = pegar_modelo_banco(tabela)
        if not modelo: raise HTTPException(status_code=404)
        
        db.query(modelo).filter(modelo.id == item_id).delete()
        db.commit()
        return {"status": "ok", "mensagem": "Apagado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
@app.put("/api/gestao/clientes/{cliente_id}")
def atualizar_dossie_cliente(cliente_id: int, dados: dict = Body(...), db: Session = Depends(get_db)):
    try:
        cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado na base.")
        
        if "nome" in dados: cliente.nome = dados["nome"]
        if "telefone" in dados: cliente.telefone = dados["telefone"]
        if "cpf" in dados: cliente.cpf = dados["cpf"]
        if "cep" in dados: cliente.cep = dados["cep"]
        if "endereco" in dados: cliente.endereco = dados["endereco"]
        if "pontos" in dados: cliente.pontos = dados["pontos"]
        if "cashback" in dados: cliente.cashback = dados["cashback"]
        if "bloqueado" in dados: cliente.bloqueado = dados["bloqueado"]
        
        db.commit()
        return {"mensagem": "Dossiê do cliente atualizado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gestao/clientes/{cliente_id}/pedidos")
def historico_pedidos_cliente(cliente_id: int, db: Session = Depends(get_db)):
    try:
        cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
        if not cliente: return []
        
        # Busca os últimos 10 pedidos do cliente pelo telefone
        pedidos = db.query(PedidoModel).filter(PedidoModel.telefone_cliente == cliente.telefone).order_by(PedidoModel.id.desc()).limit(10).all()
        
        return [{
            "id": p.id,
            "data": p.data_pedido.strftime("%d/%m/%Y %H:%M") if p.data_pedido else "N/A",
            "valor": p.valor_total,
            "status": p.status,
            "pagamento": p.forma_pagamento
        } for p in pedidos]
    except Exception as e:
        return []

@app.put("/api/gestao/clientes/{cliente_id}/editar")
def editar_cliente(cliente_id: int, dados: dict, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    
    if not cliente: 
        raise HTTPException(status_code=404)
        
    cliente.nome = dados.get("nome", cliente.nome)
    cliente.telefone = dados.get("telefone", cliente.telefone)
    cliente.pontos_fidelidade = int(dados.get("pontos", cliente.pontos_fidelidade))
    cliente.saldo_cashback = float(dados.get("cashback", cliente.saldo_cashback))
    
    db.commit()
    return {"status": "sucesso"}


@app.put("/api/gestao/clientes/{cliente_id}/bloqueio")
def alternar_bloqueio_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    
    if not cliente: 
        raise HTTPException(status_code=404)
        
    cliente.bloqueado = not getattr(cliente, 'bloqueado', False)
    db.commit()
    return {"status": "sucesso"}


@app.delete("/api/gestao/clientes/{cliente_id}")
def deletar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    
    if not cliente: 
        raise HTTPException(status_code=404)
        
    db.delete(cliente)
    db.commit()
    return {"status": "sucesso"}


# ==========================================
# ROTAS VISUAIS (TELAS HTML SERVIDAS PELO FASTAPI)
# ==========================================

@app.get("/portal", response_class=HTMLResponse)
def abrir_portal_central(): 
    if Path("templates/portal.html").exists():
        return Path("templates/portal.html").read_text(encoding="utf-8")
    return "Erro: Arquivo portal.html não encontrado na pasta templates."
    
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
    if Path("templates/tv.html").exists():
        return Path("templates/tv.html").read_text(encoding="utf-8")
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


# ==========================================
# INCLUSÃO DE ROUTERS EXTRAS E WEBHOOKS
# ==========================================

app.include_router(router_dashboard)
app.include_router(router_pagamentos)
app.include_router(router_99food)

@app.get("/api/gestao/notificacoes")
def checar_novos_pedidos(db: Session = Depends(get_db)):
    qtd_novos = db.query(PedidoModel).filter(PedidoModel.status == "RECEBIDO").count()
    return {"pendentes": qtd_novos}

@app.post("/api/webhooks/ifood")
async def webhook_ifood(request: Request, db: Session = Depends(get_db)): 
    return {"status": "ok"}

@app.post("/api/webhooks/99food")
async def webhook_99food(request: Request, db: Session = Depends(get_db)): 
    return {"status": "ok"}

@app.post("/api/webhooks/redes-sociais")
async def webhook_social(request: Request): 
    return {"status": "ok"}

@app.post("/api/webhooks/whatsapp-receber")
def receber_mensagem_cliente(payload: dict): 
    return {"status": "sucesso"}

class EditarPerfilColaborador(BaseModel):
    nome: str
    telefone: str
    email: str
    cep: str
    endereco_completo: str
    qtd_filhos_menores: int
    foto_3x4: str

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

@app.put("/api/gestao/clientes/{cliente_id}/fiado")
def alternar_fiado_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    
    if not cliente: 
        raise HTTPException(status_code=404)
        
    cliente.permite_fiado = not getattr(cliente, 'permite_fiado', False)
    db.commit()
    
    return {"status": "sucesso"}

@app.delete("/api/sistema/zerar-dados")
def limpar_banco_dados(db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        db.execute(text("DELETE FROM itens_complemento"))
        db.execute(text("DELETE FROM grupos_complemento"))
        db.execute(text("DELETE FROM fichas_tecnicas"))
        db.query(ItemPedidoModel).delete()
        db.query(PedidoModel).delete()
        db.query(ProdutoModel).delete()
        db.query(InsumoModel).delete()
        db.query(ContaPagarModel).delete()
        db.query(FornecedorModel).delete()
        db.query(ClienteModel).delete() # 🚨 APAGA CLIENTES
        db.query(PontoModel).delete()
        db.query(OcorrenciaRHModel).delete()
        db.query(SolicitacaoFeriasModel).delete()
        db.query(InfoRHModel).delete()
        db.query(FuncionarioModel).filter(FuncionarioModel.id > 1).delete() # 🚨 APAGA EQUIPE
        db.commit()
        return {"mensagem": "Sistema Limpo! Vendas, Clientes e RH zerados."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cura-final")
def forcar_colunas_fidelidade(db: Session = Depends(get_db)):
    from sqlalchemy import text
    comandos = [
        "ALTER TABLE clientes ADD COLUMN pontos INTEGER DEFAULT 0;",
        "ALTER TABLE clientes ADD COLUMN cashback FLOAT DEFAULT 0.0;",
        "ALTER TABLE clientes ADD COLUMN bloqueado BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE cupons_desconto ADD COLUMN tipo VARCHAR DEFAULT 'PERCENTUAL';",
        "ALTER TABLE cupons_desconto ADD COLUMN valor FLOAT DEFAULT 0.0;"
    ]
    logs = []
    for cmd in comandos:
        try:
            db.execute(text(cmd))
            db.commit()
            logs.append(f"SUCESSO: {cmd}")
        except Exception as e:
            db.rollback()
            logs.append(f"Ignorado (Já existe): {str(e)}")
            
    return {"status": "Colunas injetadas e corrigidas!", "resultado": logs}

@app.get("/api/consertar-banco")
def consertar_banco(db: Session = Depends(get_db)):
    from sqlalchemy import text
    comandos = [
        # Configurações da Loja
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
        
        # Produtos e Cardápio
        "ALTER TABLE produtos ADD COLUMN ativo BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE produtos ADD COLUMN participa_fidelidade BOOLEAN DEFAULT TRUE;",
        
        # Recursos Humanos (RH)
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
        
        # CRM e Clientes
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
        "ALTER TABLE clientes ADD COLUMN bloqueado BOOLEAN DEFAULT FALSE;"
    ]
    
    logs = []
    for cmd in comandos:
        try:
            db.execute(text(cmd))
            db.commit()
            logs.append(f"Sucesso: {cmd}")
        except Exception as e:
            db.rollback()
            logs.append(f"Ignorado: {str(e)}")
            
    return {"status": "Sincronização Mestra Concluída!", "logs": logs}

# ==========================================
# MOTOR DE EDIÇÃO E EXCLUSÃO (FASE 1)
# ==========================================

# 1. Atualizar Fornecedor
@app.put("/api/fornecedores/{fornecedor_id}")
def atualizar_fornecedor(fornecedor_id: int, dados: dict, db: Session = Depends(get_db)):
    from models import FornecedorModel # Certifique-se que o nome do seu model está correto
    fornecedor = db.query(FornecedorModel).filter(FornecedorModel.id == fornecedor_id).first()
    if not fornecedor:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    
    for key, value in dados.items():
        if hasattr(fornecedor, key):
            setattr(fornecedor, key, value)
            
    db.commit()
    return {"status": "sucesso", "mensagem": "Fornecedor atualizado!"}

# 2. Excluir Fornecedor
@app.delete("/api/fornecedores/{fornecedor_id}")
def excluir_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    from models import FornecedorModel
    fornecedor = db.query(FornecedorModel).filter(FornecedorModel.id == fornecedor_id).first()
    if not fornecedor:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
        
    db.delete(fornecedor)
    db.commit()
    return {"status": "sucesso", "mensagem": "Fornecedor excluído!"}

# 3. Atualizar Conta a Pagar
@app.put("/api/contas_pagar/{conta_id}")
def atualizar_conta(conta_id: int, dados: dict, db: Session = Depends(get_db)):
    from models import ContaPagarModel # Certifique-se que o nome do seu model está correto
    conta = db.query(ContaPagarModel).filter(ContaPagarModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    
    for key, value in dados.items():
        if hasattr(conta, key):
            setattr(conta, key, value)
            
    db.commit()
    return {"status": "sucesso", "mensagem": "Conta atualizada!"}

# 4. Excluir Conta a Pagar
@app.delete("/api/contas_pagar/{conta_id}")
def excluir_conta(conta_id: int, db: Session = Depends(get_db)):
    from models import ContaPagarModel
    conta = db.query(ContaPagarModel).filter(ContaPagarModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
        
    db.delete(conta)
    db.commit()
    return {"status": "sucesso", "mensagem": "Conta excluída!"}

# ==========================================
# MOTOR DE EDIÇÃO E EXCLUSÃO (FASE 2)
# ==========================================

# 1. Atualizar Produto (Cardápio)
@app.put("/api/gestao/produto/{produto_id}")
def atualizar_produto(produto_id: int, dados: dict, db: Session = Depends(get_db)):
    from models import ProdutoModel
    produto = db.query(ProdutoModel).filter(ProdutoModel.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    # Atualiza as informações (mapeamento inteligente)
    if 'nome' in dados: produto.nome = dados['nome']
    if 'descricao' in dados: produto.descricao = dados['descricao']
    if 'imagem_url' in dados: produto.imagem_url = dados['imagem_url']
    if 'categoria' in dados: produto.categoria = dados['categoria']
    if 'ativo' in dados: produto.ativo = dados['ativo']
    
    # O frontend manda como "preco", mas o banco salva como "preco_venda"
    if 'preco' in dados: produto.preco_venda = dados['preco']
        
    db.commit()
    return {"status": "sucesso", "mensagem": "Produto atualizado!"}

# 2. Excluir Produto Definitivamente
@app.delete("/api/gestao/produto/{produto_id}")
def excluir_produto(produto_id: int, db: Session = Depends(get_db)):
    from models import ProdutoModel
    produto = db.query(ProdutoModel).filter(ProdutoModel.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
        
    db.delete(produto)
    db.commit()
    return {"status": "sucesso", "mensagem": "Produto excluído permanentemente!"}

# 3. Atualizar Dossiê do Cliente (CRM)
@app.put("/api/gestao/clientes/{cliente_id}")
def atualizar_cliente(cliente_id: int, dados: dict, db: Session = Depends(get_db)):
    from models import ClienteModel
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    if 'nome' in dados: cliente.nome = dados['nome']
    if 'telefone' in dados: cliente.telefone = dados['telefone']
    
    # Blindagem de CPF Vazio
    if 'cpf' in dados: 
        novo_cpf = dados['cpf'].strip()
        if novo_cpf != "": 
            cliente.cpf = novo_cpf
            
    if 'cep' in dados: cliente.cep = dados['cep']
    if 'endereco' in dados: cliente.endereco = dados['endereco']
    if 'pontos' in dados: cliente.pontos = dados['pontos']
    if 'cashback' in dados: cliente.cashback = dados['cashback']
    if 'bloqueado' in dados: cliente.bloqueado = dados['bloqueado']
    
    db.commit()
    return {"status": "sucesso", "mensagem": "CRM do cliente atualizado!"}

# 4. Travar/Destravar Cliente Rápido
@app.put("/api/gestao/clientes/{cliente_id}/bloqueio")
def toggle_bloqueio_cliente(cliente_id: int, db: Session = Depends(get_db)):
    from models import ClienteModel
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # Se estava bloqueado, desbloqueia. Se estava liberado, bloqueia.
    cliente.bloqueado = not cliente.bloqueado
    db.commit()
    
    return {"status": "sucesso", "bloqueado": cliente.bloqueado}

# 5. Atualizar Insumo (Estoque)
@app.put("/api/gestao/insumo/{insumo_id}")
def atualizar_insumo(insumo_id: int, dados: dict, db: Session = Depends(get_db)):
    from models import InsumoModel
    insumo = db.query(InsumoModel).filter(InsumoModel.id == insumo_id).first()
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo não encontrado")

    if 'nome' in dados: insumo.nome = dados['nome']
    if 'unidade' in dados: insumo.unidade = dados['unidade']
    if 'quantidade' in dados: insumo.quantidade_atual = dados['quantidade']
    if 'minimo' in dados: insumo.quantidade_minima = dados['minimo']
    if 'custo' in dados: insumo.custo = dados['custo']

    db.commit()
    return {"status": "sucesso", "mensagem": "Insumo atualizado!"}

# 6. Atualizar Colaborador (Nome e Matrícula)
@app.put("/api/gestao/funcionarios/{func_id}")
def atualizar_funcionario(func_id: int, dados: dict, db: Session = Depends(get_db)):
    from models import FuncionarioModel
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not func:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")

    if 'nome' in dados: func.nome = dados['nome']
    if 'matricula' in dados: func.matricula = dados['matricula']

    db.commit()
    return {"status": "sucesso", "mensagem": "Colaborador atualizado!"}

# ==========================================
# MÁQUINA DE VENDAS: CUPONS E PROMOÇÕES
# ==========================================

from sqlalchemy import Column, Integer, String, Float, Boolean

class CupomModel(Base):
    __tablename__ = "cupons_desconto"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True)
    tipo = Column(String, default="PERCENTUAL") # PERCENTUAL ou VALOR_FIXO
    valor = Column(Float, default=0.0)
    desconto_percentual = Column(Float, default=0.0)
    desconto_fixo = Column(Float, default=0.0)
    ativo = Column(Boolean, default=True)
    data_validade = Column(dateTime, nullable=True) # <- AGORA ELA ESTÁ AQUI

@app.get("/api/gestao/cupons")
def listar_cupons(db: Session = Depends(get_db)):
    return db.query(CupomModel).all()

@app.post("/api/gestao/cupons")
def criar_cupom(dados: dict, db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    
    codigo = dados.get("codigo", "").upper().strip()
    if not codigo:
        raise HTTPException(status_code=400, detail="O código do cupom é obrigatório.")
        
    existe = db.query(CupomModel).filter(CupomModel.codigo == codigo).first()
    if existe:
        raise HTTPException(status_code=400, detail="Este código de cupom já existe.")
        
    tipo_cupom = dados.get("tipo", "PERCENTUAL")
    val_cupom = float(dados.get("valor", 0.0))
    
    # 🚨 BLINDAGEM MÁXIMA: Garante que NUNCA vai vazio pro PostgreSQL
    data_segura = datetime.utcnow() + timedelta(days=3650) # 10 anos de validade
    
    novo = CupomModel(
        codigo=codigo,
        tipo=tipo_cupom,
        valor=val_cupom,
        desconto_percentual=val_cupom if tipo_cupom == "PERCENTUAL" else 0.0,
        desconto_fixo=val_cupom if tipo_cupom == "VALOR_FIXO" else 0.0,
        ativo=True,
        data_validade=data_segura 
    )
    db.add(novo)
    db.commit()
    return {"status": "sucesso", "mensagem": f"Cupom {codigo} criado com sucesso!"}

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
    codigo = dados.get("codigo", "").upper().strip()
    subtotal = float(dados.get("subtotal", 0.0))
    
    cupom = db.query(CupomModel).filter(CupomModel.codigo == codigo, CupomModel.ativo == True).first()
    if not cupom:
        raise HTTPException(status_code=404, detail="Cupom inválido ou expirado.")
        
    desconto = 0.0
    if cupom.tipo == "PERCENTUAL":
        desconto = subtotal * (cupom.valor / 100.0)
    else:
        desconto = cupom.valor
        
    if desconto > subtotal:
        desconto = subtotal
        
    return {
        "status": "sucesso",
        "codigo": cupom.codigo,
        "tipo": cupom.tipo,
        "valor_desconto": round(desconto, 2),
        "total_com_desconto": round(subtotal - desconto, 2)
    }

# ==========================================
# MOTOR DE COMBOS (ASSISTENTE FAST FOOD)
# ==========================================

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

@app.post("/api/gestao/combo-maker")
def criar_combo_fast_food(combo: NovoComboFastFood, db: Session = Depends(get_db)):
    try:
        # 1. Cria o Produto Base (A capa do Combo na vitrine)
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
        
        # 2. Cria as Etapas Automáticas (Ex: "Escolha sua Bebida")
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
            
            # 3. Adiciona as opções de cada etapa
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
# MÓDULO DE CAIXA (ABERTURA, SANGRIA E FECHAMENTO)
# ==========================================

class CaixaTurnoModel(Base):
    __tablename__ = "caixa_turnos"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    operador = Column(String, default="Admin")
    data_abertura = Column(String) 
    data_fechamento = Column(String, nullable=True)
    saldo_inicial = Column(Float, default=0.0)
    entradas_saidas = Column(Float, default=0.0) # Sangria (-) ou Suprimento (+)
    total_vendas_dinheiro = Column(Float, default=0.0)
    total_vendas_outros = Column(Float, default=0.0)
    saldo_informado = Column(Float, default=0.0)
    status = Column(String, default="ABERTO") # ABERTO ou FECHADO

class AbrirCaixaSchema(BaseModel):
    operador: str
    saldo_inicial: float

class MovimentacaoCaixaSchema(BaseModel):
    valor: float
    tipo: str
    descricao: str

class FecharCaixaSchema(BaseModel):
    saldo_informado: float

@app.get("/api/pdv/caixa/atual")
def obter_caixa_atual(db: Session = Depends(get_db)):
    caixa = db.query(CaixaTurnoModel).filter(CaixaTurnoModel.status == "ABERTO").order_by(CaixaTurnoModel.id.desc()).first()
    if not caixa:
        return {"status": "fechado"}
        
    # Puxa as vendas do dia para calcular o que entrou na gaveta
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

@app.post("/api/pdv/caixa/abrir")
def abrir_caixa(dados: AbrirCaixaSchema, db: Session = Depends(get_db)):
    caixa_aberto = db.query(CaixaTurnoModel).filter(CaixaTurnoModel.status == "ABERTO").first()
    if caixa_aberto:
        raise HTTPException(status_code=400, detail="Já existe um caixa aberto.")
        
    novo_caixa = CaixaTurnoModel(
        operador=dados.operador,
        saldo_inicial=dados.saldo_inicial,
        data_abertura=datetime.now().strftime("%d/%m/%Y %H:%M"),
        status="ABERTO"
    )
    db.add(novo_caixa)
    db.commit()
    return {"status": "sucesso", "mensagem": "Caixa aberto com sucesso!"}

@app.post("/api/pdv/caixa/movimentacao")
def movimentar_caixa(dados: MovimentacaoCaixaSchema, db: Session = Depends(get_db)):
    caixa = db.query(CaixaTurnoModel).filter(CaixaTurnoModel.status == "ABERTO").first()
    if not caixa:
        raise HTTPException(status_code=400, detail="Nenhum caixa aberto no momento.")
        
    valor_real = dados.valor if dados.tipo == "SUPRIMENTO" else -dados.valor
    caixa.entradas_saidas += valor_real
    db.commit()
    return {"status": "sucesso"}

@app.post("/api/pdv/caixa/fechar")
def fechar_caixa(dados: FecharCaixaSchema, db: Session = Depends(get_db)):
    caixa = db.query(CaixaTurnoModel).filter(CaixaTurnoModel.status == "ABERTO").first()
    if not caixa:
        raise HTTPException(status_code=400, detail="Nenhum caixa aberto no momento.")
        
    caixa.status = "FECHADO"
    caixa.data_fechamento = datetime.now().strftime("%d/%m/%Y %H:%M")
    caixa.saldo_informado = dados.saldo_informado
    db.commit()
    return {"status": "sucesso", "mensagem": "Caixa fechado com sucesso!"}

# ==========================================
# APP DO CLIENTE: RASTREIO E PERFIL
# ==========================================
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
        
    if hasattr(c, 'cep'): c.cep = dados.cep
    c.endereco = dados.endereco
    if hasattr(c, 'numero'): c.numero = dados.numero
    if hasattr(c, 'bairro'): c.bairro = dados.bairro
    if hasattr(c, 'complemento'): c.complemento = dados.complemento
    
    if dados.senha and dados.senha.strip() != "":
        c.senha = dados.senha.strip()
        
    if dados.foto and dados.foto.strip() != "":
        if hasattr(c, 'foto'): 
            c.foto = dados.foto
        else:
            try:
                from sqlalchemy import text
                db.execute(text("ALTER TABLE clientes ADD COLUMN foto VARCHAR DEFAULT ''"))
                db.commit()
                c.foto = dados.foto
            except:
                pass
    
    db.commit()
    return {"status": "sucesso"}

@app.get("/api/rastreio/{busca}")
def rastrear_pedido_cliente(busca: str, db: Session = Depends(get_db)):
    hoje = datetime.utcnow().date()
    pedido = None
    
    if busca.isdigit() and len(busca) <= 4:
        pedido = db.query(PedidoModel).filter(PedidoModel.data_pedido == hoje, PedidoModel.senha_diaria == int(busca)).first()
    else:
        telefone = busca.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        pedido = db.query(PedidoModel).filter(PedidoModel.telefone_cliente == telefone).order_by(desc(PedidoModel.id)).first()
        
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        
    status_atual = str(pedido.status).split('.')[-1].upper()
    
    progresso = 20 # Recebido
    if status_atual == "EM_PREPARO": progresso = 50
    elif status_atual in ["PRONTO", "SAIU_PARA_ENTREGA"]: progresso = 80
    elif status_atual == "ENTREGUE": progresso = 100
    elif status_atual == "CANCELADO": progresso = 0
    
    return {
        "id": pedido.id,
        "senha": getattr(pedido, 'senha_diaria', pedido.id),
        "status": status_atual,
        "progresso": progresso,
        "tipo": str(getattr(pedido, 'tipo_pedido', getattr(pedido, 'tipo', ''))).split('.')[-1].upper(),
        "total": pedido.total_pago
    }

# ==========================================
# MÓDULO DE LOGÍSTICA (TAXAS DE ENTREGA)
# ==========================================
class TaxaEntregaModel(Base):
    __tablename__ = "taxas_entrega"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    bairro = Column(String, unique=True, index=True)
    taxa = Column(Float, default=0.0)

class TaxaEntregaSchema(BaseModel):
    bairro: str
    taxa: float

@app.get("/api/gestao/taxas")
def listar_taxas(db: Session = Depends(get_db)):
    return db.query(TaxaEntregaModel).all()

@app.post("/api/gestao/taxas")
def criar_taxa(dados: TaxaEntregaSchema, db: Session = Depends(get_db)):
    tx = db.query(TaxaEntregaModel).filter(TaxaEntregaModel.bairro == dados.bairro).first()
    if tx:
        tx.taxa = dados.taxa
    else:
        novo = TaxaEntregaModel(bairro=dados.bairro, taxa=dados.taxa)
        db.add(novo)
    db.commit()
    return {"status": "sucesso"}

@app.delete("/api/gestao/taxas/{id}")
def deletar_taxa(id: int, db: Session = Depends(get_db)):
    tx = db.query(TaxaEntregaModel).filter(TaxaEntregaModel.id == id).first()
    if tx:
        db.delete(tx)
        db.commit()
    return {"status": "sucesso"}

# ==========================================
# MÓDULO DE INTEGRAÇÕES (WEBHOOK IFOOD / 99FOOD)
# ==========================================

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

@app.post("/api/webhook/ifood")
def receber_pedido_externo(dados: ExtWebhookSchema, db: Session = Depends(get_db)):
    try:
        # 1. Cliente Genérico do iFood (Não polui o CRM)
        cliente = db.query(ClienteModel).filter(ClienteModel.nome == "🔴 Cliente iFood (Padrão)").first()
        if not cliente:
            cliente = ClienteModel(
                nome="🔴 Cliente iFood (Padrão)",
                telefone="00000000000",
                endereco="Integração iFood"
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)

        # 2. Cria um Produto "Coringa" via SQL Puro 
        produto_ifood = db.query(ProdutoModel).filter(ProdutoModel.nome == "Item iFood").first()
        if not produto_ifood:
            db.execute(text("""
                INSERT INTO produtos (nome, descricao, preco_venda, categoria, imagem_url, ativo, participa_fidelidade) 
                VALUES ('Item iFood', 'Integrador Externo', 0.0, 'Integrações', '', 1, false)
            """))
            db.commit()
            produto_ifood = db.query(ProdutoModel).filter(ProdutoModel.nome == "Item iFood").first()

        # 3. Monta o Carrinho Padrão (Colocando o nome real do lanche na observação)
        itens_carrinho = []
        for item in dados.items:
            obs_final = f"🔥 {item.name}"
            if item.options:
                obs_final += f" | ➕ {item.options}"
                
            if len(itens_carrinho) == 0 and dados.type.upper() == "DELIVERY" and dados.deliveryAddress:
                obs_final = f"📍 Endereço: {dados.deliveryAddress} | {obs_final}"
                
            itens_carrinho.append({
                "produto_id": produto_ifood.id,
                "quantidade": item.quantity,
                "observacao": obs_final
            })

        # 4. Registra usando o motor blindado do próprio sistema
        tipo_enum = TipoPedido.DELIVERY if dados.type.upper() == "DELIVERY" else TipoPedido.BALCAO

        novo_pedido = registrar_venda_pdv(
            db=db,
            tipo=tipo_enum,
            itens_carrinho=itens_carrinho,
            cliente_id=cliente.id
        )

        # 5. Ajustes finais da capa do pedido
        novo_pedido_real = db.query(PedidoModel).filter(PedidoModel.id == novo_pedido.id).first()
        
        senha_ext = int(dados.displayId) if dados.displayId.isdigit() else gerar_senha_diaria(db)
        novo_pedido_real.senha_diaria = senha_ext
        novo_pedido_real.origem = "iFood"
        novo_pedido_real.data_pedido = datetime.utcnow().date()
        novo_pedido_real.forma_pagamento = f"{dados.paymentMethod} (iFood)"
        
        if hasattr(novo_pedido_real, 'total_pago'):
            novo_pedido_real.total_pago = dados.totalPrice
        if hasattr(novo_pedido_real, 'valor_total'):
            novo_pedido_real.valor_total = dados.totalPrice
            
        novo_pedido_real.status = "RECEBIDO"
        
        db.commit()
        return {"status": "sucesso", "mensagem": "Pedido injetado com sucesso na Cozinha!"}
    except Exception as e:
        db.rollback() 
        print(f"Erro no Webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MOTOR PWA (APLICATIVO INSTALÁVEL)
# ==========================================

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
            {
                "src": "https://ui-avatars.com/api/?name=A+B&background=ff4757&color=fff&size=192",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://ui-avatars.com/api/?name=A+B&background=ff4757&color=fff&size=512",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return JSONResponse(content=manifest)

@app.get("/sw.js")
def get_service_worker():
    sw_content = """
    const CACHE_NAME = "arts-burguer-v1";
    self.addEventListener("install", (event) => {
        console.log("[PWA] Service Worker Instalado.");
        self.skipWaiting();
    });
    self.addEventListener("fetch", (event) => {
        event.respondWith(
            fetch(event.request).catch(() => {
                return new Response("Você está offline. Conecte-se à internet para fazer seu pedido.");
            })
        );
    });
    """
    return Response(content=sw_content, media_type="application/javascript")

if __name__ == "__main__":
    print("🚀 Iniciando Servidor Web do Art's Burguer V5 (Google Cloud Edition)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
