# auth_security.py
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import SessionLocal, FuncionarioModel, Cargo

# Chave secreta de assinatura dos tokens (defina uma chave forte no Render)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "artsburguer_super_secret_production_key_2025_phd")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas de validade

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def criar_token_acesso(dados: dict, expira_em: Optional[timedelta] = None) -> str:
    """Gera um JWT assinado digitalmente."""
    to_encode = dados.copy()
    expiracao = datetime.utcnow() + (expira_em or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expiracao})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obter_usuario_logado(
    token: Optional[str] = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> FuncionarioModel:
    """Valida o token JWT e retorna o funcionário autenticado."""
    credenciais_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão expirada ou não autenticada. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credenciais_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id: int = payload.get("sub")
        if usuario_id is None:
            raise credenciais_exception
    except JWTError:
        raise credenciais_exception

    funcionario = db.query(FuncionarioModel).filter(FuncionarioModel.id == usuario_id).first()
    if not funcionario:
        raise credenciais_exception
    return funcionario

def exigir_administrador(
    funcionario: FuncionarioModel = Depends(obter_usuario_logado),
    db: Session = Depends(get_db)
) -> FuncionarioModel:
    """Garante que a rota só pode ser acessada por quem tem permissão total (Admin)."""
    cargo = db.query(Cargo).filter(Cargo.id == funcionario.cargo_id).first()
    
    # Validação pelo cargo e pela permissão do banco
    eh_admin = (cargo and cargo.permissoes == "total") or funcionario.usuario == "admin"
    if not eh_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Negado: Apenas Administradores possuem autorização para esta operação."
        )
    return funcionario
