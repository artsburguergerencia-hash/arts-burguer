# Usa uma versão leve do Python
FROM python:3.10-slim

# Define a pasta de trabalho dentro do contentor
WORKDIR /app

# Copia e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código (main.py, pastas templates, etc) para dentro do contentor
COPY . .

# Expõe a porta 8000 do FastAPI
EXPOSE 8000

# Comando para iniciar o servidor
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]