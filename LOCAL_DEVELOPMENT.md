# Desenvolvimento local

## Pré-requisitos

- Python compatível com as versões fixadas em `backend/requirements.txt`
- Node.js e Yarn 1.22
- MongoDB local ou MongoDB Atlas
- FFmpeg para exportação de áudio, vídeo e whiteboard

As integrações de IA, geração de mídia, conversão e e-mail são opcionais para
iniciar a aplicação, mas as funções correspondentes exigem suas próprias chaves.

O antigo pacote privado `emergentintegrations` foi substituído por uma camada
local compatível baseada em LiteLLM. Configure `OPENAI_API_KEY`,
`GEMINI_API_KEY` ou `ANTHROPIC_API_KEY` conforme o provedor usado.
`EMERGENT_LLM_KEY` continua disponível somente como fallback legado.

Uma assinatura do ChatGPT não inclui automaticamente uma chave da API. Crie
uma chave de projeto na plataforma do provedor e não a envie por chat.

No Windows, o assistente local grava a chave sem exibi-la no terminal:

```powershell
.\scripts\configure-local-secrets.ps1
```

O arquivo `backend/.env` fica apenas no computador e está ignorado pelo Git.
Em produção, não copie esse arquivo: use o gerenciador de segredos da
hospedagem do backend.

Uma única chave OpenAI habilita as funções que usam modelos OpenAI. O projeto
também possui funções específicas de Gemini e Anthropic; elas exigem suas
respectivas chaves ou uma futura padronização dos modelos.

## 1. Configurar o backend

No diretório `backend`, copie `.env.example` para `.env` e ajuste pelo menos:

```dotenv
MONGO_URL=mongodb://localhost:27017
DB_NAME=scormify
```

Depois crie o ambiente virtual e instale as dependências:

```bash
cd backend
python -m venv .venv
```

No Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

No Linux ou macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Verifique:

- `http://localhost:8001/health`: processo da API ativo
- `http://localhost:8001/ready`: API conectada ao MongoDB
- `http://localhost:8001/docs`: documentação interativa do FastAPI

## 2. Configurar o frontend

Em outro terminal, copie `frontend/.env.example` para `frontend/.env` e execute:

```bash
cd frontend
yarn install
yarn start
```

A interface ficará disponível em `http://localhost:3000`.

## 3. Testes e build

Frontend:

```bash
cd frontend
yarn test
yarn build
```

Backend:

```bash
cd backend
pytest
```

Parte da suíte do backend é composta por testes de integração que acessam uma API
ativa, MongoDB ou provedores externos. Execute primeiro testes unitários isolados
e configure as integrações antes de rodar a suíte completa.

## Cuidados

- Nunca inclua `.env`, chaves de API, tokens ou credenciais em commits.
- Use um banco separado para testes.
- Confirme compatibilidade SCORM no LMS de destino após mudanças no exportador.
- Exportação de vídeo e whiteboard pode consumir bastante CPU e memória.
- O backend de produção usa um worker e `timeout-keep-alive` de 300 segundos.
