# 🛠️ Guia de Setup — Teste End-to-End com WhatsApp Real

Este guia transforma a PoC em um sistema funcional onde você envia uma mensagem pelo seu celular e recebe uma resposta gerada por IA. Todo o processo é **100% gratuito** para fins de teste.

---

## 💰 Sobre Custos

A Meta oferece um ambiente de sandbox gratuito para desenvolvedores:

| Cenário | Custo |
|---|---|
| Desenvolvimento e testes com número sandbox | **Gratuito** |
| Token de acesso temporário (válido por 24h) | **Gratuito** |
| Produção com número real (primeiras 1.000 conversas/mês) | **Gratuito** |
| Produção acima de 1.000 conversas/mês | Cobrado por conversa (janela de 24h) |

> ⚠️ **Limitações do sandbox**: apenas números explicitamente autorizados no painel da Meta podem conversar com o número de teste. O token temporário expira em 24h — veja como criar um token permanente na seção de troubleshooting.

---

## Fase 1: Configuração na Meta Developer

### 1.1 Criar conta e app

1. Acesse [developers.facebook.com](https://developers.facebook.com/) e crie uma conta de desenvolvedor (gratuito).
2. No painel, clique em **Meus Apps → Criar App**.
3. Escolha o tipo **Empresa** (`Business`) e conclua o fluxo.

### 1.2 Ativar o WhatsApp e obter os tokens

1. Na barra lateral do app, clique em **WhatsApp → Configurar** (`Set up`).
2. Acesse **Configuração da API** (`API Setup`).
3. Anote os seguintes valores — você vai precisar deles no `.env`:

| Campo no painel | Variável no `.env` |
|---|---|
| Token de acesso temporário | `META_ACCESS_TOKEN` |
| ID do número de telefone de teste | `META_PHONE_NUMBER_ID` |
| Segredo do App (em Configurações Básicas) | `META_APP_SECRET` |

4. Na seção **Números de telefone de teste**, clique em **Adicionar número de telefone** e cadastre o seu número pessoal do WhatsApp. Confirme via SMS.

> 📌 O número de telefone de teste é o número do **sistema** (ex: +1 555 000 0000). Você vai enviar mensagens *para* ele pelo seu celular pessoal.

---

## Fase 2: Ambiente Local

### 2.1 Preencher o `.env`

```bash
cp .env.example .env
```

Edite o `.env` com os valores obtidos na Fase 1:

```ini
# Token que VOCÊ cria (qualquer string segura)
META_VERIFY_TOKEN=meu_token_unico_123

# Obtido no painel da Meta (expira em 24h — veja como renovar abaixo)
META_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxx

# ID numérico do número de teste (ex: 123456789012345)
META_PHONE_NUMBER_ID=123456789012345

# Segredo do app (em Configurações Básicas do app na Meta)
META_APP_SECRET=abc123def456

# Sua chave da OpenAI
OPENAI_API_KEY=sk-proj-xxxxxxxx

# Não altere — usados pelo docker-compose
REDIS_URL=redis://redis:6379
DOCS_PATH=data/docs
CHROMA_PATH=data/chroma_db
```

### 2.2 Alimentar a base RAG (opcional mas recomendado)

Coloque arquivos `.txt` ou `.md` na pasta `data/docs/` (já existem dois exemplos).

Rode a ingestão uma vez:

```bash
docker-compose run --rm api python -c "from app.rag import ingest_documents; ingest_documents()"
```

### 2.3 Subir o sistema

```bash
docker-compose up --build
```

Aguarde até ver nos logs:
```
whatsapp_webhook_api  | INFO:     Application startup complete.
whatsapp_rag_worker   | [worker] Worker iniciado. Aguardando mensagens na fila...
```

---

## Fase 3: Expor o Servidor com Ngrok

### 3.1 Instalar e autenticar

```bash
# macOS
brew install ngrok

# Linux
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc \
  && echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list \
  && sudo apt update && sudo apt install ngrok
```

Configure o authtoken (obtido em [dashboard.ngrok.com](https://dashboard.ngrok.com/)):

```bash
ngrok config add-authtoken SEU_AUTHTOKEN
```

### 3.2 Criar o túnel

Em um **novo terminal** (com o docker-compose ainda rodando):

```bash
ngrok http 8000
```

Anote a URL pública gerada — algo como:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

> ⚠️ **A URL do ngrok muda a cada reinício.** No plano gratuito, você precisa atualizar o webhook no painel da Meta sempre que reiniciar o ngrok.

---

## Fase 4: Registrar o Webhook na Meta

1. No painel da Meta, vá em **WhatsApp → Configuração → Configuração do Webhook**.
2. Clique em **Editar** e preencha:
   - **URL de callback**: `https://abc123.ngrok-free.app/webhook`
   - **Token de verificação**: o mesmo `META_VERIFY_TOKEN` do seu `.env`
3. Clique em **Verificar e salvar**.
   - ✅ Se a verificação passar, significa que seu servidor está rodando e respondeu corretamente ao challenge da Meta.

4. Após salvar, clique em **Gerenciar** na seção **Campos Webhook** e ative o campo **`messages`**.
   - Sem isso, você recebe notificações de status (entregue, lido) mas **não as mensagens de texto**.

---

## Fase 5: Teste Final

1. No seu celular, abra o WhatsApp e inicie uma conversa com o **número de teste da Meta** (não o seu número pessoal).
2. Envie uma mensagem de texto — por exemplo: _"Qual a taxa de juros do crédito rotativo?"_
3. Em segundos, você deve receber uma resposta baseada nos documentos da pasta `data/docs/`.

**Fluxo completo no terminal:**
```
[webhook] POST /webhook recebido de 5511999999999
[broker]  Mensagem wamid.abc publicada na fila 'whatsapp:messages'
[worker]  Processando msg wamid.abc de 5511999999999
[rag]     Chunk recuperado de 'faq_credito.txt' (chunk 2)
[rag]     Chunk recuperado de 'faq_credito.txt' (chunk 4)
[worker]  Resposta gerada: A taxa de juros do crédito rotativo é de 12,5% ao mês...
[whatsapp] Mensagem enviada para 5511999999999 — status 200
```

---

## 🔧 Troubleshooting

| Problema | Causa Provável | Solução |
|---|---|---|
| Verificação do webhook falha | URL errada ou `VERIFY_TOKEN` diferente | Confirme que a URL inclui `/webhook` e que o token é idêntico no `.env` e no painel |
| Recebo status de entrega mas não a mensagem | Campo `messages` não assinado | Painel Meta → Webhook → Gerenciar → ativar `messages` |
| Erro 401 no envio da resposta | `META_ACCESS_TOKEN` expirou (24h) | Gere um novo token no painel ou crie um token de sistema permanente (veja abaixo) |
| Túnel do Ngrok caiu | Sessão expirou | Reinicie o ngrok e atualize a URL no painel da Meta |
| Worker não responde | Redis não inicializou antes do worker | `docker-compose restart worker` |
| Resposta genérica sem contexto | Base RAG não foi indexada | Rode o script de ingestão (Fase 2.2) |

### Criar um Token de Sistema Permanente (evitar expiração de 24h)

1. No **Meta Business Manager** ([business.facebook.com](https://business.facebook.com/)), vá em **Configurações → Usuários → Usuários do Sistema**.
2. Crie um **Usuário do Sistema** com função de Admin.
3. Atribua o app a esse usuário e gere um **token de acesso com permissão `whatsapp_business_messaging`** sem data de expiração.
4. Use esse token no campo `META_ACCESS_TOKEN` do `.env`.

---

## 🎬 Gravando a Demo para o Portfólio

Uma gravação de 40–60 segundos vale mais que 10 páginas de documentação:

1. Abra lado a lado: **WhatsApp Web** (ou celular) + **terminal com os logs do worker**.
2. Envie uma pergunta sobre os documentos da base RAG.
3. Mostre a resposta chegando no WhatsApp e, no terminal, os chunks recuperados e a latência de cada etapa.
4. Adicione o vídeo ao README como GIF ou link para YouTube/Loom.

```markdown
## Demo
![demo](./assets/demo.gif)
```
