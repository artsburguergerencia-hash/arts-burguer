from fastapi import FastAPI, Depends, HTTPException, Query, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from datetime import datetime, date
from sqlalchemy import desc, Column, Integer, String, Float, Boolean, text, DateTime
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
    ordem: int = 0  # 🚨 NOVA LINHA AQUI
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
    from datetime import datetime
    from sqlalchemy import func
    hoje = datetime.utcnow().date()
    
    # 🚨 Correção Absoluta: Busca usando data_hora (que existe na sua tabela) 🚨
    try:
        total_hoje = db.query(PedidoModel).filter(func.date(PedidoModel.data_hora) == hoje).count()
        return str(total_hoje + 1).zfill(3)
    except:
        # Se falhar a leitura de data_hora, usa a contagem geral
        total_hoje = db.query(PedidoModel).count()
        return str(total_hoje + 1).zfill(3)

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
        
        # Cria o modelo usando apenas as colunas garantidas
        novo_fornecedor = FornecedorModel(
            nome_fantasia=dados.nome_fantasia, 
            categoria=dados.categoria, 
            contato=dados.contato,
            cnpj=cnpj_limpo
        )
        
        # O pulo do gato: Só salva o telefone duplo se a coluna realmente existir no seu financeiro.py
        if hasattr(novo_fornecedor, 'telefone'):
            novo_fornecedor.telefone = dados.contato
            
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
        # Se falhar, agora ele envia o erro EXATO para a tela do Gestão mostrar no alerta
        raise HTTPException(status_code=500, detail=f"Falha ao salvar no banco: {str(e)}")


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
        # Tratamento rigoroso do CPF para evitar erro de duplicidade com vazio
        cpf_recebido = dados.get("cpf", "").strip()
        cpf_final = cpf_recebido if cpf_recebido != "" else None

        novo_cliente = Cliente(
            nome=dados.get("nome", "Cliente Visitante"),
            telefone=telefone_cliente,
            senha=dados.get("senha", ""),
            cpf=cpf_final,
            data_nascimento=dados.get("data_nascimento", ""),
            cep=dados.get("cep", ""),
            
            # 🚨 CORREÇÃO 1: Amarra o 'logradouro' ao 'endereco'
            endereco=dados.get("endereco", dados.get("logradouro", "")),
            
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
            
            # 🚨 CORREÇÃO 2: Envia os campos desmembrados para o Cache (localStorage)
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
    from fastapi import HTTPException
    import traceback
    
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
            
        itens_carrinho = []
        for i in pedido_web.itens:
            itens_carrinho.append({
                "produto_id": i.produto_id, 
                "quantidade": i.quantidade, 
                "observacao": i.observacao
            })
        
        if getattr(pedido_web, 'endereco_cliente', None) and len(itens_carrinho) > 0:
            obs_atual = itens_carrinho[0].get("observacao", "")
            if obs_atual is None:
                obs_atual = ""
            itens_carrinho[0]["observacao"] = f"Endereço: {pedido_web.endereco_cliente} | {obs_atual}"

        # 1. REGISTRA O PEDIDO NO PDV
        try:
            novo_pedido = registrar_venda_pdv(
                db=db, 
                tipo=TipoPedido.DELIVERY, 
                itens_carrinho=itens_carrinho, 
                cliente_id=cliente.id
            )
        except Exception as e_pdv:
            raise HTTPException(status_code=400, detail=f"Erro ao salvar pedido (PDV): {str(e_pdv)}")

        p_id = getattr(novo_pedido, "id", None)
        if not p_id and type(novo_pedido) is dict:
            p_id = novo_pedido.get("id") or novo_pedido.get("pedido_id")

        novo_pedido_real = db.query(PedidoModel).filter(PedidoModel.id == p_id).first()
        
        if novo_pedido_real:
            # 🚨 BLINDAGEM MÁXIMA DA SENHA DIÁRIA (A causa do problema!) 🚨
            try:
                novo_pedido_real.senha_diaria = gerar_senha_diaria(db)
            except Exception as e_senha:
                print(f"Erro na senha diária: {e_senha}", flush=True)
                # O banco não tem data_pedido, então usamos o ID como Senha!
                novo_pedido_real.senha_diaria = str(novo_pedido_real.id).zfill(3)

            if hasattr(novo_pedido_real, 'origem'):
                novo_pedido_real.origem = "SITE (Online)"
            
            db.commit()

        # 2. BLINDAGEM NO ESTOQUE
        try:
            for item in itens_carrinho:
                processar_baixa_estoque(db, produto_id=item["produto_id"], quantidade_vendida=item["quantidade"])
        except Exception as err_est:
            print(f"Estoque ignorado: {err_est}", flush=True)

        aceite_auto = getattr(config, 'aceite_automatico', False) if config else False

        # 3. VERIFICA A FORMA DE PAGAMENTO E O WHATSAPP
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

        # 4. INTEGRAÇÃO MERCADO PAGO
        if forma_pagamento == "pix":
            if not getattr(pedido_web, 'cpf', None):
                raise HTTPException(status_code=400, detail="CPF é obrigatório para gerar o Pix.")
            
            valor_pagar = getattr(novo_pedido_real, 'total_pago', getattr(novo_pedido_real, 'total', 0))
            
            try:
                resultado_pix = criar_pagamento_pix_mp(novo_pedido_real.id, float(valor_pagar), cliente.nome, pedido_web.cpf)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Erro de conexão no MP: {e}")
            
            if type(resultado_pix) is dict and "qr_code" in resultado_pix:
                return {"status": "checkout_transparente", "copia_e_cola": resultado_pix["qr_code"]}
            else:
                if novo_pedido_real:
                    novo_pedido_real.status = "CANCELADO"
                    db.commit()
                erro_msg = resultado_pix.get("erro", "Recusado pelo MP") if type(resultado_pix) is dict else "Recusado"
                raise HTTPException(status_code=400, detail=f"Mercado Pago recusou: {erro_msg}")
                
        elif forma_pagamento == "credito" or forma_pagamento == "vr":
            if not getattr(pedido_web, 'token_cartao', None) or not getattr(pedido_web, 'cpf', None):
                raise HTTPException(status_code=400, detail="Faltam dados do cartão ou CPF.")
                
            valor_pagar = getattr(novo_pedido_real, 'total_pago', getattr(novo_pedido_real, 'total', 0))
            
            try:
                resposta_pagamento = criar_pagamento_cartao_mp(
                    pedido_id=novo_pedido_real.id, 
                    valor_total=float(valor_pagar), 
                    token_cartao=pedido_web.token_cartao, 
                    email_cliente=f"cliente{cliente.id}@artsburguer.com",
                    payment_method_id=getattr(pedido_web, 'payment_method_id', "master"), 
                    parcelas=getattr(pedido_web, 'parcelas', 1), 
                    cpf_cliente=pedido_web.cpf
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Erro no banco: {e}")
            
            if resposta_pagamento and isinstance(resposta_pagamento, dict) and resposta_pagamento.get("status") in ["approved", "in_process"]:
                if novo_pedido_real:
                    novo_pedido_real.status = "EM_PREPARO" if aceite_auto else "RECEBIDO"
                    db.commit()
                try:
                    notificar_status_pedido(cliente.telefone, cliente.nome, novo_pedido_real.senha_diaria, novo_pedido_real.status)
                except: pass
                return {"status": "sucesso", "mensagem": "Pagamento aprovado!"}
            else:
                if novo_pedido_real:
                    novo_pedido_real.status = "CANCELADO"
                    db.commit()
                raise HTTPException(status_code=400, detail="Pagamento recusado pelo banco.")
                
        return {"status": "entrega", "mensagem": "Pedido confirmado para pagamento na entrega!"}
        
    except HTTPException:
        raise
    except Exception as global_e:
        from fastapi import HTTPException
        print(f"ERRO CRÍTICO: {global_e}", flush=True)
        raise HTTPException(status_code=400, detail=f"Falha no Python: {str(global_e)}")


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
            "permissoes": cargo.permissoes if cargo else "basico", # <--- A MÁGICA ESTÁ AQUI
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
    else:
        # Cria a ficha RH caso o funcionário tenha sido criado de forma avulsa
        novo_rh = InfoRHModel(funcionario_id=func_id, status_admissao="DEMITIDO")
        db.add(novo_rh)
        
    func.senha_hash = "REVOGADO" 
    db.commit()
    
    return {"status": "sucesso", "mensagem": "Acesso revogado com sucesso."}


@app.put("/api/gestao/funcionarios/{func_id}/readmitir")
def readmitir_funcionario(func_id: int, senha_nova: str = Query(...), db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not func: 
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
        
    rh = db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).first()
    if rh:
        rh.status_admissao = "ATIVO"
    else:
        # Cria a ficha RH caso não exista
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
    
    # A MÁGICA ESTÁ AQUI: Se o seu usuário tem permissão total, 
    # o Python força o número 1 para o frontend liberar o acesso ao Gestão!
    id_liberacao = 1 if (cargo and cargo.permissoes == "total") else funcionario.cargo_id
    
    return { 
        "status": "sucesso", 
        "nome": funcionario.nome, 
        "cargo_id": id_liberacao, 
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
            # 🚨 CORREÇÃO: Busca especificamente a pasta "Diversos", e não o primeiro da lista
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
    try:
        # CORREÇÃO 1: Usando .desc() direto na coluna (não precisa importar nada!)
        pedidos = db.query(PedidoModel).order_by(PedidoModel.id.desc()).all()
        prontos, em_rota = [], []
        
        for p in pedidos:
            try:
                status_atual = str(p.status).split('.')[-1].upper()
                tipo_atual = str(getattr(p, 'tipo_pedido', getattr(p, 'tipo', 'DELIVERY'))).split('.')[-1].upper()
                
                if tipo_atual not in ["DELIVERY", "RETIRADA"]: 
                    continue
                
                endereco_completo = 'Retirada no Balcão' if tipo_atual == 'RETIRADA' else 'Endereço não informado'
                
                # Sua lógica genial mantida e blindada!
                for item in getattr(p, 'itens', getattr(p, 'itens_pedido', [])):
                    obs = getattr(item, 'observacao', getattr(item, 'observacoes', ''))
                    if obs and "Endereço: " in obs:
                        partes = obs.split(" | ")
                        for parte in partes:
                            if "Endereço: " in parte:
                                endereco_completo = parte.replace("Endereço: ", "").strip()
                                break
                        break
                
                # CORREÇÃO 2: Buscando o telefone com segurança
                telefone_seguro = "Não informado"
                if hasattr(p, 'cliente') and p.cliente:
                    telefone_seguro = p.cliente.telefone
                    
                dados_pedido = { 
                    "id": p.id,  
                    "senha_diaria": getattr(p, 'senha_diaria', p.id),
                    "origem": getattr(p, 'origem', 'SITE'),
                    "cliente": p.cliente.nome if p.cliente else "Cliente", 
                    "telefone": getattr(p, 'telefone_cliente', telefone_seguro), 
                    "status": status_atual,  
                    "endereco": endereco_completo,
                    "tipo": tipo_atual
                }
                
                if status_atual == "PRONTO": 
                    prontos.append(dados_pedido)
                elif status_atual == "SAIU_PARA_ENTREGA": 
                    em_rota.append(dados_pedido)
            except Exception as e_item:
                print(f"Erro ao ler pedido na logística: {e_item}", flush=True)
                continue # Pula o pedido com defeito e mostra o resto!
                
        return {"prontos": prontos, "em_rota": em_rota}
    except Exception as e:
        print(f"Erro geral da Rota Logística: {e}", flush=True)
        return {"prontos": [], "em_rota": []} # Devolve vazio para não travar a tela!


@app.put("/api/logistica/pedidos/{pedido_id}/despachar")
def despachar_pedido(pedido_id: int, payload: dict, db: Session = Depends(get_db)): # CORREÇÃO 3: dict genérico
    from fastapi import HTTPException
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    
    if not pedido: 
        raise HTTPException(status_code=404)
        
    pedido.status = "SAIU_PARA_ENTREGA"
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', pedido.id)
        # BLINDAGEM DO WHATSAPP AQUI!
        try:
            notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, "SAIU_PARA_ENTREGA")
        except:
            pass
        
    return {"status": "sucesso"}


@app.put("/api/logistica/pedidos/{pedido_id}/entregar")
def concluir_entrega_final(pedido_id: int, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    
    if not pedido: 
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    
    pedido.status = "ENTREGUE"
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', pedido.id)
        # BLINDAGEM DO WHATSAPP AQUI TAMBÉM!
        try:
            notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, "ENTREGUE")
        except:
            pass
        
    return {"status": "sucesso", "mensagem": "Baixa realizada e cliente notificado!"}


@app.get("/api/kds/pedidos")
def listar_pedidos_cozinha(db: Session = Depends(get_db)):
    pedidos_ativos = db.query(PedidoModel).order_by(PedidoModel.id.asc()).all()
    
    # Criamos as duas caixas que o HTML está esperando!
    recebidos = []
    preparando = []
    
    for pedido in pedidos_ativos:
        status_atual = str(pedido.status).split('.')[-1].upper()
        # Se não estiver nesses 3, ignora
        if status_atual not in ["RECEBIDO", "EM_PREPARO", "PREPARANDO"]: 
            continue
            
        tipo_atual = str(getattr(pedido, 'tipo_pedido', getattr(pedido, 'tipo', ''))).split('.')[-1].upper()
        
        itens = []
        for item in getattr(pedido, 'itens', getattr(pedido, 'itens_pedido', [])):
            produto = db.query(ProdutoModel).filter(ProdutoModel.id == item.produto_id).first()
            obs = getattr(item, 'observacao', getattr(item, 'observacoes', ''))
            itens.append({
                "quantidade": item.quantidade, 
                "nome": produto.nome if produto else "Item Editado", # Ajustado para bater com o HTML!
                "observacao": obs
            })
            
        obj_pedido = {
            "id": pedido.id, 
            "senha_diaria": getattr(pedido, 'senha_diaria', pedido.id),
            "origem": getattr(pedido, 'origem', 'SITE'),
            "tipo": tipo_atual, 
            "status": status_atual, 
            "itens": itens
        }

        # Separa nas caixas certas
        if status_atual == "RECEBIDO":
            recebidos.append(obj_pedido)
        else:
            preparando.append(obj_pedido)
            
    # Manda as duas caixas com os nomes que o kds.html espera
    return {"recebidos": recebidos, "preparando": preparando}


from fastapi import BackgroundTasks # Coloque isso no começo do arquivo se não tiver

@app.put("/api/kds/pedidos/{pedido_id}/status")
def mudar_status_pedido(pedido_id: int, payload: AtualizarStatus, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido: 
        raise HTTPException(status_code=404)
    
    novo_status = payload.status.upper()
    pedido.status = novo_status
    db.commit()
    
    if pedido.cliente:
        senha_enviar = getattr(pedido, 'senha_diaria', pedido.id)
        # 🚨 Dispara o WhatsApp em Segundo Plano (O KDS atualiza em 0.1s agora!) 🚨
        try:
            background_tasks.add_task(notificar_status_pedido, pedido.cliente.telefone, pedido.cliente.nome, senha_enviar, novo_status)
        except: pass
        
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

# ==========================================
# ROTA DE GPS DO MOTOBOY (ANTI-TRAVAMENTO)
# ==========================================
@app.get("/api/logistica/gps/{pedido_id}")
def buscar_posicao_motoboy(pedido_id: int, db: Session = Depends(get_db)):
    """ A tela do cliente (mapa) pede a posição da moto pra cá a cada 5 segundos """
    # Coordenada padrão (Fazenda Rio Grande) para o mapa nunca travar
    coord_padrao = {"lat": -25.6600, "lng": -49.3100}
    
    try:
        pedido = db.query(PedidoModel).filter(
            (PedidoModel.id == pedido_id) | (PedidoModel.senha_diaria == pedido_id)
        ).order_by(desc(PedidoModel.id)).first()
        
        if not pedido:
            # Força o mapa a abrir mesmo se o pedido for inválido
            return {"status": "online", "posicao": coord_padrao}
            
        real_id = pedido.id

        posicao = POSICOES_MOTOBOYS_AO_VIVO.get(real_id)
        if not posicao:
            posicao = POSICOES_MOTOBOYS_AO_VIVO.get(pedido_id)

        if not posicao:
            lat_db = getattr(pedido, 'entregador_lat', None)
            lng_db = getattr(pedido, 'entregador_lng', None)
            if lat_db and lng_db and float(lat_db) != 0.0:
                posicao = {"lat": float(lat_db), "lng": float(lng_db)}

        if posicao:
            return {
                "status": "online", 
                "posicao": {"lat": float(posicao["lat"]), "lng": float(posicao["lng"])}
            }
        else:
            # FORÇA O MAPA A ABRIR SEMPRE (Acaba com o "Conectando...")
            return {"status": "online", "posicao": coord_padrao}
            
    except Exception as e:
        print(f"Erro ao processar GPS: {e}")
        return {"status": "online", "posicao": coord_padrao}

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
                "data_nascimento": c.get("data_nascimento", ""), # <--- Não esqueça dessa vírgula aqui!
                "foto": c.get("foto", "") # <--- NOVA LINHA DA FOTO AQUI!
            })
            
        return lista_blindada
    except Exception as e:
        print("Erro Crítico no GET Clientes:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

<!DOCTYPE html>
<html lang="pt-BR" class="scroll-smooth">
# 1. Atualizar Produto (Cardápio)
@app.put("/api/gestao/produto/{produto_id}")
def atualizar_produto(produto_id: int, dados: dict, db: Session = Depends(get_db)):
    from database import ProdutoModel, FichaTecnicaModel
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
    
    # 🚨 NOVA LINHA AQUI: Permite alterar a posição do lanche!
    if 'ordem' in dados: produto.ordem = int(dados['ordem'])
    
    # O PULO DO GATO: Atualiza a Ficha Técnica
    if 'fichas' in dados:
        # 1. Apaga as fichas antigas para não duplicar
        db.query(FichaTecnicaModel).filter(FichaTecnicaModel.produto_id == produto_id).delete()
        # 2. Insere a nova lista de ingredientes que veio da tela
        for f in dados['fichas']:
            db.add(FichaTecnicaModel(
                produto_id=produto_id, 
                insumo_id=f["insumo_id"], 
                quantidade_necessaria=f["quantidade"]
            ))
        
    db.commit()
    return {"status": "sucesso", "mensagem": "Produto e Ficha atualizados!"}
<body class="pb-24 overflow-x-hidden selection:bg-brand-500 selection:text-white">

    <!-- CABEÇALHO DA LOJA -->
    <header class="glass fixed top-0 w-full z-30 transition-all duration-300">
        <div class="max-w-2xl mx-auto px-4 py-3 flex justify-between items-center">
            
            <!-- IDENTIFICAÇÃO DA LOJA (CLICÁVEL PARA ABRIR MODAL) -->
            <div class="flex items-center space-x-3 truncate pr-2 cursor-pointer active:scale-95 transition-transform" onclick="abrirModalInfoLoja()">
                <div id="header-logo-container" class="w-10 h-10 bg-brand-500 rounded-full flex items-center justify-center text-white font-black text-xl shadow-lg shadow-brand-500/40 border-2 border-slate-800 dark:border-slate-800 overflow-hidden shrink-0 transition-colors duration-300">
                    <span id="header-logo-letra">A</span>
                    <img id="header-logo-img" src="" class="w-full h-full object-cover hidden">
                </div>
                <div class="truncate">
                    <h1 id="nome-loja-header" class="font-black text-lg tracking-tight text-slate-800 dark:text-white leading-none truncate">Art's Burguer <i class="ph-bold ph-caret-down text-sm ml-0.5 text-slate-400"></i></h1>
                    <p id="status-loja-header" class="text-[10px] font-bold uppercase tracking-widest mt-1 flex items-center text-slate-400">
                        <span class="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5 shrink-0" id="status-dot"></span> <span id="status-text">Carregando...</span>
                    </p>
                    <p id="info-loja-header" class="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mt-0.5 hidden truncate"></p>
                </div>
            </div>
            
            <div id="area-auth" class="flex items-center space-x-1.5 sm:space-x-2 shrink-0">
                <!-- BOTÃO INSTALAR SEMPRE VISÍVEL -->
                <button id="btn-instalar-app" onclick="instalarApp()" class="text-xs sm:text-sm bg-brand-500 hover:bg-brand-600 p-2 sm:px-4 sm:py-2 rounded-full font-black transition-all flex items-center text-white shadow-lg shadow-brand-500/40 animate-pulse" title="Instalar App">
                    <i class="ph-bold ph-download-simple sm:mr-2 text-lg"></i> <span class="hidden sm:inline">Instalar</span>
                </button>
                
                <button onclick="toggleTheme()" class="text-sm bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 p-2 sm:px-3 sm:py-2 rounded-full font-bold transition-colors flex items-center text-slate-600 dark:text-brand-400 border border-slate-300 dark:border-white/5 shadow-sm">
                    <i id="theme-icon" class="ph-bold ph-moon text-lg"></i>
                </button>

                <button onclick="abrirModalRastreio()" class="text-sm bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 p-2 sm:px-3 sm:py-2 rounded-full font-bold transition-colors flex items-center text-slate-600 dark:text-brand-400 border border-slate-300 dark:border-white/5" title="Rastrear Pedido">
                    <i class="ph-bold ph-crosshair text-lg"></i>
                </button>
                
                <button onclick="abrirModalAuth()" class="text-xs sm:text-sm bg-brand-50 dark:bg-white/10 hover:bg-brand-100 dark:hover:bg-white/20 px-3 py-2 sm:px-4 sm:py-2 rounded-full font-bold transition-colors flex items-center text-brand-600 dark:text-white border border-brand-200 dark:border-white/5 shrink-0">
                    <i class="ph-bold ph-user mr-1.5"></i> Entrar
                </button>
            </div>
        </div>

        <div id="barra-fidelidade" class="hidden bg-white/90 dark:bg-slate-800/80 px-4 py-2 text-xs border-t border-slate-200 dark:border-slate-700/50 backdrop-blur-md">
            <div class="max-w-2xl mx-auto flex justify-between items-center">
                <span class="text-amber-500 dark:text-amber-400 font-black uppercase tracking-widest flex items-center"><i class="ph-fill ph-star mr-1 text-lg"></i> <span id="fid-pontos">0</span> pts</span>
                <span class="text-emerald-600 dark:text-emerald-400 font-black uppercase tracking-widest flex items-center"><i class="ph-fill ph-money mr-1 text-lg"></i> Cashback: R$ <span id="fid-cashback">0,00</span></span>
            </div>
        </div>

        <nav class="max-w-2xl mx-auto px-4 py-3 overflow-x-auto no-scrollbar flex space-x-3 border-t border-slate-200 dark:border-slate-800" id="nav-categorias">
            <div class="h-8 flex items-center text-slate-400 text-xs font-bold animate-pulse">Carregando cardápio...</div>
        </nav>
    </header>

    <!-- BANNER DE DESTAQUE -->
    <div class="mt-44 md:mt-48 max-w-2xl mx-auto px-4 mb-6">
        <div class="bg-gradient-to-r from-brand-600 to-brand-500 rounded-2xl p-6 relative overflow-hidden shadow-xl shadow-brand-500/20">
            <i class="ph-fill ph-hamburger absolute -right-4 -bottom-4 text-[120px] text-white opacity-20 transform -rotate-12"></i>
            <div class="relative z-10">
                <span class="bg-white/20 text-white px-2 py-1 rounded text-[9px] font-black uppercase tracking-widest backdrop-blur-sm">Novidade</span>
                <h2 class="text-2xl font-black text-white mt-2 mb-1 leading-tight tracking-tight">O Melhor Burger<br>da Cidade.</h2>
                <p class="text-white/80 text-xs font-medium">Faça seu pedido agora sem filas.</p>
            </div>
        </div>
    </div>

    <!-- GRADE DE PRODUTOS -->
    <main class="max-w-2xl mx-auto px-4 space-y-8" id="lista-produtos"></main>

    <!-- BOTÃO FLUTUANTE DE CARRINHO -->
    <div id="barra-carrinho" class="fixed bottom-6 left-0 w-full px-4 md:left-1/2 md:-translate-x-1/2 md:max-w-md z-30 translate-y-40 transition-transform duration-500 ease-out pointer-events-none">
        <button onclick="abrirCarrinho()" class="w-full bg-brand-500 hover:bg-brand-600 text-white p-4 rounded-2xl shadow-[0_15px_40px_rgba(255,71,87,0.5)] flex items-center justify-between active:scale-95 transition-all border border-brand-400 pointer-events-auto">
            <div class="flex items-center space-x-3">
                <div class="bg-white text-brand-500 w-9 h-9 rounded-xl flex items-center justify-center font-black text-sm shadow-inner" id="carrinho-qtd">0</div>
                <span class="font-black text-sm uppercase tracking-widest">Ver Sacola</span>
            </div>
            <span class="font-black text-xl tracking-tighter" id="carrinho-total-flutuante">R$ 0,00</span>
        </button>
    </div>

    <!-- MODAL DE INFORMAÇÕES DA LOJA -->
    <div id="modal-info-loja" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] hidden items-center justify-center p-4" onclick="document.getElementById('modal-info-loja').classList.replace('flex','hidden')">
        <div class="bg-white dark:bg-slate-900 w-full max-w-sm rounded-[2rem] p-8 shadow-2xl relative text-center" onclick="event.stopPropagation()">
            <button onclick="document.getElementById('modal-info-loja').classList.replace('flex','hidden')" class="absolute top-4 right-4 text-slate-400 hover:text-brand-500"><i class="ph-bold ph-x text-xl"></i></button>
            
            <!-- LOGO INJETADA AQUI -->
            <div class="w-16 h-16 bg-brand-50 dark:bg-brand-500/10 text-brand-500 rounded-full flex items-center justify-center mx-auto mb-4 border border-brand-100 dark:border-brand-500/20 overflow-hidden" id="info-modal-logo-container">
                <i class="ph-fill ph-storefront text-3xl" id="info-modal-icon"></i>
                <img id="info-modal-img" src="" class="w-full h-full object-cover hidden">
            </div>

            <h2 class="text-2xl font-black text-slate-800 dark:text-white mb-1" id="info-modal-nome">Carregando...</h2>
            <p class="text-[10px] font-bold uppercase tracking-widest text-emerald-500 dark:text-emerald-400 mb-6" id="info-modal-status-text">Calculando status...</p>
            
            <div class="space-y-4 text-left border-t border-slate-200 dark:border-slate-800 pt-6">
                <div class="flex items-start text-slate-600 dark:text-slate-300">
                    <div class="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mr-4 shrink-0"><i class="ph-bold ph-clock text-xl"></i></div>
                    <div>
                        <p class="text-[9px] font-black uppercase tracking-widest text-slate-400">Horário de Funcionamento</p>
                        <p class="text-sm font-medium leading-relaxed" id="info-modal-horario">Não informado</p>
                    </div>
                </div>
                <div class="flex items-center text-slate-600 dark:text-slate-300">
                    <div class="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mr-4 shrink-0"><i class="ph-bold ph-whatsapp-logo text-xl"></i></div>
                    <div>
                        <p class="text-[9px] font-black uppercase tracking-widest text-slate-400">Contato / WhatsApp</p>
                        <p class="text-sm font-medium" id="info-modal-tel">Não informado</p>
                    </div>
                </div>
                <div class="flex items-center text-slate-600 dark:text-slate-300">
                    <div class="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mr-4 shrink-0"><i class="ph-bold ph-map-pin text-xl"></i></div>
                    <div>
                        <p class="text-[9px] font-black uppercase tracking-widest text-slate-400">Localização</p>
                        <p class="text-sm font-medium line-clamp-2" id="info-modal-end">Não informado</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL ZOOM IMAGEM -->
    <div id="modal-zoom" class="fixed inset-0 bg-black/95 z-[100] hidden items-center justify-center p-4 backdrop-blur-md cursor-pointer" onclick="fecharZoom()">
        <button class="absolute top-6 right-6 text-white bg-white/10 w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-sm hover:bg-white/20 transition-colors"><i class="ph-bold ph-x"></i></button>
        <img id="img-zoom" src="" class="max-w-full max-h-[85vh] object-contain rounded-2xl shadow-2xl transform transition-transform duration-300 scale-95">
    </div>

    <!-- MODAL DO PRODUTO -->
    <div id="modal-produto" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex-col justify-end">
        <div class="bg-white dark:bg-slate-900 w-full max-w-2xl mx-auto rounded-t-3xl h-[85vh] flex flex-col relative modal-enter">
            <button onclick="fecharModalProduto()" class="absolute right-4 top-4 w-8 h-8 bg-white/50 dark:bg-slate-800 text-slate-800 dark:text-slate-400 rounded-full flex items-center justify-center z-10 hover:text-brand-500 dark:hover:text-white transition-colors border border-slate-200 dark:border-transparent"><i class="ph-bold ph-x"></i></button>
            <div id="modal-img-container" class="h-48 shrink-0 bg-slate-100 dark:bg-slate-800 relative w-full overflow-hidden rounded-t-3xl cursor-pointer" title="Clique para ampliar"></div>
            
            <div class="flex-1 overflow-y-auto p-5 no-scrollbar pb-32">
                <h2 id="modal-prod-nome" class="text-2xl font-black text-slate-800 dark:text-white tracking-tight mb-1">Nome</h2>
                <p id="modal-prod-desc" class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-4">Descrição</p>
                <div class="inline-block bg-brand-50 dark:bg-brand-500/10 border border-brand-200 dark:border-brand-500/20 text-brand-600 dark:text-brand-400 px-3 py-1.5 rounded-lg font-black text-lg mb-6">R$ <span id="modal-prod-preco">0,00</span></div>

                <div id="area-complementos" class="space-y-6"></div>

                <div class="mt-6">
                    <label class="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-2">Observações (Opcional)</label>
                    <textarea id="modal-prod-obs" rows="2" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 text-sm text-slate-800 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:border-brand-500 transition-colors" placeholder="Ex: Tirar cebola..."></textarea>
                </div>
            </div>

            <div class="absolute bottom-0 w-full bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 p-4">
                <button onclick="confirmarAdicaoProduto()" class="w-full bg-brand-500 text-white font-black py-4 rounded-xl shadow-[0_10px_30px_rgba(255,71,87,0.3)] flex justify-between px-6 active:scale-95 transition-transform">
                    <span class="uppercase tracking-widest text-xs mt-0.5">Adicionar à Sacola</span>
                    <span>R$ <span id="modal-prod-total-btn">0,00</span></span>
                </button>
            </div>
        </div>
    </div>

    <!-- MODAL DE RASTREIO ÚNICO E LIMPO -->
    <div id="modal-rastreio" class="fixed inset-0 bg-slate-900/90 z-[90] hidden items-center justify-center p-4 backdrop-blur-md">
        <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 w-full max-w-md rounded-[2rem] p-8 shadow-2xl relative text-center">
            <button onclick="document.getElementById('modal-rastreio').classList.replace('flex','hidden')" class="absolute top-4 right-4 text-slate-400 hover:text-brand-500"><i class="ph-bold ph-x text-xl"></i></button>
            <div class="w-16 h-16 bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 text-blue-600 dark:text-blue-500 rounded-full flex items-center justify-center mx-auto mb-4"><i class="ph-fill ph-crosshair text-4xl"></i></div>
            <h2 class="text-2xl font-black text-slate-800 dark:text-white tracking-tight mb-6">Rastrear Pedido</h2>

            <div class="flex space-x-2 mb-6">
                <input type="text" id="input-rastreio" placeholder="Número ou Senha" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-white rounded-xl text-center font-black outline-none focus:blue-500 tracking-widest">
                <button onclick="buscarRastreio()" id="btn-rastreio" class="bg-blue-600 text-white px-5 rounded-xl font-black hover:bg-blue-500 transition-colors shadow-sm"><i class="ph-bold ph-magnifying-glass text-lg"></i></button>
            </div>

            <!-- RESULTADO DETALHADO ETAPA POR ETAPA -->
            <div id="resultado-rastreio" class="hidden bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 text-left relative overflow-hidden">
                <div class="flex justify-between items-center mb-6 border-b border-slate-200 dark:border-slate-800 pb-3">
                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 dark:text-slate-400">Comanda / Pedido</span>
                    <span class="text-2xl font-black text-slate-800 dark:text-white tracking-tighter">#<span id="rastreio-senha">000</span></span>
                </div>

                <!-- LINHA DO TEMPO DAS ETAPAS -->
                <div class="space-y-4 mb-6 relative before:absolute before:top-2 before:bottom-2 before:left-4 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-700">
                    <div class="flex items-center relative z-10" id="step-recebido">
                        <div class="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-500 flex items-center justify-center font-black text-xs shrink-0 transition-colors mr-3 step-icon"><i class="ph-bold ph-check"></i></div>
                        <div>
                            <p class="text-xs font-black text-slate-800 dark:text-white uppercase tracking-wider">1. Pedido Recebido</p>
                            <p class="text-[10px] text-slate-400">Aguardando confirmação</p>
                        </div>
                    </div>
                    <div class="flex items-center relative z-10" id="step-preparo">
                        <div class="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-500 flex items-center justify-center font-black text-xs shrink-0 transition-colors mr-3 step-icon"><i class="ph-bold ph-cooking-pot"></i></div>
                        <div>
                            <p class="text-xs font-black text-slate-800 dark:text-white uppercase tracking-wider">2. Em Preparo</p>
                            <p class="text-[10px] text-slate-400">Seu pedido está sendo montado</p>
                        </div>
                    </div>
                    <div class="flex items-center relative z-10" id="step-pronto">
                        <div class="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-500 flex items-center justify-center font-black text-xs shrink-0 transition-colors mr-3 step-icon"><i class="ph-bold ph-package"></i></div>
                        <div>
                            <p class="text-xs font-black text-slate-800 dark:text-white uppercase tracking-wider">3. Pronto / Despacho</p>
                            <p class="text-[10px] text-slate-400">Separando para entrega</p>
                        </div>
                    </div>
                    <div class="flex items-center relative z-10" id="step-entrega">
                        <div class="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-500 flex items-center justify-center font-black text-xs shrink-0 transition-colors mr-3 step-icon"><i class="ph-bold ph-moped"></i></div>
                        <div>
                            <p class="text-xs font-black text-slate-800 dark:text-white uppercase tracking-wider">4. Saiu para Entrega</p>
                            <p class="text-[10px] text-slate-400">A caminho do seu endereço</p>
                        </div>
                    </div>
                </div>

                <!-- Botão do Mapa GPS -->
                <div id="link-mapa-rastreio" class="hidden mt-4 pt-4 border-t border-slate-200 dark:border-slate-800"></div>
            </div>
        </div>
    </div>

    <!-- MODAL DE EDIÇÃO DE DADOS DO CLIENTE -->
    <div id="modal-editar-perfil" class="fixed inset-0 bg-slate-900/90 z-[100] hidden items-center justify-center p-4 backdrop-blur-md">
        <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 w-full max-w-md rounded-[2rem] p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto no-scrollbar">
            <button onclick="fecharModalEditarPerfil()" class="absolute top-4 right-4 text-slate-400 hover:text-brand-500"><i class="ph-bold ph-x text-xl"></i></button>
            <h2 class="text-xl font-black text-slate-800 dark:text-white mb-6 flex items-center"><i class="ph-fill ph-user-circle-gear text-brand-500 mr-2 text-2xl"></i> Meus Dados</h2>
            
            <form onsubmit="salvarEdicaoPerfil(event)" class="space-y-4">
                <div class="flex flex-col items-center justify-center mb-4">
                    <div class="relative w-24 h-24 rounded-full bg-brand-500 text-white flex items-center justify-center text-4xl font-black shadow-lg shadow-brand-500/30 overflow-hidden border-4 border-slate-50 dark:border-slate-700">
                        <img id="edit-perf-foto-preview" src="" class="w-full h-full object-cover hidden">
                        <span id="edit-perf-iniciais">AL</span>
                        <input type="file" accept="image/*" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer" onchange="lerFotoCliente(event)" title="Escolher Foto">
                    </div>
                    <p class="text-[10px] text-slate-400 dark:text-slate-500 mt-3 font-black uppercase tracking-widest pointer-events-none">Alterar Foto</p>
                    <input type="hidden" id="edit-perf-foto-base64">
                </div>

                <input type="text" id="edit-perf-nome" placeholder="Nome Completo" required class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-600 rounded-xl text-sm font-bold outline-none focus:border-brand-500">
                <input type="tel" id="edit-perf-tel" placeholder="WhatsApp (Apenas números)" required class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-600 rounded-xl text-sm font-bold outline-none focus:border-brand-500">
                <input type="password" id="edit-perf-senha" placeholder="Nova Senha (Opcional)" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-600 rounded-xl text-sm font-bold outline-none focus:border-brand-500">

                <div class="flex space-x-3 pt-2">
                    <input type="text" id="edit-perf-cep" placeholder="CEP" onblur="buscarCep(this.value, 'edit')" class="w-1/3 px-4 py-3 bg-slate-50 dark:bg-slate-900 text-brand-600 dark:text-brand-400 border border-slate-200 dark:border-slate-600 rounded-xl text-sm font-bold outline-none focus:border-brand-500 text-center">
                    <input type="text" id="edit-perf-end" placeholder="Rua e Bairro" required class="flex-1 px-4 py-3 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-600 rounded-xl text-sm font-bold outline-none focus:border-brand-500">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <input type="text" id="edit-perf-num" placeholder="Número" required class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-600 rounded-xl text-sm font-bold outline-none focus:border-brand-500">
                    <input type="text" id="edit-perf-comp" placeholder="Complemento" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-600 rounded-xl text-sm font-bold outline-none focus:border-brand-500">
                </div>
                <button type="submit" id="btn-salvar-perfil" class="w-full bg-brand-500 hover:bg-brand-600 text-white font-black py-4 rounded-xl transition-transform active:scale-95 uppercase tracking-widest text-sm mt-4 shadow-lg shadow-brand-500/30">Atualizar Perfil</button>
            </form>
        </div>
    </div>

    <!-- MODAL PERFIL VIP -->
    <div id="modal-perfil" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-[95] hidden flex-col justify-end">
        <div class="bg-white dark:bg-slate-900 w-full max-w-md mx-auto rounded-t-3xl h-[85vh] flex flex-col relative modal-enter border-t border-slate-200 dark:border-slate-800">
            <button onclick="document.getElementById('modal-perfil').classList.replace('flex','hidden')" class="absolute top-4 right-4 text-slate-400 hover:text-brand-500"><i class="ph-bold ph-x text-xl"></i></button>
            <div class="p-6 border-b border-slate-200 dark:border-slate-800">
                <div class="flex items-center justify-between mb-6">
                    <div class="flex items-center">
                        <div class="w-16 h-16 rounded-full border-2 border-brand-500 mr-4 shadow-lg shadow-brand-500/20 overflow-hidden bg-brand-500 text-white flex items-center justify-center font-black text-2xl">
                            <span id="vip-iniciais">AL</span>
                            <img id="vip-foto" src="" class="w-full h-full object-cover hidden">
                        </div>
                        <div>
                            <h2 id="vip-nome" class="text-xl font-black text-slate-800 dark:text-white tracking-tight">Nome</h2>
                            <p id="vip-tel" class="text-sm text-slate-500 dark:text-slate-400">Telefone</p>
                        </div>
                    </div>
                    <button onclick="carregarModalPerfil()" class="bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-brand-500 dark:text-brand-400 p-3 rounded-xl border border-slate-200 dark:border-slate-700 transition-colors shadow-inner" title="Editar Meus Dados">
                        <i class="ph-bold ph-pencil-simple text-xl"></i>
                    </button>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-slate-50 dark:bg-slate-800 rounded-2xl p-4 border border-slate-200 dark:border-slate-700"><p class="text-[10px] text-amber-500 dark:text-amber-400 font-bold uppercase tracking-widest mb-1"><i class="ph-fill ph-star text-base"></i> Pontos</p><p id="vip-pontos" class="text-3xl font-black text-slate-800 dark:text-white">0</p></div>
                    <div class="bg-slate-50 dark:bg-slate-800 rounded-2xl p-4 border border-slate-200 dark:border-slate-700"><p class="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold uppercase tracking-widest mb-1"><i class="ph-fill ph-money text-base"></i> Cashback</p><p id="vip-cashback" class="text-3xl font-black text-slate-800 dark:text-white">R$ 0,00</p></div>
                </div>
            </div>
            <div class="flex-1 overflow-y-auto p-6 bg-slate-50 dark:bg-slate-900 no-scrollbar">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4 flex items-center"><i class="ph-bold ph-clock-counter-clockwise mr-2 text-lg"></i> Últimos Pedidos</h3>
                <div id="lista-historico" class="space-y-4"></div>
            </div>
            <div class="p-6 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 shrink-0">
                <button onclick="fazerLogout()" class="w-full py-4 text-red-500 dark:text-red-400 font-black uppercase tracking-widest text-xs bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl hover:bg-red-100 dark:hover:bg-red-500/20 transition-colors active:scale-95">
                    <i class="ph-bold ph-sign-out mr-2 text-lg"></i> Sair da conta
                </button>
            </div>
        </div>
    </div>

    <!-- MODAL LOGIN / CADASTRO -->
    <div id="modal-auth" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden items-center justify-center p-4">
        <div class="bg-white dark:bg-slate-900 w-full max-w-md rounded-3xl p-6 shadow-2xl relative modal-enter border border-slate-200 dark:border-slate-800 transition-colors">
            <button onclick="fecharModalAuth()" class="absolute top-4 right-4 text-slate-400 hover:text-brand-500"><i class="ph-bold ph-x text-xl"></i></button>
            
            <div class="flex border-b border-slate-200 dark:border-slate-800 mb-6 mt-2">
                <button onclick="alternarAbaAuth('login')" id="aba-login" class="flex-1 pb-3 text-brand-500 font-black tracking-widest uppercase text-xs border-b-2 border-brand-500 transition-colors">Entrar</button>
                <button onclick="alternarAbaAuth('cadastro')" id="aba-cadastro" class="flex-1 pb-3 text-slate-500 font-bold tracking-widest uppercase text-xs border-b-2 border-transparent transition-colors">Criar Conta</button>
            </div>

            <form id="form-login" onsubmit="fazerLogin(event)" class="space-y-4">
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-1.5">Telefone</label>
                    <input type="tel" id="log-tel" placeholder="(00) 00000-0000" required class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3.5 text-sm text-slate-800 dark:text-white font-bold outline-none focus:border-brand-500 transition-colors">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-1.5">Senha</label>
                    <input type="password" id="log-senha" placeholder="••••••••" required class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3.5 text-sm text-slate-800 dark:text-white font-bold outline-none focus:border-brand-500 transition-colors">
                </div>
                <button type="submit" class="w-full bg-brand-500 text-white font-black uppercase tracking-widest text-xs py-4 rounded-xl shadow-lg active:scale-95 transition-transform mt-2">Acessar Conta</button>
            </form>

            <form id="form-cadastro" onsubmit="fazerCadastro(event)" class="space-y-4 hidden h-[60vh] overflow-y-auto no-scrollbar px-1 pb-4">
                <input type="text" id="cad-nome" placeholder="Nome Completo" required class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                <input type="tel" id="cad-tel" placeholder="WhatsApp (Apenas números)" required class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                <input type="password" id="cad-senha" placeholder="Crie uma Senha" required class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                <div class="grid grid-cols-2 gap-3">
                    <input type="text" id="cad-cpf" placeholder="CPF (Opcional)" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                    <input type="text" id="cad-nasc" placeholder="Nasc (DD/MM)" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                </div>
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest pt-2">Endereço de Entrega</h3>
                <input type="text" id="cad-cep" placeholder="CEP (Auto-busca)" onblur="buscarCep(this.value, 'reg')" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-brand-600 dark:text-brand-400 font-bold border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                <div class="grid grid-cols-3 gap-3">
                    <input type="text" id="cad-rua" placeholder="Rua" class="col-span-2 w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                    <input type="text" id="cad-num" placeholder="Nº" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                </div>
                <input type="text" id="cad-bairro" placeholder="Bairro" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                <input type="text" id="cad-comp" placeholder="Complemento (Ex: Casa 2)" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:border-brand-500 text-sm">
                
                <button type="submit" class="w-full bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-black uppercase tracking-widest text-xs py-4 rounded-xl shadow-lg active:scale-95 transition-transform mt-4">Finalizar Cadastro</button>
            </form>
        </div>
    </div>

    <!-- MODAL DO CARRINHO FINAL (CHECKOUT UNIFICADO) -->
    <div id="modal-carrinho" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-40 hidden flex-col justify-end">
        <div class="bg-white dark:bg-slate-900 w-full max-w-2xl mx-auto rounded-t-3xl h-[90vh] flex flex-col relative modal-enter border-t border-slate-200 dark:border-slate-800">
            <div class="flex justify-between items-center p-5 border-b border-slate-200 dark:border-slate-800 shrink-0">
                <h2 class="text-xl font-black text-slate-800 dark:text-white"><i class="ph-fill ph-shopping-bag text-brand-500 mr-2"></i> Sua Sacola</h2>
                <button onclick="fecharCarrinho()" class="bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 p-2 rounded-full hover:text-brand-500 dark:hover:text-white transition-colors"><i class="ph-bold ph-x"></i></button>
            </div>
            
            <div class="flex-1 overflow-y-auto p-5 no-scrollbar pb-32">
                <div id="lista-carrinho-modal" class="space-y-4 mb-6"></div>
                
                <div class="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4 rounded-2xl mb-4 flex items-center space-x-2">
                    <input type="text" id="input-cupom" placeholder="Possui cupom de desconto?" class="flex-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-xs font-bold uppercase text-slate-800 dark:text-white outline-none focus:border-brand-500">
                    <button type="button" onclick="aplicarCupom()" class="bg-slate-900 hover:bg-slate-800 text-white font-black text-xs px-4 py-2.5 rounded-xl border border-slate-700 transition-colors uppercase tracking-wider">Aplicar</button>
                </div>
                <div id="status-cupom" class="text-xs font-bold mb-4 hidden"></div>
                
                <div class="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
                    <h3 class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3 flex items-center"><i class="ph-fill ph-moped mr-2 text-brand-500 text-lg"></i> Logística</h3>
                    
                    <div class="flex space-x-2 mb-4">
                        <label id="label-delivery" class="flex-1 cursor-pointer">
                            <input type="radio" name="tipo_entrega" value="entrega" checked onchange="toggleEndereco(true)" class="peer sr-only">
                            <div class="text-center py-3 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 peer-checked:bg-brand-50 dark:peer-checked:bg-brand-500/20 peer-checked:text-brand-600 dark:peer-checked:text-brand-400 peer-checked:border-brand-200 dark:peer-checked:border-brand-500/40 transition-colors"><i class="ph-bold ph-moped text-lg mb-1 block"></i> Delivery</div>
                        </label>
                        <label id="label-retirada" class="flex-1 cursor-pointer">
                            <input type="radio" name="tipo_entrega" value="retirada" onchange="toggleEndereco(false)" class="peer sr-only">
                            <div class="text-center py-3 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 peer-checked:bg-brand-50 dark:peer-checked:bg-brand-500/20 peer-checked:text-brand-600 dark:peer-checked:text-brand-400 peer-checked:border-brand-200 dark:peer-checked:border-brand-500/40 transition-colors"><i class="ph-bold ph-storefront text-lg mb-1 block"></i> Retirar Local</div>
                        </label>
                    </div>

                    <div id="box-endereco" class="space-y-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4 rounded-2xl transition-all">
                        <label class="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">Bairro de Entrega (Para a Taxa)</label>
                        <div class="relative mb-2">
                            <select id="ped-bairro" onchange="calcularFrete()" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-white rounded-xl text-sm font-bold outline-none focus:border-brand-500 appearance-none">
                                <option value="0">Carregando...</option>
                            </select>
                            <i class="ph-bold ph-caret-down absolute right-4 top-1/2 transform -translate-y-1/2 text-slate-400 pointer-events-none"></i>
                        </div>

                        <label class="block text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1 mt-4">Endereço de Entrega</label>
                        <div class="grid grid-cols-3 gap-2">
                            <input type="text" id="ped-cep" placeholder="CEP" onblur="buscarCepCheckout(this.value)" class="col-span-1 px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 text-brand-600 dark:text-brand-400 font-bold rounded-xl text-sm outline-none focus:border-brand-500 text-center">
                            <input type="text" id="ped-rua" placeholder="Rua e Bairro" class="col-span-2 px-4 py-3 bg-slate-200 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-white rounded-xl text-sm font-medium outline-none focus:border-brand-500 transition-colors">
                        </div>
                        <div class="grid grid-cols-3 gap-2 mt-2">
                            <input type="text" id="ped-num" placeholder="Nº" class="col-span-1 px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-white rounded-xl text-sm font-bold outline-none focus:border-brand-500 text-center">
                            <input type="text" id="ped-comp" placeholder="Complemento (Ex: Casa 2)" class="col-span-2 px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-white rounded-xl text-sm font-medium outline-none focus:border-brand-500">
                        </div>
                        
                        <div class="flex justify-between items-center text-sm font-bold text-slate-500 dark:text-slate-400 mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 hidden" id="box-frete">
                            <span class="uppercase tracking-widest text-[10px]">Taxa de Entrega:</span>
                            <span id="valor-frete" class="text-brand-500 dark:text-brand-400 font-black">+ R$ 0,00</span>
                        </div>
                    </div>

                    <h3 class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3 mt-6 flex items-center"><i class="ph-fill ph-user mr-2 text-brand-500 text-lg"></i> Identificação</h3>

                    <!-- FORM GUEST -->
                    <div id="area-guest" class="space-y-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4 rounded-2xl">
                        <div class="bg-brand-50 dark:bg-brand-500/10 p-3 rounded-xl border border-brand-200 dark:border-brand-500/20 mb-4">
                            <p class="text-[11px] text-brand-600 dark:text-brand-400 font-bold leading-snug"><i class="ph-fill ph-star"></i> Faça login (Feche a sacola e vá em "Entrar") para ganhar Pontos nesta compra!</p>
                        </div>
                        <input type="text" id="guest-nome" placeholder="Seu Nome Completo" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm">
                        <input type="tel" id="guest-tel" placeholder="WhatsApp (Apenas números)" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm">
                        <input type="text" id="guest-cpf" placeholder="CPF (Opcional, digite só números)" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm" maxlength="14">
                    </div>

                    <!-- RESUMO LOGADO -->
                    <div id="area-logado" class="hidden space-y-3">
                        <div class="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4 rounded-2xl">
                            <p class="text-sm font-black text-slate-800 dark:text-white" id="logado-nome-resumo">Nome</p>
                        </div>
                        <div>
                            <label class="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest block mb-1">Confirme seu CPF para Pagamento</label>
                            <input type="text" id="logado-cpf" placeholder="Apenas números (Opcional)" class="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm" maxlength="14">
                        </div>
                    </div>
                </div>

                <!-- PAGAMENTO -->
                <div class="mt-8 pt-6 border-t border-slate-200 dark:border-slate-800">
                    <label class="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest block mb-3">Forma de Pagamento</label>
                    <select id="forma-pag-online" onchange="toggleAreaCartao()" class="w-full px-4 py-4 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none font-bold text-slate-800 dark:text-white mb-4 appearance-none shadow-sm transition-colors">
                        <option value="pix">⚡ Pix (Aprovação Imediata)</option>
                        <option value="credito">💳 Cartão de Crédito</option>
                        <option value="entrega">💵 Pagar na Entrega</option>
                    </select>

                    <div id="area-cartao" class="hidden bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-4 space-y-3 relative overflow-hidden transition-colors">
                        <div class="absolute top-0 left-0 w-1 h-full bg-brand-500"></div>
                        <h3 class="text-xs font-black text-slate-800 dark:text-white uppercase tracking-widest mb-3 flex items-center"><i class="ph-bold ph-credit-card mr-2 text-brand-500 text-lg"></i> Dados do Cartão</h3>
                        <input type="text" id="cc-num" placeholder="Número do Cartão" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm" maxlength="19">
                        <input type="text" id="cc-nome" placeholder="Nome Impresso" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm uppercase">
                        <div class="grid grid-cols-2 gap-3">
                            <input type="text" id="cc-val" placeholder="Validade (MM/AA)" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm" maxlength="5">
                            <input type="tel" id="cc-cvv" placeholder="CVV" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm" maxlength="4">
                        </div>
                        <select id="cc-parcelas" class="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-800 dark:text-white outline-none focus:border-brand-500 text-sm font-bold appearance-none">
                            <option value="1">1x sem juros</option>
                        </select>
                    </div>
                    
                    <div class="bg-slate-100 dark:bg-slate-900 p-4 rounded-xl flex justify-between items-center text-slate-800 dark:text-white mt-6 border border-slate-200 dark:border-slate-700 transition-colors">
                        <span class="text-xs font-bold uppercase tracking-widest">Pagar Hoje:</span>
                        <span class="text-2xl font-black text-brand-500 dark:text-brand-400" id="final-total">R$ 0,00</span>
                    </div>
                </div>
            </div>

            <div class="absolute bottom-0 w-full bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 p-4 transition-colors">
                <button onclick="enviarPedidoNuvem(event)" id="btn-enviar-pedido" class="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-black py-4 rounded-xl flex justify-between px-6 items-center shadow-[0_10px_30px_rgba(16,185,129,0.2)] active:scale-95 transition-transform uppercase tracking-widest text-xs">
                    <span>Confirmar Pedido</span>
                    <span id="carrinho-total-final" class="text-sm">R$ 0,00</span>
                </button>
            </div>
        </div>
    </div>

    <!-- 🚨 NOVO: ALERTA PREMIUM CUSTOMIZADO (Substitui os alertas do Chrome) 🚨 -->
    <div id="alerta-customizado" class="fixed inset-0 bg-slate-900/80 z-[250] hidden items-center justify-center p-4 backdrop-blur-sm transition-opacity">
        <div class="bg-white dark:bg-slate-900 rounded-3xl p-8 max-w-sm w-full text-center shadow-2xl relative border border-slate-200 dark:border-slate-800">
            <div id="alerta-icone-bg" class="w-20 h-20 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center mx-auto mb-4 border-4 border-white dark:border-slate-800 shadow-md">
                <i id="alerta-icone" class="ph-fill ph-bell-ringing text-4xl"></i>
            </div>
            <h3 id="alerta-titulo" class="text-xl font-black text-slate-800 dark:text-white mb-2 tracking-tight">Aviso</h3>
            <p id="alerta-mensagem" class="text-slate-500 dark:text-slate-400 text-sm font-medium mb-6 leading-relaxed">Sua mensagem aqui.</p>
            <button type="button" onclick="fecharAlertaPremium()" class="w-full bg-brand-500 hover:bg-brand-600 text-white font-black py-4 rounded-xl transition-transform active:scale-95 uppercase tracking-widest text-xs shadow-lg">
                OK, Entendi
            </button>
        </div>
    </div>

    <!-- 🚨 NOVO: TELA PROFISSIONAL DE PAGAMENTO PIX 🚨 -->
    <div id="modal-pix" class="fixed inset-0 bg-slate-900/90 z-[250] hidden items-center justify-center p-4 backdrop-blur-sm transition-opacity">
        <div class="bg-white dark:bg-slate-900 rounded-3xl p-8 max-w-md w-full text-center shadow-2xl relative border border-slate-200 dark:border-slate-800">
            <div class="w-20 h-20 bg-emerald-50 text-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4 border-4 border-white dark:border-slate-800 shadow-md">
                <i class="ph-fill ph-check-circle text-4xl"></i>
            </div>
            <h3 class="text-2xl font-black text-slate-800 dark:text-white mb-2 tracking-tight">Pedido <span id="pix-pedido-num" class="text-brand-500"></span> Gerado!</h3>
            <p class="text-slate-500 dark:text-slate-400 text-sm font-medium mb-6 leading-relaxed">Copie o código PIX abaixo e pague no aplicativo do seu banco para liberar o preparo na cozinha.</p>
            
            <div class="bg-slate-100 dark:bg-slate-800 p-4 rounded-xl mb-6 relative group overflow-hidden">
                <p id="pix-codigo-texto" class="text-[10px] font-mono text-slate-600 dark:text-slate-400 break-all select-all"></p>
            </div>
            
            <div class="grid grid-cols-1 gap-3">
                <button type="button" onclick="copiarPixPremium()" id="btn-copiar-pix" class="w-full bg-slate-900 dark:bg-white dark:text-slate-900 hover:bg-slate-800 text-white font-black py-4 rounded-xl transition-colors active:scale-95 uppercase tracking-widest text-xs shadow-lg flex items-center justify-center">
                    <i class="ph-bold ph-copy mr-2 text-lg"></i> Copiar Código PIX
                </button>
                <button type="button" onclick="window.location.reload()" class="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-black py-4 rounded-xl transition-colors active:scale-95 uppercase tracking-widest text-xs shadow-lg">
                    Já paguei, Fechar
                </button>
            </div>
        </div>
    </div>
    
    <!-- ============================================== -->
    <!-- MOTOR JAVASCRIPT PRINCIPAL -->
    <!-- ============================================== -->
    <script>
        function toggleTheme() {
            const icon = document.getElementById('theme-icon');
            if (document.documentElement.classList.contains('dark')) {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
                if(icon) icon.classList.replace('ph-sun', 'ph-moon');
            } else {
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
                if(icon) icon.classList.replace('ph-moon', 'ph-sun');
            }
        }

        let produtosServer = [];
        let carrinho = [];
        let clienteLogado = null;
        let produtoSendoMontado = null;
        let complementosAtuais = [];
        let cupomAplicado = null;
        let valorDescontoCupom = 0;
        let taxasEntrega = [];
        let valorFreteAtual = 0;

        document.addEventListener('DOMContentLoaded', () => {
            carregarConfiguracoes(); 
            verificarSessao();
            carregarCardapioDigital();
            carregarTaxasEntrega(); 
        });

        // 🚨 SUBSTITUI TODOS OS ALERTS NATIVOS DO NAVEGADOR PELO SISTEMA PREMIUM 🚨
        let alertaCallbackGlobal = null;
        function alertaPremium(mensagem, titulo = "Aviso da Loja", tipo = "info", callback = null) {
            document.getElementById('alerta-titulo').innerText = titulo;
            document.getElementById('alerta-mensagem').innerText = mensagem;
            
            const icone = document.getElementById('alerta-icone');
            const bg = document.getElementById('alerta-icone-bg');
            
            if(tipo === 'sucesso') {
                icone.className = "ph-fill ph-check-circle text-4xl";
                bg.className = "w-20 h-20 bg-emerald-50 text-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4 border-4 border-white dark:border-slate-800 shadow-md";
            } else if (tipo === 'erro') {
                icone.className = "ph-fill ph-warning-circle text-4xl";
                bg.className = "w-20 h-20 bg-red-50 text-red-500 rounded-full flex items-center justify-center mx-auto mb-4 border-4 border-white dark:border-slate-800 shadow-md";
            } else {
                icone.className = "ph-fill ph-bell-ringing text-4xl";
                bg.className = "w-20 h-20 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center mx-auto mb-4 border-4 border-white dark:border-slate-800 shadow-md";
            }
            
            alertaCallbackGlobal = callback;
            document.getElementById('alerta-customizado').classList.replace('hidden', 'flex');
        }

        function fecharAlertaPremium() {
            document.getElementById('alerta-customizado').classList.replace('flex', 'hidden');
            if (typeof alertaCallbackGlobal === 'function') {
                alertaCallbackGlobal();
                alertaCallbackGlobal = null;
            }
        }
        
        window.alert = function(msg) { alertaPremium(msg); }; // Mágica que intercepta todos os alerts antigos!

        // Função do Botão Copiar PIX
        async function copiarPixPremium() {
            const codigo = document.getElementById('pix-codigo-texto').innerText;
            try {
                await navigator.clipboard.writeText(codigo);
                const btn = document.getElementById('btn-copiar-pix');
                const txtOriginal = btn.innerHTML;
                btn.innerHTML = '<i class="ph-bold ph-check mr-2 text-lg"></i> Copiado!';
                btn.classList.replace('bg-slate-900', 'bg-emerald-500');
                btn.classList.replace('dark:bg-white', 'dark:bg-emerald-500');
                btn.classList.replace('dark:text-slate-900', 'dark:text-white');
                setTimeout(() => {
                    btn.innerHTML = txtOriginal;
                    btn.classList.replace('bg-emerald-500', 'bg-slate-900');
                    btn.classList.replace('dark:bg-emerald-500', 'dark:bg-white');
                    btn.classList.replace('dark:text-white', 'dark:text-slate-900');
                }, 2000);
            } catch(e) { alert("Pix Copiado com Sucesso!"); }
        }

        // 🚨 FUNÇÃO DE BUSCA DE CEP PARA CADASTRO E EDIÇÃO DE PERFIL 🚨
        async function buscarCep(cep, tipo) {
            const cepLimpo = cep.replace(/\D/g, '');
            if (cepLimpo.length === 8) {
                let ruaField, bairroField, numField;

                if (tipo === 'edit') {
                    ruaField = document.getElementById('edit-perf-end');
                    numField = document.getElementById('edit-perf-num');
                } else if (tipo === 'reg') {
                    ruaField = document.getElementById('cad-rua');
                    bairroField = document.getElementById('cad-bairro');
                    numField = document.getElementById('cad-num');
                }

                if (ruaField) ruaField.value = "Buscando...";
                if (bairroField) bairroField.value = "Buscando...";

                try {
                    const res = await fetch(`https://viacep.com.br/ws/${cepLimpo}/json/`);
                    const data = await res.json();
                    
                    if (!data.erro) {
                        if (tipo === 'edit') {
                            ruaField.value = `${data.logradouro}, ${data.bairro}`;
                        } else if (tipo === 'reg') {
                            ruaField.value = data.logradouro;
                            if (bairroField) bairroField.value = data.bairro;
                        }
                        // Pula o cursor direto para o campo do número para agilizar!
                        if (numField) numField.focus(); 
                    } else {
                        if (ruaField) ruaField.value = "";
                        if (bairroField) bairroField.value = "";
                        alertaPremium("CEP não localizado. Verifique se digitou corretamente.", "Atenção", "erro");
                    }
                } catch(e) { 
                    if (ruaField) ruaField.value = "";
                    if (bairroField) bairroField.value = "";
                }
            }
        }
        

        // ==========================
        // SISTEMA DE EDIÇÃO DE PERFIL E FOTO
        // ==========================
        function fecharModalEditarPerfil() {
            document.getElementById('modal-editar-perfil').classList.add('hidden');
            document.getElementById('modal-editar-perfil').classList.remove('flex');
        }

        function lerFotoCliente(event) {
            const file = event.target.files[0];
            if(file) {
                const reader = new FileReader();
                reader.onloadend = () => {
                    document.getElementById('edit-perf-foto-base64').value = reader.result;
                    const imgPreview = document.getElementById('edit-perf-foto-preview');
                    imgPreview.src = reader.result;
                    imgPreview.classList.remove('hidden');
                    document.getElementById('edit-perf-iniciais').classList.add('hidden');
                };
                reader.readAsDataURL(file);
            }
        }

        async function carregarModalPerfil() {
            if(!clienteLogado) return;
            try {
                const res = await fetch(`/api/cliente/${clienteLogado.id}/perfil`);
                if(res.ok) {
                    const d = await res.json();
                    document.getElementById('edit-perf-nome').value = d.nome || "";
                    document.getElementById('edit-perf-tel').value = d.telefone || "";
                    document.getElementById('edit-perf-cep').value = d.cep || "";
                    document.getElementById('edit-perf-end').value = d.endereco || "";
                    document.getElementById('edit-perf-num').value = d.numero || "";
                    document.getElementById('edit-perf-comp').value = d.complemento || "";
                    document.getElementById('edit-perf-senha').value = "";
                    
                    const nomeSeguro = d.nome || "Cliente";
                    const iniciais = nomeSeguro.substring(0, 2).toUpperCase();
                    document.getElementById('edit-perf-iniciais').innerText = iniciais;

                    const imgPreview = document.getElementById('edit-perf-foto-preview');
                    if (clienteLogado.foto && clienteLogado.foto.trim() !== "") {
                        imgPreview.src = clienteLogado.foto;
                        imgPreview.classList.remove('hidden');
                        document.getElementById('edit-perf-iniciais').classList.add('hidden');
                    } else {
                        imgPreview.classList.add('hidden');
                        document.getElementById('edit-perf-iniciais').classList.remove('hidden');
                    }
                    
                    document.getElementById('modal-perfil').classList.replace('flex', 'hidden'); 
                    document.getElementById('modal-editar-perfil').classList.remove('hidden');
                    document.getElementById('modal-editar-perfil').classList.add('flex');
                }
            } catch(e) { alert("Erro ao puxar seus dados."); }
        }

        async function salvarEdicaoPerfil(e) {
            e.preventDefault();
            const btn = document.getElementById('btn-salvar-perfil');
            btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-lg"></i>';
            
            const cepDigitado = document.getElementById('edit-perf-cep').value;
            const ruaDigitada = document.getElementById('edit-perf-end').value;
            const numDigitado = document.getElementById('edit-perf-num').value;
            const compDigitado = document.getElementById('edit-perf-comp').value;

            // Monta a string segura para o banco de dados (Python) não perder nada
            let endFinalBanco = `${ruaDigitada}, ${numDigitado}`;
            if (compDigitado) endFinalBanco += ` (${compDigitado})`;
            if (cepDigitado) endFinalBanco += ` - CEP: ${cepDigitado}`;

            const payload = {
                nome: document.getElementById('edit-perf-nome').value,
                telefone: document.getElementById('edit-perf-tel').value.replace(/\D/g, ''),
                cep: cepDigitado,
                endereco: endFinalBanco, // Enviado montado para a nuvem
                numero: numDigitado,
                complemento: compDigitado,
                senha: document.getElementById('edit-perf-senha').value,
                foto: document.getElementById('edit-perf-foto-base64').value
            };
            
            try {
                const res = await fetch(`/api/cliente/${clienteLogado.id}/perfil`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                if(res.ok) {
                alert("Seus dados foram atualizados com sucesso!");
                
                // 🚨 CORREÇÃO: Força as variáveis separadas pro cache
                clienteLogado.nome = payload.nome;
                clienteLogado.telefone = payload.telefone;
                clienteLogado.cep = payload.cep;
                clienteLogado.endereco = payload.endereco;
                clienteLogado.numero = payload.numero;
                clienteLogado.complemento = payload.complemento;
                clienteLogado.endereco_completo = `${payload.endereco}, ${payload.numero} (${payload.complemento})`;
                
                if(payload.foto) clienteLogado.foto = payload.foto;
                localStorage.setItem('arts_cliente', JSON.stringify(clienteLogado));
                // ... resto do seu código
                    
                    document.getElementById('modal-editar-perfil').classList.replace('flex', 'hidden');
                    verificarSessao(); 
                } else {
                    alert("Erro ao salvar dados.");
                }
            } catch(e) { alert("Erro de conexão com o banco."); }
            btn.innerHTML = "Atualizar Perfil";
        }

        // ==========================
        // SISTEMA LOGÍSTICA E GERAL
        // ==========================
        let eventoInstalacao;
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js').then(reg => { console.log('App Registrado!'); }).catch(err => console.log('Erro no App', err));
            });
        }
        window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); eventoInstalacao = e; });
        
        function instalarApp() { 
            if (eventoInstalacao) { 
                eventoInstalacao.prompt(); 
            } else {
                alert("Para instalar o nosso App, abra o menu do seu navegador (os 3 pontinhos ou botão de Compartilhar) e toque em 'Adicionar à Tela Inicial'.");
            }
        }

        async function carregarTaxasEntrega() {
            try {
                const res = await fetch('/api/taxas/listar'); // Rota corrigida!
                taxasEntrega = await res.json();
                const sel = document.getElementById('ped-bairro');
                if(sel) {
                    if(taxasEntrega.length === 0) sel.innerHTML = '<option value="0">Frete Único / Grátis</option>';
                    else sel.innerHTML = '<option value="0">Selecione seu bairro de entrega...</option>' + taxasEntrega.map(t => `<option value="${t.taxa}">${t.bairro}</option>`).join('');
                }
            } catch(e) {}
        }

        function toggleEndereco(mostrar) {
            if(mostrar) document.getElementById('box-endereco').classList.remove('hidden');
            else document.getElementById('box-endereco').classList.add('hidden');
            calcularFrete(); 
        }

        function calcularFrete() {
            const radioEntrega = document.querySelector('input[name="tipo_entrega"]:checked');
            const isDelivery = radioEntrega && radioEntrega.value === 'entrega';
            const selBairro = document.getElementById('ped-bairro');
            
            valorFreteAtual = (isDelivery && selBairro && selBairro.value !== "0") ? parseFloat(selBairro.value) : 0;
            
            const boxFrete = document.getElementById('box-frete');
            if (isDelivery && valorFreteAtual > 0) {
                boxFrete.classList.remove('hidden');
                document.getElementById('valor-frete').innerText = `+ R$ ${valorFreteAtual.toFixed(2).replace('.',',')}`;
            } else { if(boxFrete) boxFrete.classList.add('hidden'); }
            atualizarContadoresCheckout(); 
        }

        function atualizarContadoresCheckout() {
            const subtotal = carrinho.reduce((acc, item) => acc + (item.preco * item.quantidade), 0);
            let final = subtotal - valorDescontoCupom + valorFreteAtual;
            if(final < 0) final = 0;
            const btnFinal1 = document.getElementById('final-total'); if(btnFinal1) btnFinal1.innerText = `R$ ${final.toFixed(2).replace('.',',')}`;
            const btnFinal2 = document.getElementById('carrinho-total-final'); if(btnFinal2) btnFinal2.innerText = `R$ ${final.toFixed(2).replace('.',',')}`;
        }

        function abrirZoom(url) {
            const modal = document.getElementById('modal-zoom'); const img = document.getElementById('img-zoom');
            img.src = url; modal.classList.remove('hidden'); modal.classList.add('flex');
            setTimeout(() => { img.classList.replace('scale-95', 'scale-100'); }, 10);
        }
        function fecharZoom() { 
            const modal = document.getElementById('modal-zoom'); const img = document.getElementById('img-zoom');
            img.classList.replace('scale-100', 'scale-95');
            setTimeout(() => { modal.classList.add('hidden'); modal.classList.remove('flex'); }, 200);
        }

        function abrirModalInfoLoja() {
            document.getElementById('modal-info-loja').classList.remove('hidden');
            document.getElementById('modal-info-loja').classList.add('flex');
        }

        // 🚨 RELÓGIO INTELIGENTE: LÊ O DIA EXATO E MOSTRA SE ESTÁ ABERTO 🚨
        function atualizarStatusAberto(horarioStr) {
            const statusDot = document.getElementById('status-dot');
            const statusText = document.getElementById('status-text');
            const statusTextModal = document.getElementById('info-modal-status-text');
            
            let aberto = true; 
            
            if(horarioStr && horarioStr.trim() !== "") {
                try {
                    const diasSemana = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];
                    const dataAtual = new Date();
                    const diaAtualNome = diasSemana[dataAtual.getDay()]; 
                    
                    const strLower = horarioStr.toLowerCase();
                    const partes = strLower.split(',');
                    const parteHoje = partes.find(p => p.includes(diaAtualNome) || p.includes(diaAtualNome.replace('ç', 'c')));
                    
                    if (parteHoje) {
                        if (parteHoje.includes('fechado')) {
                            aberto = false;
                        } else {
                            // Extrai os horários no formato 19:00 ou 19h
                            const times = parteHoje.match(/(\d{1,2})[h:]?(\d{2})?/g);
                            if (times && times.length >= 2) {
                                let extractTime = (tStr) => {
                                    let clean = tStr.replace('h', ':');
                                    if(!clean.includes(':')) clean += ':00';
                                    let [h, m] = clean.split(':');
                                    return parseInt(h) * 60 + (parseInt(m) || 0);
                                };
                                
                                let minInicio = extractTime(times[0]);
                                let minFim = extractTime(times[1]);
                                let minAgora = dataAtual.getHours() * 60 + dataAtual.getMinutes();
                                
                                if (minInicio < minFim) {
                                    aberto = (minAgora >= minInicio && minAgora <= minFim);
                                } else {
                                    aberto = (minAgora >= minInicio || minAgora <= minFim); // Passou da meia noite
                                }
                            }
                        }
                    }
                } catch(e) { console.error("Erro no relógio inteligente:", e); }
            }

            if(aberto) {
                statusDot.className = "w-1.5 h-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400 mr-1.5 animate-pulse shrink-0";
                statusText.innerText = "Aberto agora";
                statusText.className = "text-emerald-500 dark:text-emerald-400";
                if(statusTextModal) {
                    statusTextModal.innerText = "ESTAMOS ABERTOS! FAÇA SEU PEDIDO.";
                    statusTextModal.className = "text-[10px] font-bold uppercase tracking-widest text-emerald-500 dark:text-emerald-400 mb-6";
                }
            } else {
                statusDot.className = "w-1.5 h-1.5 rounded-full bg-red-500 dark:bg-red-400 mr-1.5 shrink-0";
                statusText.innerText = "Fechado agora";
                statusText.className = "text-red-500 dark:text-red-400";
                if(statusTextModal) {
                    statusTextModal.innerText = "A LOJA ESTÁ FECHADA NO MOMENTO.";
                    statusTextModal.className = "text-[10px] font-bold uppercase tracking-widest text-red-500 dark:text-red-400 mb-6";
                }
            }
        }

        async function carregarConfiguracoes() {
            try {
                const res = await fetch('/api/gestao/configuracoes'); 
                const configLoja = await res.json();
                
                if(configLoja.nome_empresa) { 
                    const nomeEl = document.getElementById('nome-loja-header'); 
                    if(nomeEl) nomeEl.innerHTML = `${configLoja.nome_empresa} <i class="ph-bold ph-caret-down text-sm ml-0.5 text-slate-400"></i>`; 
                    document.getElementById('info-modal-nome').innerText = configLoja.nome_empresa;
                }

                document.getElementById('info-modal-horario').innerText = configLoja.horario_funcionamento || "Não informado";
                document.getElementById('info-modal-tel').innerText = configLoja.telefone || "Não informado";
                document.getElementById('info-modal-end').innerText = configLoja.endereco || "Não informado";
                
                atualizarStatusAberto(configLoja.horario_funcionamento);
                
                // INJETANDO A LOGO NO CABEÇALHO E NO MODAL
                if(configLoja.logo_url && String(configLoja.logo_url).trim() !== '' && configLoja.logo_url !== 'None') {
                    const letra = document.getElementById('header-logo-letra'); 
                    const img = document.getElementById('header-logo-img'); 
                    const container = document.getElementById('header-logo-container');
                    
                    const modalImg = document.getElementById('info-modal-img');
                    const modalIcon = document.getElementById('info-modal-icon');
                    const modalContainer = document.getElementById('info-modal-logo-container');

                    if(letra && img && container) {
                        img.onerror = function() { this.classList.add('hidden'); letra.classList.remove('hidden'); };
                        img.src = configLoja.logo_url; 
                        img.classList.remove('hidden');
                        letra.classList.add('hidden'); 
                        container.classList.remove('bg-brand-500', 'border-slate-800', 'dark:border-slate-800'); 
                        container.classList.add('bg-white', 'border-slate-200', 'dark:border-slate-700');
                    }

                    if(modalImg && modalIcon && modalContainer) {
                        modalImg.src = configLoja.logo_url;
                        modalImg.classList.remove('hidden');
                        modalIcon.classList.add('hidden');
                        modalContainer.classList.remove('bg-brand-50', 'dark:bg-brand-500/10', 'text-brand-500', 'border-brand-100');
                        modalContainer.classList.add('bg-white', 'dark:bg-slate-800', 'border-slate-200', 'dark:border-slate-700');
                    }
                }

                if(configLoja.aceita_retirada === false) {
                    document.getElementById('label-retirada').style.display = 'none';
                    document.querySelector('input[value="entrega"]').checked = true;
                    toggleEndereco(true);
                }
                if(configLoja.aceita_delivery === false) {
                    document.getElementById('label-delivery').style.display = 'none';
                    document.querySelector('input[value="retirada"]').checked = true;
                    toggleEndereco(false);
                }

                const pgs = configLoja.formas_pagamento ? configLoja.formas_pagamento.split(',') : ['Dinheiro Físico', 'Pix', 'Cartão'];
                const selectPg = document.getElementById('forma-pag-online');
                if(selectPg) {
                    selectPg.innerHTML = pgs.map(pg => {
                        let icone = '💵'; let valLow = pg.toLowerCase(); let valorParaOBanco = pg.trim(); 
                        if(valLow.includes('pix')) { icone = '⚡'; valorParaOBanco = 'pix'; } 
                        else if(valLow.includes('crédito') || valLow.includes('credito') || valLow.includes('cartão online')) { icone = '💳'; valorParaOBanco = 'credito'; }
                        else if(valLow.includes('vr') || valLow.includes('alimentação')) { icone = '🎟️'; valorParaOBanco = 'vr'; }
                        else if(valLow.includes('débito') || valLow.includes('cartão')) { icone = '💳'; }
                        return `<option value="${valorParaOBanco}">${icone} ${pg.trim()}</option>`;
                    }).join('');
                }
            } catch(e) { console.error("Configurações não carregadas.", e); }
        }

        function toggleAreaCartao() {
            const forma = document.getElementById('forma-pag-online').value.toLowerCase();
            const area = document.getElementById('area-cartao');
            if(forma === 'credito' || forma === 'vr') { area.classList.remove('hidden'); } else { area.classList.add('hidden'); }
        }

        function abrirModalRastreio() { 
            document.getElementById('resultado-rastreio').classList.add('hidden'); document.getElementById('input-rastreio').value = '';
            document.getElementById('modal-rastreio').classList.remove('hidden'); document.getElementById('modal-rastreio').classList.add('flex'); 
        }

        async function buscarRastreio() {
            let busca = document.getElementById('input-rastreio').value.trim();
            busca = busca.replace('#', ''); 
            if(!busca) { alert("Digite o número do celular ou a senha da comanda."); return; }
            
            const btn = document.getElementById('btn-rastreio'); 
            const txtOriginal = btn.innerHTML;
            btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-lg"></i>'; 
            btn.disabled = true;
            
            try {
                const res = await fetch(`/api/rastreio/${busca}`);
                
                if(res.ok) {
                    const data = await res.json();
                    
                    // Atualiza os textos com segurança (só se existirem no HTML)
                    const elSenha = document.getElementById('rastreio-senha');
                    if(elSenha) elSenha.innerText = data.senha || data.id; 
                    
                    const elStatus = document.getElementById('rastreio-status');
                    if(elStatus) elStatus.innerText = (data.status || "RECEBIDO").replace(/_/g, ' ');
                    
                    const bar = document.getElementById('rastreio-progresso'); 
                    if(bar) {
                        bar.style.width = (data.progresso || 20) + '%';
                        if(data.progresso === 100) bar.className = "bg-emerald-500 h-full rounded-full transition-all duration-1000";
                        else if(data.progresso === 0) bar.className = "bg-red-500 h-full rounded-full transition-all duration-1000";
                        else bar.className = "bg-blue-500 h-full rounded-full transition-all duration-1000";
                    }

                    // Tenta atualizar a linha do tempo (se o HTML da linha do tempo existir)
                    const statusU = (data.status || "").toUpperCase();
                    const activeStep = (id) => { const el = document.querySelector(`#${id} .step-icon`); if(el) el.className = "w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-black text-xs shrink-0 transition-colors mr-3 step-icon shadow-md shadow-blue-500/30"; };
                    const resetStep = (id) => { const el = document.querySelector(`#${id} .step-icon`); if(el) el.className = "w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-400 flex items-center justify-center font-black text-xs shrink-0 transition-colors mr-3 step-icon"; };
                    
                    resetStep('step-recebido'); resetStep('step-preparo'); resetStep('step-pronto'); resetStep('step-entrega');
                    
                    if (statusU.includes("RECEBIDO") || data.progresso <= 20) { activeStep('step-recebido'); } 
                    else if (statusU.includes("PREPARO") || data.progresso === 50) { activeStep('step-recebido'); activeStep('step-preparo'); } 
                    else if (statusU.includes("PRONTO") || data.progresso === 80) { activeStep('step-recebido'); activeStep('step-preparo'); activeStep('step-pronto'); } 
                    else if (statusU.includes("SAIU") || statusU.includes("ENTREGA") || data.progresso > 80) { activeStep('step-recebido'); activeStep('step-preparo'); activeStep('step-pronto'); activeStep('step-entrega'); }

                    // Cria e exibe o botão do Mapa GPS com segurança
                    let containerMapa = document.getElementById('link-mapa-rastreio');
                    const resultadoBox = document.getElementById('resultado-rastreio');
                    
                    if (!containerMapa && resultadoBox) {
                        containerMapa = document.createElement('div');
                        containerMapa.id = 'link-mapa-rastreio';
                        containerMapa.className = 'mt-4';
                        resultadoBox.appendChild(containerMapa);
                    }

                    if (containerMapa) {
                        if (statusU.includes("SAIU") || statusU.includes("ENTREGA") || data.progresso >= 80) {
                            containerMapa.innerHTML = `
                                <a href="/mapa?pedido=${data.senha || data.id}" target="_blank" class="w-full bg-brand-500 hover:bg-brand-600 text-white font-black py-4 rounded-xl flex items-center justify-center shadow-lg transition-transform active:scale-95 uppercase tracking-widest text-xs animate-pulse">
                                    <i class="ph-bold ph-map-pin-line text-lg mr-2"></i> Ver Motoboy no Mapa
                                </a>
                            `;
                            containerMapa.classList.remove('hidden');
                        } else {
                            containerMapa.classList.add('hidden');
                        }
                    }

                    if(resultadoBox) resultadoBox.classList.remove('hidden');
                } else {
                    alert("Ops! Nenhum pedido encontrado com este número."); 
                    const resBox = document.getElementById('resultado-rastreio');
                    if(resBox) resBox.classList.add('hidden');
                }
            } catch(err) { 
                console.error("Erro capturado no rastreio:", err);
                alert("Erro de conexão ao buscar pedido."); 
            }
            btn.innerHTML = txtOriginal || '<i class="ph-bold ph-magnifying-glass text-lg"></i>'; 
            btn.disabled = false;
        }

        // ==========================================
        // AUTH E PERFIL VIP BLINDADO
        // ==========================================
        function verificarSessao() {
            const dados = localStorage.getItem('arts_cliente');
            const areaGuest = document.getElementById('area-guest');
            const areaLogado = document.getElementById('area-logado');

            if (dados) {
                clienteLogado = JSON.parse(dados);
                
                const nomeSeguro = clienteLogado.nome || "Visitante";
                const fotoAvatar = clienteLogado.foto || "";
                let htmlAvatar = "";
                
                if (fotoAvatar && fotoAvatar.trim() !== "") {
                    htmlAvatar = `<img id="header-foto" src="${fotoAvatar}" class="w-8 h-8 rounded-full border border-slate-200 dark:border-slate-600 object-cover shrink-0">`;
                } else {
                    const inic = nomeSeguro.substring(0, 2).toUpperCase();
                    htmlAvatar = `<div class="w-8 h-8 rounded-full bg-brand-500 text-white flex items-center justify-center font-black text-xs shrink-0">${inic}</div>`;
                }

                // MOSTRA O AVATAR E ESCONDE O BOTÃO "ENTRAR"
                document.getElementById('area-auth').innerHTML = `
                    <button id="btn-instalar-app" onclick="instalarApp()" class="text-xs sm:text-sm bg-brand-500 hover:bg-brand-600 p-2 sm:px-4 sm:py-2 rounded-full font-black transition-all flex items-center text-white shadow-lg shadow-brand-500/40 animate-pulse" title="Instalar App">
                        <i class="ph-bold ph-download-simple sm:mr-2 text-lg"></i> <span class="hidden sm:inline">Instalar</span>
                    </button>
                    <button onclick="toggleTheme()" class="text-sm bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 p-2 sm:px-3 sm:py-2 rounded-full font-bold transition-colors flex items-center text-slate-600 dark:text-brand-400 border border-slate-300 dark:border-white/5 shadow-sm">
                        <i id="theme-icon" class="ph-bold ph-moon text-lg"></i>
                    </button>
                    <button onclick="abrirModalRastreio()" class="text-sm bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 p-2 sm:px-3 sm:py-2 rounded-full font-bold transition-colors flex items-center text-slate-600 dark:text-brand-400 border border-slate-300 dark:border-white/5" title="Rastrear Pedido">
                        <i class="ph-bold ph-crosshair text-lg"></i>
                    </button>
                    <div class="cursor-pointer active:scale-95 transition-transform" onclick="abrirModalPerfil()" title="Meu Perfil">
                        ${htmlAvatar}
                    </div>
                `;
                
                const themeIconEl = document.getElementById('theme-icon');
                if (document.documentElement.classList.contains('dark') && themeIconEl) themeIconEl.classList.replace('ph-moon', 'ph-sun');

                document.getElementById('barra-fidelidade').classList.remove('hidden');
                document.getElementById('fid-pontos').innerText = clienteLogado.pontos || 0;
                const cashbackVal = parseFloat(clienteLogado.cashback) || 0;
                document.getElementById('fid-cashback').innerText = cashbackVal.toFixed(2).replace('.', ',');
                
                if(areaGuest) areaGuest.classList.add('hidden');
                if(areaLogado) {
                    areaLogado.classList.remove('hidden');
                    document.getElementById('logado-nome-resumo').innerText = nomeSeguro;
                    document.getElementById('logado-cpf').value = clienteLogado.cpf || ""; 
                }
            } else {
                if(areaGuest) areaGuest.classList.remove('hidden');
                if(areaLogado) areaLogado.classList.add('hidden');
            }
        }

        function fazerLogout() { localStorage.removeItem('arts_cliente'); window.location.reload(); }

        function abrirModalAuth() { document.getElementById('modal-auth').classList.remove('hidden'); document.getElementById('modal-auth').classList.add('flex'); }
        function fecharModalAuth() { document.getElementById('modal-auth').classList.add('hidden'); document.getElementById('modal-auth').classList.remove('flex'); }
        
        function alternarAbaAuth(aba) {
            const isLogin = aba === 'login';
            document.getElementById('form-login').classList.toggle('hidden', !isLogin); document.getElementById('form-cadastro').classList.toggle('hidden', isLogin);
            document.getElementById('aba-login').className = isLogin ? "flex-1 pb-3 text-brand-500 font-black tracking-widest uppercase text-xs border-b-2 border-brand-500 transition-colors" : "flex-1 pb-3 text-slate-500 font-bold tracking-widest uppercase text-xs border-b-2 border-transparent transition-colors";
            document.getElementById('aba-cadastro').className = !isLogin ? "flex-1 pb-3 text-brand-500 font-black tracking-widest uppercase text-xs border-b-2 border-brand-500 transition-colors" : "flex-1 pb-3 text-slate-500 font-bold tracking-widest uppercase text-xs border-b-2 border-transparent transition-colors";
        }

        async function fazerLogin(e) {
            e.preventDefault();
            const btn = e.target.querySelector('button[type="submit"]'); const txtO = btn.innerHTML;
            btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-xl"></i>'; btn.disabled = true;
            
            const payload = { telefone: document.getElementById('log-tel').value.replace(/\D/g,''), senha: document.getElementById('log-senha').value };
            try {
                const res = await fetch('/api/cliente/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                const data = await res.json();
                if(res.ok) { localStorage.setItem('arts_cliente', JSON.stringify(data.cliente)); fecharModalAuth(); verificarSessao(); window.location.reload(); } 
                else { alert(data.detail); btn.innerHTML = txtO; btn.disabled = false; }
            } catch(err) { alert("Erro de conexão"); btn.innerHTML = txtO; btn.disabled = false; }
        }

        async function fazerCadastro(e) {
            e.preventDefault();
            const payload = {
                nome: document.getElementById('cad-nome').value, telefone: document.getElementById('cad-tel').value.replace(/\D/g,''),
                senha: document.getElementById('cad-senha').value, cpf: document.getElementById('cad-cpf').value.replace(/\D/g,''),
                data_nascimento: document.getElementById('cad-nasc').value, cep: document.getElementById('cad-cep').value.replace(/\D/g,''),
                logradouro: document.getElementById('cad-rua').value, numero: document.getElementById('cad-num').value,
                bairro: document.getElementById('cad-bairro').value, complemento: document.getElementById('cad-comp').value
            };
            try {
                const res = await fetch('/api/cliente/registrar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                if(res.ok) { alert("Cadastro realizado com sucesso! Faça login para continuar."); alternarAbaAuth('login'); }
                else { const data = await res.json(); alert(data.detail); }
            } catch(err) { alert("Erro de conexão"); }
        }

        async function carregarCardapioDigital() {
            try {
                const res = await fetch('/api/cardapio'); produtosServer = await res.json();
                const categorias = [...new Set(produtosServer.map(p => p.categoria).filter(c => c && c.toUpperCase() !== 'INTEGRAÇÕES'))];
                
                document.getElementById('nav-categorias').innerHTML = categorias.map((c, i) => `
                    <a href="#cat-${c.replace(/\s+/g, '-')}" class="shrink-0 px-5 py-2.5 rounded-full text-[11px] font-black uppercase tracking-widest transition-colors ${i===0 ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/30 border-transparent' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:text-brand-500 dark:hover:text-white'}">${c}</a>
                `).join('');

                document.getElementById('lista-produtos').innerHTML = categorias.map(cat => {
                    const prodsCat = produtosServer.filter(p => p.categoria === cat);
                    return `
                        <div id="cat-${cat.replace(/\s+/g, '-')}" class="pt-24 -mt-20 mb-8">
                            <h3 class="text-xl font-black text-slate-800 dark:text-white mb-4 tracking-tight flex items-center">
                                <span class="w-1.5 h-6 bg-brand-500 rounded-full mr-3 block"></span> ${cat}
                            </h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                ${prodsCat.map(p => {
                                    const imgUrl = p.imagem_url || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?q=80&w=800&auto=format&fit=crop";
                                    return `
                                    <div class="bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-3xl p-4 flex gap-4 transition-colors shadow-sm relative">
                                        <div class="flex-1 flex flex-col justify-between pr-2 cursor-pointer active:scale-95 transition-transform" onclick="abrirModalMontagem(${p.id})">
                                            <div>
                                                <h4 class="font-black text-slate-800 dark:text-white text-base leading-tight mb-1">${p.nome}</h4>
                                                <p class="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed mb-3">${p.descricao || 'Experimente esta delícia!'}</p>
                                            </div>
                                            <span class="font-black text-emerald-500 dark:text-emerald-400 text-sm">R$ ${p.preco_venda.toFixed(2).replace('.',',')}</span>
                                        </div>
                                        <div onclick="abrirZoom('${imgUrl}')" class="w-28 h-28 shrink-0 bg-slate-100 dark:bg-slate-900 rounded-2xl overflow-hidden relative border border-slate-200 dark:border-slate-700 cursor-pointer group" title="Clique para dar Zoom">
                                            <img src="${imgUrl}" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">
                                            <div class="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"><i class="ph-bold ph-arrows-out text-white text-2xl drop-shadow-md"></i></div>
                                            <button onclick="event.stopPropagation(); abrirModalMontagem(${p.id})" class="absolute bottom-1 right-1 w-7 h-7 bg-white/90 dark:bg-slate-900/90 backdrop-blur text-brand-500 rounded-xl flex items-center justify-center font-black shadow-md hover:scale-110 transition-transform"><i class="ph-bold ph-plus"></i></button>
                                        </div>
                                    </div>
                                `}).join('')}
                            </div>
                        </div>
                    `;
                }).join('');
            } catch (e) { document.getElementById('lista-produtos').innerHTML = '<p class="text-center text-brand-500 font-bold py-10">Lojinha fechada no momento.</p>'; }
        }

        async function abrirModalMontagem(id) {
            produtoSendoMontado = produtosServer.find(p => p.id === id);
            document.getElementById('modal-prod-nome').innerText = produtoSendoMontado.nome; document.getElementById('modal-prod-desc').innerText = produtoSendoMontado.descricao || "Feito com carinho para você.";
            document.getElementById('modal-prod-preco').innerText = produtoSendoMontado.preco_venda.toFixed(2).replace('.', ','); document.getElementById('modal-prod-total-btn').innerText = produtoSendoMontado.preco_venda.toFixed(2).replace('.', ',');
            
            const imgContainer = document.getElementById('modal-img-container');
            const imgUrl = produtoSendoMontado.imagem_url || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?q=80&w=800&auto=format&fit=crop";
            imgContainer.innerHTML = `<img src="${imgUrl}" onclick="abrirZoom('${imgUrl}')" class="w-full h-full object-cover opacity-80 cursor-pointer hover:opacity-100 transition-opacity"><div class="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent pointer-events-none"></div>`;
            document.getElementById('modal-prod-obs').value = "";
            
            const areaComp = document.getElementById('area-complementos'); areaComp.innerHTML = '<p class="text-center text-slate-500 text-sm py-4"><i class="ph-bold ph-spinner animate-spin text-xl"></i></p>';
            document.getElementById('modal-produto').classList.remove('hidden'); document.getElementById('modal-produto').classList.add('flex');

            try {
                const res = await fetch(`/api/produtos/${id}/complementos`); complementosAtuais = await res.json(); renderizarComplementos();
            } catch(e) { areaComp.innerHTML = ''; }
        }

        function renderizarComplementos() {
            const areaComp = document.getElementById('area-complementos');
            areaComp.innerHTML = complementosAtuais.map((grupo, gIndex) => `
                <div class="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm transition-colors">
                    <h4 class="font-black text-lg text-slate-800 dark:text-white mb-1 flex justify-between items-center">${grupo.nome} <span class="${grupo.obrigatorio ? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/30' : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-300 dark:border-slate-600'} px-3 py-1 rounded-lg text-[10px] font-black tracking-widest uppercase shadow-sm">${grupo.obrigatorio ? 'Obrigatório' : 'Opcional'}</span></h4>
                    <p class="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-4 border-b border-slate-200 dark:border-slate-700 pb-4">Escolha de ${grupo.min} até ${grupo.max} opções</p>
                    <div class="space-y-3">
                        ${grupo.itens.map(i => {
                            const type = grupo.max === 1 ? 'radio' : 'checkbox';
                            return `
                            <label class="flex items-center justify-between text-lg cursor-pointer p-5 bg-white dark:bg-slate-900 hover:border-brand-500 border-2 border-transparent dark:border-slate-700 rounded-xl shadow-sm transition-all group active:scale-95">
                                <div class="flex items-center font-black text-slate-700 dark:text-slate-200 group-hover:text-brand-500">
                                    <input type="${type}" name="grupo_${gIndex}" value="${i.nome}|${i.preco}" onchange="recalcularTotalModal()" class="mr-4 w-6 h-6 accent-brand-500 cursor-pointer">
                                    ${i.nome}
                                </div>
                                ${i.preco > 0 ? `<span class="text-brand-500 font-black bg-brand-50 dark:bg-brand-500/10 px-2 py-1 rounded-lg">+ R$ ${i.preco.toFixed(2).replace('.',',')}</span>` : `<span class="text-slate-400 text-[10px] font-black uppercase tracking-widest bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded-lg">Incluso</span>`}
                            </label>`
                        }).join('')}
                    </div>
                </div>
            `).join('');
            recalcularTotalModal();
        }

        function recalcularTotalModal() {
            let totalAdicionais = 0; document.querySelectorAll('#area-complementos input:checked').forEach(input => { totalAdicionais += parseFloat(input.dataset.preco); });
            const totalGeral = produtoSendoMontado.preco_venda + totalAdicionais; document.getElementById('modal-prod-total-btn').innerText = totalGeral.toFixed(2).replace('.', ',');
        }

        function fecharModalProduto() { document.getElementById('modal-produto').classList.add('hidden'); document.getElementById('modal-produto').classList.remove('flex'); }

        function confirmarAdicaoProduto() {
            let totalAdicionais = 0; let strAdicionais = []; let inputsInvalidos = false;
            complementosAtuais.forEach((grupo, gIndex) => {
                const selecionados = document.querySelectorAll(`input[name="grupo_${gIndex}"]:checked`);
                if(grupo.obrigatorio && selecionados.length < grupo.min) { alert(`⚠️ Obrigatório: Escolha pelo menos ${grupo.min} opção em "${grupo.nome}".`); inputsInvalidos = true; }
                if(selecionados.length > grupo.max) { alert(`⚠️ Limite excedido: Máximo de ${grupo.max} opções em "${grupo.nome}".`); inputsInvalidos = true; }
                selecionados.forEach(sel => {
                    totalAdicionais += parseFloat(sel.dataset.preco);
                    const precoAdd = parseFloat(sel.dataset.preco) > 0 ? `(+R$ ${parseFloat(sel.dataset.preco).toFixed(2)})` : '';
                    strAdicionais.push(`-> ${sel.dataset.nome} ${precoAdd}`);
                });
            });

            if(inputsInvalidos) return;
            const obsBase = document.getElementById('modal-prod-obs').value;
            const obsFinal = strAdicionais.length > 0 ? `Opções Extras: ${strAdicionais.join(' | ')}. ${obsBase ? 'Obs: ' + obsBase : ''}` : obsBase;
            const precoFinal = produtoSendoMontado.preco_venda + totalAdicionais;

            const itemExistente = carrinho.find(i => i.produto_id === produtoSendoMontado.id && i.observacao === obsFinal);
            if (itemExistente) { itemExistente.quantidade++; } else { carrinho.push({ produto_id: produtoSendoMontado.id, nome: produtoSendoMontado.nome, preco: precoFinal, quantidade: 1, observacao: obsFinal, img: produtoSendoMontado.imagem_url }); }
            
            fecharModalProduto(); atualizarContadores();
        }

        async function aplicarCupom() {
            const codigo = document.getElementById('input-cupom').value.trim().toUpperCase();
            const subtotal = carrinho.reduce((acc, item) => acc + (item.preco * item.quantidade), 0);
            const statusDiv = document.getElementById('status-cupom');
            if(!codigo) { alert("Digite o código do cupom."); return; }

            try {
                const res = await fetch('/api/carrinho/validar-cupom', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ codigo, subtotal }) });
                const data = await res.json();
                if(res.ok) {
                    cupomAplicado = data.codigo; valorDescontoCupom = data.valor_desconto;
                    statusDiv.className = "text-xs font-bold mb-4 text-emerald-500 dark:text-emerald-400 block";
                    statusDiv.innerText = `✅ Cupom "${data.codigo}" aplicado! Desconto de R$ ${data.valor_desconto.toFixed(2).replace('.', ',')}`;
                    atualizarContadores();
                } else {
                    statusDiv.className = "text-xs font-bold mb-4 text-red-500 dark:text-red-400 block"; statusDiv.innerText = `❌ ${data.detail || "Cupom inválido."}`;
                    cupomAplicado = null; valorDescontoCupom = 0; atualizarContadores();
                }
            } catch(e) { alert("Erro ao validar cupom."); }
        }

        function atualizarContadores() {
            const subtotalLocal = carrinho.reduce((acc, item) => acc + (item.preco * item.quantidade), 0);
            if(cupomAplicado) { const divDesc = document.getElementById('div-desconto'); if(divDesc) divDesc.classList.remove('hidden'); } else { const divDesc = document.getElementById('div-desconto'); if(divDesc) divDesc.classList.add('hidden'); }

            let final = subtotalLocal - valorDescontoCupom; if(final < 0) final = 0;
            const form = `R$ ${final.toFixed(2).replace('.', ',')}`;
            const carTotalFlu = document.getElementById('carrinho-total-flutuante'); if(carTotalFlu) carTotalFlu.innerText = form;
            
            const qtd = carrinho.reduce((acc, item) => acc + item.quantidade, 0);
            const carQtd = document.getElementById('carrinho-qtd'); if(carQtd) carQtd.innerText = qtd;
            
            const barra = document.getElementById('barra-carrinho');
            if (qtd > 0) { barra.classList.remove('translate-y-40'); } 
            else {
                barra.classList.add('translate-y-40'); cupomAplicado = null; valorDescontoCupom = 0;
                const sc = document.getElementById('status-cupom'); if(sc) { sc.classList.add('hidden'); document.getElementById('input-cupom').value = ''; }
                fecharCarrinho();
            }
            atualizarContadoresCheckout();
        }

        function abrirCarrinho() {
            const lista = document.getElementById('lista-carrinho-modal');
            lista.innerHTML = carrinho.map((item, index) => `
                <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 p-6 rounded-3xl flex items-center justify-between shadow-sm transition-colors">
                    <img src="${item.img || ''}" class="w-24 h-24 rounded-2xl object-cover mr-6 shadow-sm border border-slate-100 dark:border-slate-800" onerror="this.src='https://images.unsplash.com/photo-1568901346375-23c9450c58cd?q=80&w=200&auto=format&fit=crop';">
                    <div class="flex-1 pr-4">
                        <h4 class="font-black text-slate-800 dark:text-white text-2xl leading-tight mb-2">${item.nome}</h4>
                        ${item.observacao ? `<p class="text-xs text-slate-500 dark:text-slate-400 font-bold mb-2 leading-snug uppercase tracking-widest">${item.observacao}</p>` : ''}
                        <p class="font-black text-brand-500 text-xl">R$ ${(item.preco * item.quantidade).toFixed(2).replace('.',',')}</p>
                    </div>
                    <div class="flex flex-col items-center bg-slate-50 dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 p-2 shadow-inner">
                        <button onclick="carrinho[${index}].quantidade++; atualizarContadores(); abrirCarrinho();" class="w-14 h-12 flex items-center justify-center bg-white dark:bg-slate-900 rounded-xl shadow-sm text-brand-500 font-black text-2xl touch-effect mb-2"><i class="ph-bold ph-plus"></i></button>
                        <span class="font-black text-2xl text-slate-800 dark:text-white my-1">${item.quantidade}</span>
                        <button onclick="carrinho[${index}].quantidade--; if(carrinho[${index}].quantidade<=0) carrinho.splice(${index},1); atualizarContadores(); abrirCarrinho();" class="w-14 h-12 flex items-center justify-center bg-white dark:bg-slate-900 rounded-xl shadow-sm text-slate-400 dark:text-slate-500 font-black text-2xl touch-effect mt-2"><i class="ph-bold ph-minus"></i></button>
                    </div>
                </div>
            `).join('');
            
            // 🚨 EXTRATOR INTELIGENTE DEFINITIVO 🚨
            if (clienteLogado && document.getElementById('ped-rua').value === "") {
                let cepStr = clienteLogado.cep || "";
                let ruaStr = clienteLogado.endereco || "";
                let numStr = clienteLogado.numero || "";
                let compStr = clienteLogado.complemento || "";

                // Se logou em outro aparelho e a API só devolveu a frase inteira "Rua X, 123 (Casa) - CEP: 000"
                if (!ruaStr && clienteLogado.endereco_completo) {
                    let endCompleto = clienteLogado.endereco_completo; 
                    
                    const matchCep = endCompleto.match(/(?:CEP:\s*)?(\d{5}-?\d{3})/i);
                    if (matchCep) {
                        cepStr = matchCep[1].trim();
                        endCompleto = endCompleto.replace(matchCep[0], '').replace(/-\s*$/, '').trim();
                    }

                    const matchComp = endCompleto.match(/\((.*?)\)/);
                    if (matchComp) {
                        compStr = matchComp[1].trim();
                        endCompleto = endCompleto.replace(/\(.*?\)/, '').trim(); 
                    }

                    let partes = endCompleto.split(',');
                    if (partes.length > 1) {
                        let ultimaParte = partes.pop().trim(); 
                        let matchNum = ultimaParte.match(/(\d+)/);
                        if (matchNum) {
                            numStr = matchNum[0];
                            ruaStr = partes.join(',').trim();
                        } else {
                            ruaStr = endCompleto; 
                        }
                    } else {
                        ruaStr = endCompleto;
                    }
                }

                // Limpeza de vírgulas sobrando
                if (ruaStr.startsWith(',')) ruaStr = ruaStr.substring(1).trim();

                document.getElementById('ped-cep').value = cepStr;
                document.getElementById('ped-rua').value = ruaStr;
                document.getElementById('ped-num').value = numStr;
                document.getElementById('ped-comp').value = compStr;
            }

            document.getElementById('modal-carrinho').classList.replace('hidden', 'flex');
        }

        function fecharCarrinho() { document.getElementById('modal-carrinho').classList.replace('flex', 'hidden'); }

        async function enviarPedidoNuvem(e) {
            e.preventDefault();
            const btn = document.getElementById('btn-enviar-pedido'); const txtOriginal = btn.innerHTML;
            btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-2xl"></i>'; btn.disabled = true;

            let nome, tel, end, cliente_id, cpf;
            const radioEntrega = document.querySelector('input[name="tipo_entrega"]:checked');
            const isDelivery = radioEntrega ? radioEntrega.value === 'entrega' : false;
            
            const selBairro = document.getElementById('ped-bairro');
            const nomeBairro = (isDelivery && selBairro && selBairro.value !== "0") ? selBairro.options[selBairro.selectedIndex].text : "";

           // 🚨 Lógica Unificada de Endereço (Corrigida)
            let endLimpo = "";
            if (isDelivery) {
                const cep = document.getElementById('ped-cep').value;
                const rua = document.getElementById('ped-rua').value;
                const num = document.getElementById('ped-num').value;
                const comp = document.getElementById('ped-comp').value;
                
                if (!rua || !num) {
                    alertaPremium("⚠️ Preencha a Rua e o Número do endereço para a entrega.", "Atenção", "erro");
                    btn.innerHTML = txtOriginal; btn.disabled = false; return;
                }
                
                // Formatação limpa que o Ponto de Venda/Motoboy consegue ler:
                endLimpo = `${rua}, ${num}`;
                if (comp) endLimpo += ` (${comp})`;
            } else {
                endLimpo = "Retirada Balcão";
            }

            if (clienteLogado) {
                nome = clienteLogado.nome; 
                tel = clienteLogado.telefone; 
                // 🚨 O PULO DO GATO: Se for delivery, usa o que tá na tela. Se for balcão, ignora.
                end = isDelivery ? endLimpo : "Retirada Balcão"; 
                cliente_id = clienteLogado.id; 
                cpf = document.getElementById('logado-cpf').value.replace(/\D/g, ''); 
            } else {
// ... resto do seu código igual
                nome = document.getElementById('guest-nome').value.trim(); 
                tel = document.getElementById('guest-tel').value.trim();
                end = endLimpo;
                cpf = document.getElementById('guest-cpf').value.replace(/\D/g, ''); 
                cliente_id = null;
                if (!nome || !tel) { alertaPremium("⚠️ Preencha seu Nome e WhatsApp.", "Atenção", "erro"); btn.innerHTML=txtOriginal; btn.disabled=false; return; }
            }

            if (isDelivery && taxasEntrega.length > 0 && (!selBairro || selBairro.value === "0")) { alertaPremium("⚠️ Por favor, selecione o seu bairro de entrega na tabela.", "Atenção", "erro"); btn.innerHTML=txtOriginal; btn.disabled=false; return; }
            if (isDelivery && nomeBairro) end += ` (Bairro: ${nomeBairro} - Taxa R$ ${valorFreteAtual.toFixed(2)})`;

            const tipoPgto = document.getElementById('forma-pag-online').value;
            if ((tipoPgto === 'pix' || tipoPgto === 'credito') && !cpf) {
                alertaPremium("⚠️ O CPF é obrigatório para garantir o seu pagamento online via Pix ou Cartão.", "Atenção", "erro");
                if(clienteLogado) document.getElementById('logado-cpf').focus(); else document.getElementById('guest-cpf').focus();
                btn.innerHTML=txtOriginal; btn.disabled=false; return;
            }

            let itensFinais = carrinho.map(i => ({ 
                produto_id: i.produto_id, 
                quantidade: i.quantidade, 
                observacao: i.observacao || "" 
            }));
            if(cupomAplicado) itensFinais[0].observacao += ` | 🎫 Cupom Usado: ${cupomAplicado} (-R$ ${valorDescontoCupom.toFixed(2)})`;

            const descontoFinalEnviado = valorDescontoCupom - valorFreteAtual;

            const payload = { 
                cliente_id: cliente_id, 
                nome_cliente: nome, 
                telefone_cliente: tel, 
                endereco_cliente: end, 
                cpf: cpf, 
                itens: itensFinais, 
                usar_saldo_cashback: descontoFinalEnviado 
            };

            if (tipoPgto === 'credito') {
                const numCartao = document.getElementById('cc-num').value.replace(/\D/g, ''); const nomeCartao = document.getElementById('cc-nome').value;
                const valCartao = document.getElementById('cc-val').value; const cvvCartao = document.getElementById('cc-cvv').value;

                if(!numCartao || !nomeCartao || !valCartao || !cvvCartao) { alertaPremium("⚠️ Preencha todos os dados do cartão de crédito!", "Atenção", "erro"); btn.disabled = false; btn.innerHTML = txtOriginal; return; }

                try {
                    const mp = new MercadoPago('APP_USR-848cf42a-5349-4310-9ba5-b8c42f1ee022'); 
                    const metodos = await mp.getPaymentMethods({ bin: numCartao.substring(0, 6) });
                    if(metodos.results.length === 0) throw new Error();
                    
                    const tokenRes = await mp.createCardToken({
                        cardNumber: numCartao, cardholderName: nomeCartao, cardExpirationMonth: valCartao.split('/')[0],
                        cardExpirationYear: valCartao.split('/')[1].length === 2 ? "20" + valCartao.split('/')[1] : valCartao.split('/')[1],
                        securityCode: cvvCartao, identificationType: "CPF", identificationNumber: cpf.replace(/\D/g, '')
                    });

                    if(tokenRes.error) throw new Error();
                    payload.token_cartao = tokenRes.id; payload.payment_method_id = metodos.results[0].id; payload.parcelas = document.getElementById('cc-parcelas').value;
                } catch (e) { alertaPremium("⚠️ Dados do cartão de crédito inválidos.", "Erro", "erro"); btn.disabled = false; btn.innerHTML = txtOriginal; return; }
            }

            try {
                const res = await fetch(`/api/pedidos/online?forma_pagamento=${tipoPgto}`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify(payload) 
                });
                
                if (res.ok) {
                    let data = {};
                    try { data = await res.json(); } catch(jsonErr) {}

                    const numPed = data.senha_diaria || data.pedido_id || data.id || "000";

                    if (data.status === "checkout_transparente") { 
                        // ABRE O NOVO MODAL DE PIX!
                        document.getElementById('pix-pedido-num').innerText = numPed;
                        document.getElementById('pix-codigo-texto').innerText = data.copia_e_cola;
                        document.getElementById('modal-pix').classList.replace('hidden', 'flex');
                    } 
                    else { 
                        // MENSAGEM CUSTOMIZADA COM O NÚMERO DO PEDIDO PARA O CLIENTE
                        const txtSucesso = tipoPgto === 'credito' ? 
                            `O Pagamento foi aprovado!\nSeu pedido #${numPed} já foi para a cozinha. Acompanhe a entrega na tela de Rastreio.` : 
                            `Seu pedido #${numPed} foi recebido pela cozinha com sucesso!\nAcompanhe o preparo pela tela de Rastreio.`;
                        
                        alertaPremium(txtSucesso, "Pedido Confirmado! 🎉", "sucesso", () => {
                            window.location.reload();
                        });
                    }
                } else { 
                    let errData = {};
                    try { errData = await res.json(); } catch(e) {}
                    let mensagemErro = errData.detail || "Verifique os dados preenchidos.";
                    alertaPremium("Pedido recusado:\n" + mensagemErro, "Falha na Transação", "erro"); 
                    btn.disabled = false; btn.innerHTML = txtOriginal; 
                }
            } catch(e) { 
                alertaPremium("Ocorreu um erro de rede. Se o pedido descontou, avise a loja no WhatsApp.", "Erro", "erro"); 
                btn.disabled = false; btn.innerHTML = txtOriginal; 
            }
        }

        // 🚨 1. RESTAURA O MODAL DO PERFIL E HISTÓRICO DE PEDIDOS 🚨
        async function abrirModalPerfil() {
            const nomeSeguro = clienteLogado.nome || "Visitante";
            document.getElementById('vip-nome').innerText = nomeSeguro;
            document.getElementById('vip-tel').innerText = clienteLogado.telefone || "";
            if (clienteLogado.foto && clienteLogado.foto.trim() !== "") {
                document.getElementById('vip-foto').src = clienteLogado.foto;
                document.getElementById('vip-foto').classList.remove('hidden');
                document.getElementById('vip-iniciais').classList.add('hidden');
            } else {
                document.getElementById('vip-foto').classList.add('hidden');
                document.getElementById('vip-iniciais').innerText = nomeSeguro.substring(0, 2).toUpperCase();
                document.getElementById('vip-iniciais').classList.remove('hidden');
            }
            document.getElementById('vip-pontos').innerText = clienteLogado.pontos || 0;
            const cashbackVal = parseFloat(clienteLogado.cashback) || 0;
            document.getElementById('vip-cashback').innerText = "R$ " + cashbackVal.toFixed(2).replace('.', ',');
            
            const listaHistorico = document.getElementById('lista-historico');
            listaHistorico.innerHTML = '<p class="text-center text-slate-500 text-sm py-4"><i class="ph-bold ph-spinner animate-spin text-2xl"></i></p>';
            document.getElementById('modal-perfil').classList.remove('hidden');
            document.getElementById('modal-perfil').classList.add('flex');

            try {
                const res = await fetch(`/api/cliente/${clienteLogado.id}/pedidos`);
                const historico = await res.json();
                if(historico.length === 0) {
                    listaHistorico.innerHTML = '<p class="text-center text-slate-500 text-sm py-4">Você ainda não fez nenhum pedido.</p>';
                    return;
                }
                listaHistorico.innerHTML = historico.map(p => {
                    const statusCores = { "RECEBIDO": "bg-slate-100", "EM_PREPARO": "bg-amber-50", "PRONTO": "bg-blue-50", "SAIU_PARA_ENTREGA": "bg-purple-50", "ENTREGUE": "bg-emerald-50", "CANCELADO": "bg-red-50" };
                    const cor = statusCores[p.status] || "bg-slate-100";
                    return `<div class="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm mb-3">
                                <div class="flex justify-between items-center mb-3">
                                    <span class="font-black text-sm text-slate-800 dark:text-white">Pedido #${p.id}</span>
                                    <span class="text-[9px] font-black px-2 py-1 border rounded uppercase ${cor} text-slate-700">${p.status.replace(/_/g, ' ')}</span>
                                </div>
                                <p class="font-black text-brand-500 text-sm">R$ ${p.total.toFixed(2).replace('.', ',')}</p>
                            </div>`;
                }).join('');
            } catch(e) { listaHistorico.innerHTML = '<p class="text-center text-red-500 text-sm py-4">Erro ao carregar histórico.</p>'; }
        }

        // ==============================================================
        // 🚨 MOTORES DE BUSCA DE CEP (TOLERANTE A FALHAS) 🚨
        // ==============================================================
        
        // 1. Busca de CEP para o Carrinho
        window.buscarCepCheckout = async function(cep) {
            const cepLimpo = cep.replace(/\D/g, '');
            if (cepLimpo.length === 8) {
                const ruaField = document.getElementById('ped-rua');
                const numField = document.getElementById('ped-num');
                const valorAntigo = ruaField.value; // Salva pra não apagar!
                
                ruaField.value = "Buscando...";
                try {
                    const res = await fetch(`https://viacep.com.br/ws/${cepLimpo}/json/`);
                    const data = await res.json();
                    if (!data.erro) {
                        ruaField.value = `${data.logradouro}, ${data.bairro}`;
                        if(numField) numField.focus(); 
                    } else {
                        ruaField.value = valorAntigo; // Devolve o que estava escrito
                        alertaPremium("CEP não encontrado. Pode digitar a rua manualmente.", "Aviso", "info");
                    }
                } catch(e) { ruaField.value = valorAntigo; }
            }
        };

        // 2. Busca de CEP para Perfil e Cadastro
        window.buscarCep = async function(cep, tipo) {
            const cepLimpo = cep.replace(/\D/g, '');
            if (cepLimpo.length === 8) {
                let ruaField, bairroField, numField;

                if (tipo === 'edit') {
                    ruaField = document.getElementById('edit-perf-end');
                    numField = document.getElementById('edit-perf-num');
                } else if (tipo === 'reg') {
                    ruaField = document.getElementById('cad-rua');
                    bairroField = document.getElementById('cad-bairro');
                    numField = document.getElementById('cad-num');
                }

                const valorAntigo = ruaField ? ruaField.value : "";
                if (ruaField) ruaField.value = "Buscando...";

                try {
                    const res = await fetch(`https://viacep.com.br/ws/${cepLimpo}/json/`);
                    const data = await res.json();
                    
                    if (!data.erro) {
                        if (tipo === 'edit') {
                            ruaField.value = `${data.logradouro}, ${data.bairro}`;
                        } else if (tipo === 'reg') {
                            ruaField.value = data.logradouro;
                            if (bairroField) bairroField.value = data.bairro;
                        }
                        if (numField) numField.focus(); 
                    } else {
                        if (ruaField) ruaField.value = valorAntigo; // Devolve o que estava escrito
                        alertaPremium("CEP não encontrado nos Correios. Pode digitar manualmente.", "Aviso", "info");
                    }
                } catch(e) { 
                    if (ruaField) ruaField.value = valorAntigo; 
                }
            }
        };
    </script>
</body>
</html>


        # ==========================================
# MOTOR UNIVERSAL DE GESTÃO (CRUD FASE 4)
# ==========================================

# MUDANÇA: Definição única e absoluta do CupomModel aqui para evitar conflitos!
# Gerador automático para cupons sem validade preenchida no front-end
def data_infinita_str():
    from datetime import datetime, timedelta
    return (datetime.utcnow() + timedelta(days=3650)).strftime("%Y-%m-%dT%H:%M")

class CupomModel(Base):
    __tablename__ = "cupons_desconto"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True)
    tipo = Column(String, default="PERCENTUAL") 
    valor = Column(Float, default=0.0)
    desconto_percentual = Column(Float, default=0.0)
    desconto_fixo = Column(Float, default=0.0)
    # BLINDAGEM: Se a data não vier do HTML, ele insere 10 anos automaticamente
    data_validade = Column(String, default=data_infinita_str, nullable=True) 
    ativo = Column(Boolean, default=True)


def pegar_modelo_banco(tabela: str):
    # Traduz o nome da URL para a tabela real do banco
    if tabela == "insumos": return InsumoModel
    if tabela == "fornecedores": return FornecedorModel
    if tabela == "financeiro": return ContaPagarModel
    if tabela == "funcionarios": return FuncionarioModel
    if tabela == "cupons": return CupomModel
    if tabela == "clientes": return ClienteModel # <-- ADICIONE ESTA LINHA
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
        
        # --- 🚨 BLINDAGEM MÁXIMA PARA EXCLUSÃO DE CLIENTES 🚨 ---
        if tabela == "clientes":
            # 1. Desvincula os pedidos do cliente (Não apaga as vendas da loja, só remove o dono)
            db.query(PedidoModel).filter(PedidoModel.cliente_id == item_id).update({"cliente_id": None})
            # 2. Apaga a carteira de fidelidade (A causa raiz do Erro 500)
            from sqlalchemy import text
            db.execute(text("DELETE FROM fidelidade_pontos WHERE cliente_id = :id"), {"id": item_id})
        # --------------------------------------------------------
        
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
    try:
        cliente = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
        if not cliente: 
            raise HTTPException(status_code=404)
            
        # 1. Desvincula todos os pedidos (mantém o financeiro da loja intacto, mas anônimo)
        pedidos = db.query(PedidoModel).filter(PedidoModel.cliente_id == cliente_id).all()
        for p in pedidos:
            p.cliente_id = None
            
        # 2. O SEGREDO: Destrói a carteira de fidelidade amarrada ao cliente (Resolve o Erro 500!)
        from sqlalchemy import text
        db.execute(text("DELETE FROM fidelidade_pontos WHERE cliente_id = :id"), {"id": cliente_id})
        
        # 3. Agora sim, apaga o cliente com segurança
        db.delete(cliente)
        db.commit()
        return {"status": "sucesso"}
        
    except Exception as e:
        db.rollback()
        print(f"Erro Crítico ao deletar cliente: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


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
        # A Ordem de Exclusão é a lei sagrada dos Bancos de Dados!
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
    try:
        from financeiro import FornecedorModel 
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

# 2. Excluir Fornecedor
@app.delete("/api/fornecedores/{fornecedor_id}")
def excluir_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    try:
        from financeiro import FornecedorModel
        fornecedor = db.query(FornecedorModel).filter(FornecedorModel.id == fornecedor_id).first()
        if not fornecedor:
            raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
            
        db.delete(fornecedor)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        # 🚨 Identifica se o erro é por causa de contas vinculadas
        if "IntegrityError" in str(type(e)) or "Foreign Key" in str(e):
            raise HTTPException(status_code=400, detail="Não é possível excluir: existem contas a pagar vinculadas a este fornecedor.")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

# 3. Atualizar Conta a Pagar
@app.put("/api/contas_pagar/{conta_id}")
def atualizar_conta(conta_id: int, dados: dict, db: Session = Depends(get_db)):
    try:
        from financeiro import ContaPagarModel 
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

# 4. Excluir Conta a Pagar
@app.delete("/api/contas_pagar/{conta_id}")
def excluir_conta(conta_id: int, db: Session = Depends(get_db)):
    try:
        from financeiro import ContaPagarModel
        conta = db.query(ContaPagarModel).filter(ContaPagarModel.id == conta_id).first()
        if not conta:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
            
        db.delete(conta)
        db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MOTOR DE EDIÇÃO E EXCLUSÃO (FASE 2)
# ==========================================

# 🚨 NOVA ROTA: Busca os ingredientes atuais do lanche para mostrar na tela de edição
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

# 6. Atualizar Colaborador (Nome, Matrícula, Senha e Cargo)
@app.put("/api/gestao/funcionarios/{func_id}")
def atualizar_funcionario_basico(func_id: int, dados: dict, db: Session = Depends(get_db)):
    func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
    if not func:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
        
    if 'nome' in dados and dados['nome']: 
        func.nome = dados['nome']
    if 'matricula' in dados: 
        func.matricula_cracha = dados['matricula']
        
    # --- Atualização Blindada do Cargo ---
    if 'cargo_id' in dados and dados['cargo_id'] is not None:
        try:
            func.cargo_id = int(dados['cargo_id'])
        except ValueError:
            pass
        
    # --- Suporte para resetar a senha ---
    if 'senha' in dados and dados['senha'] and dados['senha'].strip() != "":
        func.senha_hash = pwd_context.hash(dados['senha'].strip())
        
    db.commit()
    db.refresh(func)
    return {"status": "sucesso", "mensagem": "Colaborador atualizado!"}

# 7. Exclusão Definitiva do Colaborador do Banco de Dados
@app.delete("/api/gestao/funcionarios/{func_id}/excluir")
def excluir_funcionario_definitivo(func_id: int, db: Session = Depends(get_db)):
    try:
        func = db.query(FuncionarioModel).filter(FuncionarioModel.id == func_id).first()
        if not func: 
            raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
            
        # Apaga os vínculos para evitar erro 500 no banco de dados
        db.query(InfoRHModel).filter(InfoRHModel.funcionario_id == func_id).delete()
        db.query(PontoModel).filter(PontoModel.funcionario_id == func_id).delete()
        db.query(OcorrenciaRHModel).filter(OcorrenciaRHModel.funcionario_id == func_id).delete()
        db.query(SolicitacaoFeriasModel).filter(SolicitacaoFeriasModel.funcionario_id == func_id).delete()
        
        # Apaga o funcionário
        db.delete(func)
        db.commit()
        return {"status": "sucesso", "mensagem": "Funcionário apagado do sistema."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MÁQUINA DE VENDAS: CUPONS E PROMOÇÕES
# ==========================================

@app.get("/api/gestao/cupons")
def listar_cupons(db: Session = Depends(get_db)):
    return db.query(CupomModel).all()

@app.post("/api/gestao/cupons")
def criar_cupom(dados: dict, db: Session = Depends(get_db)):
    codigo = str(dados.get("codigo", "")).upper().strip()
    if not codigo:
        raise HTTPException(status_code=400, detail="O código do cupom é obrigatório.")
        
    existe = db.query(CupomModel).filter(CupomModel.codigo == codigo).first()
    if existe:
        raise HTTPException(status_code=400, detail="Este código de cupom já existe.")
        
    tipo_cupom = dados.get("tipo", "PERCENTUAL")
    val_cupom = float(dados.get("valor", 0.0))
    
    from datetime import datetime, timedelta
    
    novo = CupomModel(
        codigo=codigo,
        tipo=tipo_cupom,
        valor=val_cupom,
        desconto_percentual=val_cupom if tipo_cupom == "PERCENTUAL" else 0.0,
        desconto_fixo=val_cupom if tipo_cupom == "VALOR_FIXO" else 0.0,
        ativo=True,
        data_validade=datetime.utcnow() + timedelta(days=365) # Preenche a validade exigida pelo PostgreSQL
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
    
    # 🚨 CORREÇÃO 3: Só atualiza o bairro se ele vier preenchido
    if hasattr(c, 'bairro') and dados.bairro: c.bairro = dados.bairro
    
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

# ==========================================
# 1. ROTA DE RASTREIO 100% BLINDADA
# ==========================================
@app.get("/api/rastreio/{busca}")
def rastrear_pedido_cliente(busca: str, db: Session = Depends(get_db)):
    try:
        # Extrai apenas os números da busca
        busca_limpa = "".join(filter(str.isdigit, busca))
        pedido = None
        
        if busca_limpa:
            num = int(busca_limpa)
            pedido = db.query(PedidoModel).filter(PedidoModel.id == num).first()
        
        # Se não achou pelo ID, tenta pelo telefone
        if not pedido:
            telefone = busca.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("+", "")
            pedido = db.query(PedidoModel).filter(PedidoModel.telefone_cliente == telefone).order_by(desc(PedidoModel.id)).first()
            
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
            
        status_raw = str(getattr(pedido, 'status', 'RECEBIDO')).upper()
        status_atual = status_raw.split('.')[-1]
        
        progresso = 20
        if status_atual in ["EM_PREPARO", "PREPARANDO"]: progresso = 50
        elif status_atual in ["PRONTO", "SAIU_PARA_ENTREGA"]: progresso = 80
        elif status_atual in ["ENTREGUE", "FINALIZADO"]: progresso = 100
        elif status_atual == "CANCELADO": progresso = 0
        
        # Converte valores financeiros com segurança contra vírgulas ou textos nulos
        val_total = 0.0
        for col in ['total_pago', 'valor_total', 'total', 'valor']:
            val = getattr(pedido, col, None)
            if val is not None:
                try:
                    val_total = float(str(val).replace(',', '.'))
                    break
                except ValueError:
                    pass
                
        return {
            "id": pedido.id,
            "senha": pedido.id,
            "status": status_atual,
            "progresso": progresso,
            "tipo": "BALCAO",
            "total": val_total
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Erro no Rastreio: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no servidor")

# ==========================================
# MÓDULO DE LOGÍSTICA (TAXAS DE ENTREGA)
# ==========================================
class TaxaEntregaSchema(BaseModel):
    bairro: str
    taxa: float

@app.get("/api/taxas/listar")
def listar_taxas(db: Session = Depends(get_db)):
    from database import TaxaEntregaModel 
    try:
        return db.query(TaxaEntregaModel).order_by(TaxaEntregaModel.bairro.asc()).all()
    except Exception as e:
        print(f"Erro ao listar taxas: {e}")
        return []

@app.post("/api/taxas/salvar")
def criar_taxa(dados: TaxaEntregaSchema, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    from database import TaxaEntregaModel
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
        raise HTTPException(status_code=400, detail=f"Erro no banco DB: {str(e)}")

@app.delete("/api/taxas/{id}")
def deletar_taxa(id: int, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    from database import TaxaEntregaModel
    try:
        tx = db.query(TaxaEntregaModel).filter(TaxaEntregaModel.id == id).first()
        if tx:
            db.delete(tx)
            db.commit()
        return {"status": "sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro DB: {str(e)}")

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
                "src": "https://raw.githubusercontent.com/artsburguergerencia-hash/arts-burguer/main/static/img/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "https://raw.githubusercontent.com/artsburguergerencia-hash/arts-burguer/main/static/img/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any"
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

@app.get("/api/resgate-admin")
def resgate_admin(db: Session = Depends(get_db)):
    try:
        # 1. Garante que o cargo Administrador existe e tem permissão total
        cargo_admin = db.query(Cargo).filter(Cargo.nome == "Administrador").first()
        if not cargo_admin:
            cargo_admin = Cargo(nome="Administrador", permissoes="total")
            db.add(cargo_admin)
            db.commit()
            db.refresh(cargo_admin)
        else:
            cargo_admin.permissoes = "total"
            db.commit()

        # 2. Força a recriação ou atualização da senha do 'admin'
        admin = db.query(FuncionarioModel).filter(FuncionarioModel.usuario == "admin").first()
        if not admin:
            import random
            admin = FuncionarioModel(
                nome="Admin de Resgate", 
                usuario="admin", 
                senha_hash=pwd_context.hash("admin123"), 
                cargo_id=cargo_admin.id,
                # Usa matrícula aleatória para NUNCA dar erro de duplicidade
                matricula_cracha=f"RESG-{random.randint(1000, 9999)}" 
            )
            db.add(admin)
        else:
            # Se o admin já existe, apenas força a senha de volta e garante o cargo
            admin.senha_hash = pwd_context.hash("admin123")
            admin.cargo_id = cargo_admin.id
            
        db.commit()
        return {"mensagem": "Acesso de resgate liberado! Use usuário: admin | senha: admin123"}
        
    except Exception as e:
        db.rollback()
        # Se falhar, agora ele vai mostrar EXATAMENTE o que deu errado na tela
        return {"erro_critico": str(e), "dica": "Copie esse erro e me envie para correção"}

@app.get("/api/master-key", response_class=HTMLResponse)
def master_key_access(db: Session = Depends(get_db)):
    try:
        # 1. Garante que o cargo Administrador existe e tem poder total
        cargo_admin = db.query(Cargo).filter(Cargo.nome == "Administrador").first()
        if not cargo_admin:
            cargo_admin = Cargo(nome="Administrador", permissoes="total")
            db.add(cargo_admin)
            db.commit()
            db.refresh(cargo_admin)
        else:
            cargo_admin.permissoes = "total"
            db.commit()

        # 2. Garante que o usuário 'admin' existe com a senha 'admin123'
        admin = db.query(FuncionarioModel).filter(FuncionarioModel.usuario == "admin").first()
        if not admin:
            import random
            admin = FuncionarioModel(
                nome="Admin Supremo", 
                usuario="admin", 
                senha_hash=pwd_context.hash("admin123"), 
                cargo_id=cargo_admin.id,
                matricula_cracha=f"SUP-{random.randint(1000, 9999)}" 
            )
            db.add(admin)
            db.commit()
        else:
            admin.senha_hash = pwd_context.hash("admin123")
            admin.cargo_id = cargo_admin.id
            db.commit()

        # 3. O PULO DO GATO: Injeta a permissão direto no navegador e te joga pra Gestão
        html_content = f"""
        <!DOCTYPE html>
        <html>
            <head><title>Autorizando...</title></head>
            <body style="background: #0f172a; color: white; text-align: center; font-family: sans-serif; padding-top: 20%;">
                <h2>Destravando o sistema... Você será redirecionado! 🚀</h2>
                <script>
                    // Força o cache do navegador a aceitar que você é o dono (Cargo 1)
                    localStorage.setItem('funcionario_nome', '{admin.nome}');
                    localStorage.setItem('funcionario_cargo', '1');
                    
                    // Te teletransporta direto pra tela de gestão (ignorando o Hub)
                    setTimeout(() => {{
                        window.location.replace('/gestao');
                    }}, 1500);
                </script>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        db.rollback()
        return HTMLResponse(content=f"<h2 style='color:red;'>Erro ao usar a chave mestra: {str(e)}</h2>")

@app.get("/api/cura-fornecedor")
def cura_fornecedor(db: Session = Depends(get_db)):
    from sqlalchemy import text
    logs = []
    
    # Tenta criar a coluna contato
    try:
        db.execute(text("ALTER TABLE fornecedores ADD COLUMN contato VARCHAR DEFAULT '';"))
        db.commit()
        logs.append("Coluna 'contato' injetada com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Contato ignorado: {str(e)}")

    # Tenta criar a coluna telefone
    try:
        db.execute(text("ALTER TABLE fornecedores ADD COLUMN telefone VARCHAR DEFAULT '';"))
        db.commit()
        logs.append("Coluna 'telefone' injetada com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Telefone ignorado: {str(e)}")

    return {"status": "Operação Concluída!", "detalhes": logs}

@app.get("/api/cura-produtos")
def cura_produtos(db: Session = Depends(get_db)):
    from sqlalchemy import text
    logs = []
    
    # 1. Converte a coluna 'ativo' de Número para Boolean
    try:
        db.execute(text("ALTER TABLE produtos ALTER COLUMN ativo DROP DEFAULT;"))
        db.execute(text("ALTER TABLE produtos ALTER COLUMN ativo TYPE boolean USING (ativo != 0);"))
        db.execute(text("ALTER TABLE produtos ALTER COLUMN ativo SET DEFAULT TRUE;"))
        db.commit()
        logs.append("Coluna 'ativo' convertida para BOOLEAN com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Ativo ignorado (já deve estar correto): {str(e)}")

    # 2. Converte a coluna 'participa_fidelidade' de Número para Boolean
    try:
        db.execute(text("ALTER TABLE produtos ALTER COLUMN participa_fidelidade DROP DEFAULT;"))
        db.execute(text("ALTER TABLE produtos ALTER COLUMN participa_fidelidade TYPE boolean USING (participa_fidelidade != 0);"))
        db.execute(text("ALTER TABLE produtos ALTER COLUMN participa_fidelidade SET DEFAULT TRUE;"))
        db.commit()
        logs.append("Coluna 'participa_fidelidade' convertida para BOOLEAN com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Fidelidade ignorada (já deve estar correto): {str(e)}")

    return {"status": "Banco Consertado", "logs": logs}

@app.get("/api/cura-produtos-bruta")
def cura_produtos_bruta(db: Session = Depends(get_db)):
    from sqlalchemy import text
    logs = []
    
    # 1. Arranca a coluna velha e recria a 'ativo' perfeitamente como Boolean
    try:
        db.execute(text("ALTER TABLE produtos DROP COLUMN IF EXISTS ativo;"))
        db.execute(text("ALTER TABLE produtos ADD COLUMN ativo BOOLEAN DEFAULT TRUE;"))
        db.commit()
        logs.append("Coluna 'ativo' DESTRUÍDA e RECRIADA como BOOLEAN com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Erro no ativo: {str(e)}")

    # 2. Arranca a coluna velha e recria a 'participa_fidelidade' como Boolean
    try:
        db.execute(text("ALTER TABLE produtos DROP COLUMN IF EXISTS participa_fidelidade;"))
        db.execute(text("ALTER TABLE produtos ADD COLUMN participa_fidelidade BOOLEAN DEFAULT TRUE;"))
        db.commit()
        logs.append("Coluna 'participa_fidelidade' DESTRUÍDA e RECRIADA como BOOLEAN com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Erro na fidelidade: {str(e)}")

    return {"status": "Tabela de Produtos Consertada na Força Bruta!", "logs": logs}

@app.get("/api/cura-checkout")
def cura_checkout(db: Session = Depends(get_db)):
    from sqlalchemy import text
    logs = []
    
    # 1. Consertando os campos de Verdadeiro/Falso na tabela CLIENTES
    try:
        db.execute(text("ALTER TABLE clientes DROP COLUMN IF EXISTS bloqueado;"))
        db.execute(text("ALTER TABLE clientes ADD COLUMN bloqueado BOOLEAN DEFAULT FALSE;"))
        
        db.execute(text("ALTER TABLE clientes DROP COLUMN IF EXISTS permite_fiado;"))
        db.execute(text("ALTER TABLE clientes ADD COLUMN permite_fiado BOOLEAN DEFAULT FALSE;"))
        db.commit()
        logs.append("Tabela CLIENTES curada com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Erro em Clientes: {str(e)}")

    # 2. Consertando os campos de Verdadeiro/Falso na tabela CONFIGURAÇÕES
    try:
        db.execute(text("ALTER TABLE configuracoes_loja DROP COLUMN IF EXISTS aceita_delivery;"))
        db.execute(text("ALTER TABLE configuracoes_loja ADD COLUMN aceita_delivery BOOLEAN DEFAULT TRUE;"))
        
        db.execute(text("ALTER TABLE configuracoes_loja DROP COLUMN IF EXISTS aceita_retirada;"))
        db.execute(text("ALTER TABLE configuracoes_loja ADD COLUMN aceita_retirada BOOLEAN DEFAULT TRUE;"))
        
        db.execute(text("ALTER TABLE configuracoes_loja DROP COLUMN IF EXISTS aceite_automatico;"))
        db.execute(text("ALTER TABLE configuracoes_loja ADD COLUMN aceite_automatico BOOLEAN DEFAULT FALSE;"))
        db.commit()
        logs.append("Tabela CONFIGURACOES_LOJA curada com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Erro em Configurações: {str(e)}")

    # 3. Consertando os Cupons (Por precaução)
    try:
        db.execute(text("ALTER TABLE cupons_desconto DROP COLUMN IF EXISTS ativo;"))
        db.execute(text("ALTER TABLE cupons_desconto ADD COLUMN ativo BOOLEAN DEFAULT TRUE;"))
        db.commit()
        logs.append("Tabela CUPONS curada com sucesso!")
    except Exception as e:
        db.rollback()
        logs.append(f"Erro em Cupons: {str(e)}")

    return {"status": "Vacina do Checkout Aplicada!", "logs": logs}
    
 # =======================================================
# ROTAS DE CONEXÃO: TV E LOGÍSTICA (À PROVA DE FALHAS)
# =======================================================

@app.get("/api/tv/pedidos")
def obter_pedidos_tv(db: Session = Depends(get_db)):
    """ Rota exclusiva para alimentar a tela da TV do Salão """
    try:
        pedidos = db.query(PedidoModel).all()
        em_preparo = []
        prontos = []
        for p in pedidos:
            st = str(p.status).upper()
            
            # 🚨 TRAVA DE DELIVERY REMOVIDA AQUI! AGORA TODOS APARECEM NA TV 🚨
            
            obj = {
                "id": p.id,
                "senha_diaria": getattr(p, 'senha_diaria', str(p.id).zfill(3)),
                "cliente_nome": p.cliente.nome if getattr(p, 'cliente', None) else "Cliente"
            }
            
            if "RECEBIDO" in st or "PREPAR" in st:
                em_preparo.append(obj)
            elif "PRONTO" in st:
                prontos.append(obj)
                
        return {"em_preparo": em_preparo, "prontos": prontos}
    except Exception: 
        return {"em_preparo": [], "prontos": []}


@app.get("/api/logistica/pedidos")
def obter_pedidos_logistica(db: Session = Depends(get_db)):
    """ Rota exclusiva para alimentar o Painel de Expedição e Logística """
    try:
        pedidos = db.query(PedidoModel).all()
        prontos = []
        em_rota = []
        for p in pedidos:
            st = str(p.status).upper()
            tipo = str(getattr(p, 'tipo_pedido', getattr(p, 'tipo', 'DELIVERY'))).upper()
            
            # Puxa apenas o que está saindo da cozinha ou na rua
            if "PRONTO" in st or "SAIU" in st or "ROTA" in st:
                obj = {
                    "id": p.id,
                    "senha_diaria": getattr(p, 'senha_diaria', str(p.id).zfill(3)),
                    "cliente": p.cliente.nome if getattr(p, 'cliente', None) else "Cliente",
                    "endereco": getattr(p, 'endereco', 'Retirada Balcão'),
                    "tipo": tipo
                }
                
                if "PRONTO" in st:
                    prontos.append(obj)
                else:
                    em_rota.append(obj)
                    
        return {"prontos": prontos, "em_rota": em_rota}
    except Exception: 
        return {"prontos": [], "em_rota": []}


@app.put("/api/logistica/pedidos/{pedido_id}/despachar")
def despachar_pedido(pedido_id: int, payload: dict, db: Session = Depends(get_db)):
    try:
        pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
        if pedido:
            pedido.status = "SAIU_PARA_ENTREGA"
            db.commit()
            senha = getattr(pedido, 'senha_diaria', pedido.id)
            if getattr(pedido, 'cliente', None):
                try:
                    notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha, "SAIU_PARA_ENTREGA")
                except: pass
        return {"ok": True}
    except Exception: 
        return {"ok": False}


@app.put("/api/logistica/pedidos/{pedido_id}/entregar")
def entregar_pedido(pedido_id: int, db: Session = Depends(get_db)):
    try:
        pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
        if pedido:
            pedido.status = "ENTREGUE"
            db.commit()
            senha = getattr(pedido, 'senha_diaria', pedido.id)
            if getattr(pedido, 'cliente', None):
                try:
                    notificar_status_pedido(pedido.cliente.telefone, pedido.cliente.nome, senha, "ENTREGUE")
                except: pass
        return {"ok": True}
    except Exception: 
        return {"ok": False}

# =======================================================
# 🚨 RESOLUÇÃO DO BUG DAS SENHAS DIÁRIAS (SUBSTITUA A SUA) 🚨
# =======================================================
def gerar_senha_diaria(db: Session):
    """
    Substitua a sua função antiga por esta. 
    Lê o último pedido de forma segura e reseta a senha para 001 à meia-noite.
    """
    from datetime import datetime
    hoje = datetime.utcnow().date()
    try:
        ultimo = db.query(PedidoModel).order_by(PedidoModel.id.desc()).first()
        if not ultimo: 
            return "001"
        
        # Procura onde o seu banco salvou a data
        data_ultimo = getattr(ultimo, 'data_pedido', None)
        if not data_ultimo:
            dh = getattr(ultimo, 'data_hora', None)
            if dh and hasattr(dh, 'date'): 
                data_ultimo = dh.date()
                
        if data_ultimo == hoje:
            try:
                # É de hoje, então soma 1 à senha anterior
                return str(int(ultimo.senha_diaria) + 1).zfill(3)
            except: 
                return str(ultimo.id + 1).zfill(3)
        else:
            # Não é de hoje (já é o dia seguinte), reseta para 001
            return "001"
    except Exception: 
        return "001"

# =======================================================
# ROTAS DO GPS E MOTOBOY (MAPA EM TEMPO REAL)
# =======================================================

from fastapi.responses import HTMLResponse, FileResponse
from fastapi import Request
import os

# Memória RAM temporária para guardar as coordenadas das motos ao vivo
# Estrutura: { 195: {"lat": -25.64, "lng": -49.31, "status": "online", "ultima_atualizacao": datetime} }
POSICOES_MOTOBOYS_AO_VIVO = {}

@app.get("/mapa", response_class=HTMLResponse)
def tela_rastreio_mapa(request: Request):
    """ Retorna a tela do mapa para o cliente acompanhar o motoboy """
    return FileResponse(os.path.join("templates", "mapa.html"))

@app.get("/motoboy", response_class=HTMLResponse)
def tela_app_motoboy(request: Request):
    """ Retorna a tela/app web para o motoboy transmitir o GPS """
    return FileResponse(os.path.join("templates", "motoboy.html"))

@app.post("/api/logistica/gps/{pedido_id}/atualizar")
def atualizar_posicao_motoboy(pedido_id: int, payload: dict):
    """ O app do motoboy manda a posição a cada 5 segundos pra cá """
    try:
        lat = payload.get("lat")
        lng = payload.get("lng")
        
        if lat and lng:
            from datetime import datetime
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
        
if __name__ == "__main__":
    print("🚀 Iniciando Servidor Web do Art's Burguer V5 (Google Cloud Edition)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
