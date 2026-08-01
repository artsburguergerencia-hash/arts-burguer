from fastapi import FastAPI, Depends, HTTPException, Query, Request, Body
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from datetime import datetime, date
from sqlalchemy import desc
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
    ItemComplementoModel
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
        novo_fornecedor = FornecedorModel(
            nome_fantasia=dados.nome_fantasia, 
            categoria=dados.categoria, 
            contato=dados.contato, 
            cnpj=dados.cnpj
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

        # Cria o novo cliente capturando todos os campos novos do Cardápio
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
    
    if not cliente or not cliente.senha_hash or not pwd_context.verify(dados.senha, cliente.senha_hash):
        raise HTTPException(status_code=401, detail="Telefone ou senha incorretos.")
    
    return {
        "status": "sucesso",
        "cliente": {
            "id": cliente.id,
            "nome": cliente.nome,
            "telefone": cliente.telefone,
            "endereco_completo": f"{cliente.logradouro}, {cliente.numero} - {cliente.bairro} ({cliente.complemento})",
            "pontos": cliente.pontos_fidelidade,
            "cashback": cliente.saldo_cashback
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
    produtos = db.query(ProdutoModel).all()
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
        produto = db.query(Produto).filter(Produto.id == produto_id).first()
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
                "endereco": c.get("endereco", "")
            })
            
        return lista_blindada
    except Exception as e:
        print("Erro Crítico no GET Clientes:", str(e))
        raise HTTPException(status_code=500, detail=str(e))        
@app.put("/api/gestao/clientes/{cliente_id}")
def atualizar_dossie_cliente(cliente_id: int, dados: dict = Body(...), db: Session = Depends(get_db)):
    try:
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
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
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
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
    try:
        # Apaga os registros, mas mantém a estrutura das tabelas viva
        db.query(ItemPedido).delete()
        db.query(PedidoModel).delete()
        db.query(Produto).delete()
        db.query(Insumo).delete()
        db.query(Cliente).delete()
        db.query(ContaPagar).delete()
        db.query(Fornecedor).delete()
        db.commit()
        return {"mensagem": "Dados de teste apagados! O sistema está limpo para produção."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/consertar-banco")
def consertar_banco(db: Session = Depends(get_db)):
    from sqlalchemy import text
    comandos = [
        "ALTER TABLE clientes ADD COLUMN cpf VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN cep VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN endereco VARCHAR DEFAULT '';",
        "ALTER TABLE clientes ADD COLUMN permite_fiado BOOLEAN DEFAULT 0;"
    ]
    logs = []
    for cmd in comandos:
        try:
            db.execute(text(cmd))
            db.commit()
            logs.append(f"Sucesso: {cmd}")
        except Exception as e:
            db.rollback()
            logs.append(f"Ignorado (já existe): {cmd}")
            
    return {"status": "Banco Atualizado a Força!", "logs": logs}
    
if __name__ == "__main__":
    print("🚀 Iniciando Servidor Web do Art's Burguer V5 (Google Cloud Edition)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
