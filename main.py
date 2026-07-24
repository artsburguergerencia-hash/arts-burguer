from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from pathlib import Path
from datetime import datetime
from sqlalchemy import desc
import uvicorn
from passlib.context import CryptContext
from sqlalchemy import Column, Integer, String, Boolean, Float
from typing import Optional 
from fastapi import Request 

# Importações dos nossos módulos do Art's Burguer
from integracao_99food import router_99food
from pagamentos_pagbank import criar_pagamento_pix_mp, criar_link_pagamento_mp, criar_pagamento_cartao_mp
from database import SessionLocal, ProdutoModel, ProdutoCreateInput, criar_produto_com_ficha, cadastrar_insumo, engine, Base, FuncionarioModel, Cargo, InsumoModel, processar_baixa_estoque, FichaTecnicaModel
from vendas_pdv import ClienteModel, registrar_venda_pdv, TipoPedido, PedidoModel
from financeiro import lancar_conta_pagar, FornecedorModel, ContaPagarModel
from dashboard import router_dashboard
from pagamentos_crm import router_pagamentos
from database import inicializar_banco

# NOVA IMPORTAÇÃO: Apenas a função de envio automático
from whatsapp_ia import notificar_status_pedido

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
app = FastAPI(title="API - Art's Burguer", version="1.0.0")

from database import GrupoComplementoModel, ItemComplementoModel

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

class ConfiguracaoLojaModel(Base):
    __tablename__ = "configuracoes_loja"
    id = Column(Integer, primary_key=True, index=True)
    logo_url = Column(String, default="https://via.placeholder.com/150")
    aceita_delivery = Column(Boolean, default=True)
    aceita_retirada = Column(Boolean, default=True)
    aceite_automatico = Column(Boolean, default=False)
    tempo_preparo = Column(Integer, default=30)
    formas_pagamento = Column(String, default="Pix,Dinheiro,Cartão")

# === NOVAS TABELAS DE RH E FOLHA DE PAGAMENTO ===
class InfoRHModel(Base):
    __tablename__ = "info_rh"
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer, unique=True)
    telefone = Column(String, default="")
    salario = Column(Float, default=0.0)
    escala = Column(String, default="")

class PontoModel(Base):
    __tablename__ = "pontos_rh"
    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer)
    data = Column(String) 
    entrada = Column(String, default="")
    saida = Column(String, default="")

inicializar_banco()
Base.metadata.create_all(bind=engine) # Cria as novas tabelas de RH sem apagar o resto!

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- SCHEMAS ---
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

class NovoFuncionario(BaseModel):
    nome: str
    usuario: str
    senha: str
    cargo_id: int
    foto: str = ""
    telefone: str = ""
    salario: float = 0.0
    escala: str = ""

class RegistroPonto(BaseModel):
    funcionario_id: int
    tipo: str # "entrada" ou "saida"

class AtualizarFuncionario(BaseModel):
    nome: str
    usuario: str
    senha: str = "" 
    cargo_id: int
    foto: str = ""

class NovoFornecedor(BaseModel):
    nome_fantasia: str
    categoria: str = "Geral"
    contato: str = ""
    cnpj: str = ""

# --- ROTAS DE VENDAS E DELIVERY ---
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
        novo = FornecedorModel(
            nome_fantasia=dados.nome_fantasia, 
            categoria=dados.categoria, 
            contato=dados.contato, 
            cnpj=dados.cnpj
        )
        db.add(novo)
        db.commit()
        db.refresh(novo)
        return {"status": "sucesso", "id": novo.id, "mensagem": "Fornecedor cadastrado com sucesso!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/api/cliente/registrar")
def registrar_cliente_cardapio(dados: RegistroClienteData, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == dados.telefone).first()
    if cliente:
        raise HTTPException(status_code=400, detail="Este telefone já está registado!")
    
    novo_cliente = ClienteModel(
        nome=dados.nome,
        telefone=dados.telefone,
        senha_hash=pwd_context.hash(dados.senha),
        cpf=dados.cpf,
        data_nascimento=dados.data_nascimento,
        cep=dados.cep,
        logradouro=dados.logradouro,
        numero=dados.numero,
        bairro=dados.bairro,
        complemento=dados.complemento
    )
    db.add(novo_cliente)
    db.commit()
    return {"status": "sucesso", "mensagem": "Conta criada com sucesso!"}

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
    pedidos = db.query(PedidoModel).filter(PedidoModel.cliente_id == cliente_id).order_by(desc(PedidoModel.id)).limit(10).all()
    historico = []
    for p in pedidos:
        resumo_itens = []
        for item in getattr(p, 'itens', getattr(p, 'itens_pedido', [])):
            prod = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
            nome_prod = prod.nome if prod else "Produto Indisponível"
            resumo_itens.append(f"{item.quantidade}x {nome_prod}")
        
        historico.append({
            "id": p.id,
            "status": str(p.status).split('.')[-1].upper(),
            "total": p.total_pago,
            "itens_resumo": ", ".join(resumo_itens)
        })
    return historico

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
        
@app.post("/api/pedidos/online")
def receber_pedido_site(pedido_web: CheckoutPedido, forma_pagamento: str = Query("entrega"), db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == pedido_web.telefone_cliente).first()
    if not cliente:
        cliente = ClienteModel(nome=pedido_web.nome_cliente, telefone=pedido_web.telefone_cliente)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        
    itens_carrinho = [{"produto_id": i.produto_id, "quantidade": i.quantidade, "observacao": i.observacao} for i in pedido_web.itens]
    
    if pedido_web.endereco_cliente and len(itens_carrinho) > 0:
        obs_atual = itens_carrinho[0]["observacao"]
        itens_carrinho[0]["observacao"] = f"Endereço: {pedido_web.endereco_cliente} | {obs_atual}"

    novo_pedido = registrar_venda_pdv(db=db, tipo=TipoPedido.DELIVERY, itens_carrinho=itens_carrinho, cliente_id=cliente.id)

    for item in itens_carrinho:
        processar_baixa_estoque(db, produto_id=item["produto_id"], quantidade_vendida=item["quantidade"])
    
    if forma_pagamento in ["pix", "credito", "vr"]:
        novo_pedido.status = "AGUARDANDO_PAGAMENTO"
        db.commit()
    else:
        novo_pedido.status = "RECEBIDO"
        db.commit()
        notificar_status_pedido(cliente.telefone, cliente.nome, novo_pedido.id, "RECEBIDO")

    if forma_pagamento == "pix":
        if not pedido_web.cpf: raise HTTPException(status_code=400, detail="CPF é obrigatório para gerar o Pix.")
            
        resultado_pix = criar_pagamento_pix_mp(novo_pedido.id, novo_pedido.total_pago, cliente.nome, pedido_web.cpf)
        
        if type(resultado_pix) is dict and "qr_code" in resultado_pix:
            codigo_limpo = resultado_pix["qr_code"]
            return {"status": "checkout_transparente", "copia_e_cola": codigo_limpo}
        else:
            novo_pedido.status = "CANCELADO"
            db.commit()
            motivo = resultado_pix.get("erro", "Erro desconhecido") if type(resultado_pix) is dict else "Falha de conexão com o banco."
            raise HTTPException(status_code=400, detail=f"Mercado Pago recusou: {motivo}")
            
    elif forma_pagamento == "credito" or forma_pagamento == "vr":
        if not pedido_web.token_cartao or not pedido_web.cpf:
            raise HTTPException(status_code=400, detail="Faltam dados do cartão ou CPF para processar o pagamento.")
            
        resposta_pagamento = criar_pagamento_cartao_mp(
            pedido_id=novo_pedido.id, 
            valor_total=novo_pedido.total_pago, 
            token_cartao=pedido_web.token_cartao, 
            email_cliente=f"cliente{cliente.id}@artsburguer.com",
            payment_method_id=pedido_web.payment_method_id, 
            parcelas=pedido_web.parcelas, 
            cpf_cliente=pedido_web.cpf
        )
        
        if resposta_pagamento and resposta_pagamento.get("status") in ["approved", "in_process"]:
            novo_pedido.status = "RECEBIDO"
            db.commit()
            notificar_status_pedido(cliente.telefone, cliente.nome, novo_pedido.id, "RECEBIDO")
            return {"status": "sucesso", "mensagem": "Pagamento aprovado!"}
        else:
            novo_pedido.status = "CANCELADO"
            db.commit()
            detalhe_erro = resposta_pagamento.get("status_detail", "Pagamento recusado pelo banco.") if resposta_pagamento else "Falha de conexão com a operadora."
            raise HTTPException(status_code=400, detail=f"Atenção: {detalhe_erro}")
            
    return {"status": "entrega", "mensagem": "Pedido confirmado para pagamento na entrega!"}
            
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

@app.get("/api/pdv/cliente/{telefone}")
def buscar_cliente_pdv(telefone: str, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.telefone == telefone).first()
    if not cliente: raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {
        "nome": cliente.nome,
        "pontos": getattr(cliente, 'pontos_fidelidade', 0),
        "cashback": getattr(cliente, 'saldo_cashback', 0.0),
        "bloqueado": getattr(cliente, 'bloqueado', False)
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
        novo_pedido = registrar_venda_pdv(db=db, tipo=TipoPedido.BALCAO, itens_carrinho=itens_carrinho, cliente_id=cliente.id)
        
        if cliente.telefone != "BALCAO":
            if pedido_caixa.usar_pontos and getattr(cliente, 'pontos_fidelidade', 0) >= 10:
                cliente.pontos_fidelidade -= 10
            else:
                cliente.pontos_fidelidade = getattr(cliente, 'pontos_fidelidade', 0) + 1 
            
            saldo_atual = getattr(cliente, 'saldo_cashback', 0.0)
            if pedido_caixa.usar_saldo_cashback > 0 and saldo_atual >= pedido_caixa.usar_saldo_cashback:
                cliente.saldo_cashback -= pedido_caixa.usar_saldo_cashback
            
            valor_real_pago = novo_pedido.total_pago - pedido_caixa.usar_saldo_cashback
            if valor_real_pago > 0:
                cliente.saldo_cashback = getattr(cliente, 'saldo_cashback', 0.0) + (valor_real_pago * 0.05)

        for item in itens_carrinho:
            processar_baixa_estoque(db, produto_id=item["produto_id"], quantidade_vendida=item["quantidade"])
            
        db.commit()
        return {"status": "sucesso", "pedido_id": novo_pedido.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro no PDV: {str(e)}")


# --- ROTAS DE GESTÃO DE RH (COLABORADORES E PONTO) ---
@app.get("/api/gestao/funcionarios")
def listar_funcionarios_rh(db: Session = Depends(get_db)):
    funcionarios = db.query(FuncionarioModel).all()
    hoje = datetime.now().strftime("%Y-%m-%d")
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
            "telefone": rh.telefone if rh else "",
            "salario": rh.salario if rh else 0.0,
            "escala": rh.escala if rh else "",
            "ponto_entrada": ponto_hoje.entrada if ponto_hoje else "",
            "ponto_saida": ponto_hoje.saida if ponto_hoje else ""
        })
    return lista

@app.post("/api/gestao/funcionarios")
def cadastrar_funcionario(dados: NovoFuncionario, db: Session = Depends(get_db)):
    try:
        existe = db.query(FuncionarioModel).filter(FuncionarioModel.usuario == dados.usuario).first()
        if existe: raise HTTPException(status_code=400, detail="Usuário já em uso.")
            
        novo_func = FuncionarioModel(
            nome=dados.nome, usuario=dados.usuario, 
            senha_hash=pwd_context.hash(dados.senha), cargo_id=dados.cargo_id
        )
        db.add(novo_func)
        db.flush() # Gera o ID do funcionário
        
        info_rh = InfoRHModel(funcionario_id=novo_func.id, telefone=dados.telefone, salario=dados.salario, escala=dados.escala)
        db.add(info_rh)
        db.commit()
        return {"status": "sucesso", "mensagem": "Colaborador cadastrado na Folha de Pagamento!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/gestao/funcionarios/{func_id}")
def demitir_funcionario(func_id: int, db: Session = Depends(get_db)):
    if func_id == 1: raise HTTPException(status_code=403, detail="Não é possível demitir o Administrador.")
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not func: raise HTTPException(status_code=404)
    db.delete(func)
    db.commit()
    return {"status": "sucesso", "mensagem": "Funcionário demitido e acesso revogado."}

@app.post("/api/gestao/ponto")
def bater_ponto_rh(dados: RegistroPonto, db: Session = Depends(get_db)):
    hoje = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M")
    
    ponto = db.query(PontoModel).filter(PontoModel.funcionario_id == dados.funcionario_id, PontoModel.data == hoje).first()
    
    if not ponto:
        ponto = PontoModel(funcionario_id=dados.funcionario_id, data=hoje)
        db.add(ponto)
        db.flush()
        
    if dados.tipo == "entrada":
        if ponto.entrada: return {"status": "erro", "detail": "Entrada já registrada hoje."}
        ponto.entrada = hora
    else:
        if not ponto.entrada: return {"status": "erro", "detail": "A pessoa precisa Bater a Entrada primeiro."}
        if ponto.saida: return {"status": "erro", "detail": "Saída já registrada hoje."}
        ponto.saida = hora
        
    db.commit()
    return {"status": "sucesso", "mensagem": f"Ponto de {dados.tipo.upper()} cravado às {hora}!"}


# --- OUTRAS ROTAS GERAIS ---
@app.post("/api/gestao/complementos")
def criar_grupo_complemento(payload: GrupoCompSchema, db: Session = Depends(get_db)):
    try:
        grupo = GrupoComplementoModel(
            produto_id=payload.produto_id, nome=payload.nome,
            obrigatorio=payload.obrigatorio, minimo_opcoes=payload.minimo_opcoes, maximo_opcoes=payload.maximo_opcoes
        )
        db.add(grupo)
        db.flush() 
        for item in payload.itens:
            db.add(ItemComplementoModel(grupo_id=grupo.id, nome=item.nome, preco_adicional=item.preco_adicional))
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
            "id": g.id, "nome": g.nome, "obrigatorio": g.obrigatorio,
            "min": g.minimo_opcoes, "max": g.maximo_opcoes, "itens": itens
        })
    return resultado

@app.post("/api/login")
def fazer_login(dados: LoginData, db: Session = Depends(get_db)):
    funcionario = db.query(FuncionarioModel).filter(FuncionarioModel.usuario == dados.usuario).first()
    if not funcionario or not pwd_context.verify(dados.senha, funcionario.senha_hash):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos!")
    cargo = db.query(Cargo).filter(Cargo.id == funcionario.cargo_id).first()
    return { "status": "sucesso", "nome": funcionario.nome, "cargo_id": funcionario.cargo_id, "cargo_nome": cargo.nome if cargo else "Indefinido" }

@app.get("/api/cardapio")
def listar_cardapio_digital(db: Session = Depends(get_db)): 
    produtos = db.query(ProdutoModel).all()
    return [
        {
            "id": p.id,
            "nome": p.nome,
            "descricao": getattr(p, "descricao", ""),
            "preco_venda": p.preco_venda,
            "categoria": p.categoria,
            "imagem_url": getattr(p, "imagem_url", "")
        }
        for p in produtos
    ]

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
            db.add(FichaTecnicaModel(produto_id=novo_produto.id, insumo_id=f.insumo_id, quantidade_necessaria=f.quantidade))
        db.commit()
        return {"status": "sucesso", "mensagem": "Produto criado com sucesso no cardápio!"}
    except Exception as e: 
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gestao/insumos")
def listar_insumos_disp(db: Session = Depends(get_db)):
    insumos = db.query(InsumoModel).order_by(InsumoModel.nome.asc()).all()
    return [{"id": i.id, "nome": i.nome, "unidade": i.unidade_medida, "quantidade_atual": i.quantidade_atual, "quantidade_minima": i.quantidade_minima, "custo": i.custo_unitario} for i in insumos]

@app.post("/api/gestao/insumo")
def receber_novo_insumo(insumo: NovoInsumo, db: Session = Depends(get_db)):
    try:
        novo = cadastrar_insumo(db=db, nome=insumo.nome, unidade=insumo.unidade, qtd_inicial=insumo.quantidade, qtd_min=insumo.minimo, custo=insumo.custo)
        return {"status": "sucesso", "insumo_id": novo.id}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500)

@app.delete("/api/gestao/produto/{produto_id}")
def deletar_produto(produto_id: int, db: Session = Depends(get_db)):
    try:
        produto = db.query(ProdutoModel).filter(ProdutoModel.id == produto_id).first()
        if not produto: raise HTTPException(status_code=404)
        db.delete(produto)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500)

# --- ROTAS FINANCEIRAS ---

@app.post("/api/gestao/conta")
def receber_nova_conta(conta: NovaConta, db: Session = Depends(get_db)):
    try:
        fornecedor_id = conta.fornecedor_id
        if not fornecedor_id:
            fornecedor = db.query(FornecedorModel).first()
            if not fornecedor:
                fornecedor = FornecedorModel(nome_fantasia="Diversos", categoria="Geral")
                db.add(fornecedor); db.commit(); db.refresh(fornecedor)
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
    lista = [{"id": c.id, "descricao": c.descricao, "valor": c.valor, "vencimento": c.data_vencimento.strftime("%d/%m/%Y"), "tipo": c.tipo_despesa, "status": c.status} for c in contas]
    return {"total_empresa": total_empresa, "total_casa": total_casa, "contas": lista}

@app.get("/api/gestao/financeiro/lucratividade")
def obter_relatorio_lucratividade(db: Session = Depends(get_db)):
    pedidos = db.query(PedidoModel).all()
    faturamento_total = sum(p.total_pago for p in pedidos if str(p.status).split('.')[-1].upper() not in ["CANCELADO", "RECEBIDO"])
    contas = db.query(ContaPagarModel).all()
    despesas_empresa = sum(c.valor for c in contas if c.tipo_despesa == "Empresa")
    despesas_casa = sum(c.valor for c in contas if c.tipo_despesa == "Casa")
    lucro_operacional = faturamento_total - despesas_empresa
    lucro_liquido_real = lucro_operacional - despesas_casa
    margem_lucro = (lucro_operacional / faturamento_total * 100) if faturamento_total > 0 else 0
    return { "faturamento": faturamento_total, "despesas_empresa": despesas_empresa, "despesas_casa": despesas_casa, "lucro_operacional": lucro_operacional, "lucro_liquido": lucro_liquido_real, "margem_lucro": round(margem_lucro, 2) }

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
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo": tipo_pedido,
        "cliente_nome": cliente.nome if cliente else "Cliente Avulso",
        "cliente_telefone": cliente.telefone if cliente else "",
        "endereco": endereco,
        "itens": itens_formatados,
        "total": pedido.total_pago,
        "forma_pagamento": str(pedido.forma_pagamento).replace('_', ' ').upper()
    }
    
# --- ROTAS DE LOGÍSTICA E KDS ---

@app.get("/api/logistica/pedidos")
def listar_pedidos_logistica(db: Session = Depends(get_db)):
    pedidos = db.query(PedidoModel).order_by(desc(PedidoModel.id)).all()
    prontos, em_rota = [], []
    for p in pedidos:
        status_atual = str(p.status).split('.')[-1].upper()
        tipo_atual = str(getattr(p, 'tipo_pedido', getattr(p, 'tipo', ''))).split('.')[-1].upper()
        if tipo_atual not in ["DELIVERY", "RETIRADA"]: continue
        
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
            "cliente": p.cliente.nome if p.cliente else "Cliente",  
            "status": status_atual,  
            "endereco": endereco_completo,
            "tipo": tipo_atual
        }
        if status_atual == "PRONTO": prontos.append(dados_pedido)
        elif status_atual == "SAIU_PARA_ENTREGA": em_rota.append(dados_pedido)
    return {"prontos": prontos, "em_rota": em_rota}

@app.put("/api/logistica/pedidos/{pedido_id}/despachar")
def despachar_pedido(pedido_id: int, payload: DespachoMotoboy, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido: raise HTTPException(status_code=404)
    pedido.status = "SAIU_PARA_ENTREGA"
    db.commit()
    
    if pedido.cliente:
        notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, pedido.id, "SAIU_PARA_ENTREGA")
        
    return {"status": "sucesso"}

@app.get("/api/kds/pedidos")
def listar_pedidos_cozinha(db: Session = Depends(get_db)):
    pedidos_ativos = db.query(PedidoModel).order_by(PedidoModel.id.asc()).all()
    lista_kds = []
    for pedido in pedidos_ativos:
        status_atual = str(pedido.status).split('.')[-1].upper()
        if status_atual not in ["RECEBIDO", "EM_PREPARO"]: continue
        tipo_atual = str(getattr(pedido, 'tipo_pedido', getattr(pedido, 'tipo', ''))).split('.')[-1].upper()
        itens = []
        for item in getattr(pedido, 'itens', getattr(pedido, 'itens_pedido', [])):
            produto = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
            obs = getattr(item, 'observacao', getattr(item, 'observacoes', ''))
            itens.append({"quantidade": item.quantidade, "nome_produto": produto.nome if produto else "Removido", "observacao": obs})
        lista_kds.append({"id": pedido.id, "tipo": tipo_atual, "status": status_atual, "itens": itens})
    return lista_kds

@app.put("/api/kds/pedidos/{pedido_id}/status")
def mudar_status_pedido(pedido_id: int, payload: AtualizarStatus, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido: raise HTTPException(status_code=404)
    
    novo_status = payload.status.upper()
    pedido.status = novo_status
    db.commit()
    
    if pedido.cliente:
        notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, pedido.id, novo_status)
        
    return {"mensagem": "Status atualizado"}


# --- ROTAS DE CONFIGURAÇÃO E CLIENTES ---

@app.get("/api/gestao/configuracoes")
def ler_configuracoes(db: Session = Depends(get_db)):
    config = db.query(ConfiguracaoLojaModel).first()
    if not config:
        config = ConfiguracaoLojaModel()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

@app.put("/api/gestao/clientes/{cliente_id}/editar")
def editar_cliente(cliente_id: int, dados: dict, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente: raise HTTPException(status_code=404)
    cliente.nome = dados.get("nome", cliente.nome)
    cliente.telefone = dados.get("telefone", cliente.telefone)
    cliente.pontos_fidelidade = int(dados.get("pontos", cliente.pontos_fidelidade))
    cliente.saldo_cashback = float(dados.get("cashback", cliente.saldo_cashback))
    db.commit()
    return {"status": "sucesso"}

@app.delete("/api/gestao/clientes/{cliente_id}")
def deletar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente: raise HTTPException(status_code=404)
    db.delete(cliente)
    db.commit()
    return {"status": "sucesso"}

@app.put("/api/gestao/configuracoes")
def salvar_configuracoes(dados: dict, db: Session = Depends(get_db)):
    config = db.query(ConfiguracaoLojaModel).first()
    config.logo_url = dados.get("logo_url", config.logo_url)
    config.aceita_delivery = dados.get("aceita_delivery", config.aceita_delivery)
    config.aceita_retirada = dados.get("aceita_retirada", config.aceita_retirada)
    config.aceite_automatico = dados.get("aceite_automatico", config.aceite_automatico)
    config.tempo_preparo = dados.get("tempo_preparo", config.tempo_preparo)
    config.formas_pagamento = dados.get("formas_pagamento", config.formas_pagamento)
    db.commit()
    return {"status": "sucesso"}

@app.get("/api/gestao/clientes")
def listar_clientes_painel(db: Session = Depends(get_db)):
    clientes = db.query(ClienteModel).all()
    return [{"id": c.id, "nome": c.nome, "telefone": c.telefone, "bloqueado": getattr(c, 'bloqueado', False), "pontos": getattr(c, 'pontos_fidelidade', 0), "cashback": getattr(c, 'saldo_cashback', 0.0)} for c in clientes]

@app.put("/api/gestao/clientes/{cliente_id}/bloqueio")
def alternar_bloqueio_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not cliente: raise HTTPException(status_code=404)
    cliente.bloqueado = not getattr(cliente, 'bloqueado', False)
    db.commit()
    return {"status": "sucesso"}

@app.get("/api/gestao/relatorios/curva-abc")
def obter_relatorio_curva_abc(db: Session = Depends(get_db)):
    pedidos = db.query(PedidoModel).filter(PedidoModel.status != "CANCELADO").all()
    
    ranking = {}
    
    for pedido in pedidos:
        itens = getattr(pedido, 'itens', getattr(pedido, 'itens_pedido', []))
        for item in itens:
            prod_id = item.produto_id
            qtd = item.quantidade
            
            if prod_id not in ranking:
                produto = db.query(ProdutoModel).filter(ProdutoModel.id == prod_id).first()
                if produto:
                    ranking[prod_id] = {
                        "nome": produto.nome, 
                        "categoria": produto.categoria,
                        "quantidade_vendida": 0, 
                        "faturamento_gerado": 0.0
                    }
            
            if prod_id in ranking:
                produto_preco = db.query(ProdutoModel).filter(ProdutoModel.id == prod_id).first().preco_venda
                ranking[prod_id]["quantidade_vendida"] += qtd
                ranking[prod_id]["faturamento_gerado"] += (qtd * produto_preco)
                
    lista_ranking = list(ranking.values())
    lista_ranking.sort(key=lambda x: x["faturamento_gerado"], reverse=True)
    
    return lista_ranking[:10] 
    
# --- ROTAS VISUAIS (Telas HTML) ---
@app.get("/login", response_class=HTMLResponse)
def abrir_tela_login(): return Path("templates/login.html").read_text(encoding="utf-8") if Path("templates/login.html").exists() else "Erro"

@app.get("/", response_class=HTMLResponse)
def abrir_cardapio(): return Path("templates/cardapio.html").read_text(encoding="utf-8") if Path("templates/cardapio.html").exists() else "Erro"

@app.get("/admin", response_class=HTMLResponse)
def abrir_admin(): return Path("templates/dashboard.html").read_text(encoding="utf-8") if Path("templates/dashboard.html").exists() else "Erro"

@app.get("/gestao", response_class=HTMLResponse)
def abrir_gestao(): return Path("templates/gestao.html").read_text(encoding="utf-8") if Path("templates/gestao.html").exists() else "Erro"

@app.get("/pdv", response_class=HTMLResponse)
def abrir_pdv(): return Path("templates/pdv.html").read_text(encoding="utf-8") if Path("templates/pdv.html").exists() else "Erro"

@app.get("/logistica", response_class=HTMLResponse)
def abrir_logistica(): return Path("templates/logistica.html").read_text(encoding="utf-8") if Path("templates/logistica.html").exists() else "Erro"

@app.get("/kds", response_class=HTMLResponse)
def abrir_kds(): return Path("templates/kds.html").read_text(encoding="utf-8") if Path("templates/kds.html").exists() else "Erro"

app.include_router(router_dashboard)
app.include_router(router_pagamentos)
app.include_router(router_99food)

@app.get("/api/gestao/notificacoes")
def checar_novos_pedidos(db: Session = Depends(get_db)):
    qtd_novos = db.query(PedidoModel).filter(PedidoModel.status == "RECEBIDO").count()
    return {"pendentes": qtd_novos}

@app.put("/api/logistica/pedidos/{pedido_id}/entregar")
def concluir_entrega_final(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido: 
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    
    pedido.status = "ENTREGUE"
    db.commit()
    
    if pedido.cliente:
        notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, pedido.id, "ENTREGUE")
        
    return {"status": "sucesso", "mensagem": "Baixa realizada e cliente notificado!"}
    
if __name__ == "__main__":
    print("🚀 Iniciando Servidor Web do Art's Burguer (Modo Notificações Automatizadas)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
