import os
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session
from database import SessionLocal, FuncionarioModel

# A chave mestra da criptografia. No Render, você deve criar uma variável de ambiente com este nome.
SECRET_KEY = os.getenv("SECRET_KEY", "chave_provisoria_arts_burguer_2024_trocar_depois")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # O Token expira em 24 horas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def criar_token_acesso(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def obter_usuario_logado(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão expirada ou credenciais inválidas. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Tenta abrir o token e ler o ID do usuário
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_str: str = payload.get("sub")
        cargo_id: int = payload.get("cargo_id")
        
        if usuario_str is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    # Vai no banco confirmar se o funcionário ainda existe (não foi demitido, por ex.)
    usuario = db.query(FuncionarioModel).filter(FuncionarioModel.usuario == usuario_str).first()
    if usuario is None or usuario.senha_hash == "REVOGADO":
        raise credentials_exception
        
    return {"usuario": usuario, "cargo_id": cargo_id}

def verificar_admin(usuario_logado: dict = Depends(obter_usuario_logado)):
    """Bloqueio VIP: Só passa se for cargo 1 (Admin)"""
    if usuario_logado["cargo_id"] != 1:
        raise HTTPException(status_code=403, detail="Acesso negado: Área restrita para a Diretoria.")
    return usuario_logado
