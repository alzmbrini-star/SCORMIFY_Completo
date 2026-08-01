# Implantação multi-tenant

## Arquitetura recomendada

Para manter a aplicação atual:

1. Publique o frontend React em uma hospedagem de sites.
2. Publique o backend FastAPI em um serviço compatível com Python e processos
   de longa duração.
3. Use MongoDB Atlas como banco persistente externo.
4. Guarde chaves de IA e a URI do MongoDB no gerenciador de segredos do
   ambiente de hospedagem.

O Sites pode hospedar a interface e oferece D1/R2 para aplicações construídas
para esse ambiente. Ele não executa diretamente este backend FastAPI/MongoDB.
Migrar para D1 exigiria reescrever a camada de dados e partes do backend.

Topologia pretendida:

```text
Navegador
   ├── Interface React ── Sites
   └── /api ──────────── Backend FastAPI (hospedagem Python)
                              ├── MongoDB Atlas
                              ├── armazenamento persistente de arquivos
                              └── provedores de IA
```

## Isolamento dos clientes

O tenant da aplicação é `companyId`. Usuários comuns nunca devem escolher esse
valor diretamente; ele deve vir da sessão autenticada. Superadministradores
podem operar entre empresas de forma explícita.

Regras obrigatórias:

- toda consulta de dados de cliente deve incluir `companyId`;
- recursos buscados por ID devem passar por um guard de autorização;
- projetos sem `companyId` são legados e visíveis apenas ao superadministrador;
- jobs, mídia, relatórios, uploads e caches também precisam carregar o tenant;
- logs de auditoria devem registrar usuário, empresa, ação e recurso;
- testes devem tentar acessar recursos de outra empresa e esperar 404/403.

## Segredos de IA

Use chaves de projeto separadas por ambiente:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `KLING_API_KEY` (chave única do Kling AI Open Platform)

Não coloque chaves no frontend nem no Git. Em produção, configure-as como
segredos do backend. Para controlar custos, registre consumo com `companyId` e
aplique cotas por empresa antes de chamar o provedor.

### Vídeos educativos com Kling AI

No serviço **backend** do Render, configure:

```dotenv
KLING_API_KEY=<chave criada no console do Kling AI>
KLING_API_BASE_URL=https://api-singapore.klingai.com
KLING_MAX_VIDEO_BYTES=188743680
```

O frontend nunca recebe essa chave. A geração é assíncrona: o projeto salva
o identificador da tarefa, consulta o progresso e, quando o Kling conclui,
baixa o MP4 para os ativos permanentes do projeto no MongoDB. Isso é
necessário porque as URLs de resultado do provedor são temporárias.

Para usar a opção diretamente no fluxo de storyboard, o Agent precisa estar
ativado (`ENABLE_LEGACY_AI_ROUTES=true`) e submetido às mesmas regras de
isolamento por `companyId` descritas acima.

## MongoDB Atlas

Crie um cluster e um usuário exclusivo para a aplicação. Configure:

```dotenv
MONGO_URL=mongodb+srv://...
DB_NAME=scormify
```

Use TLS, restrição de rede, backups, alertas e credenciais distintas entre
desenvolvimento e produção. Os índices de acesso mais frequentes devem começar
por `companyId`.

## Antes de produção

- substituir o login Google acoplado ao Emergent por um provedor próprio;
- configurar cookies seguros e origens CORS exatas;
- concluir a revisão de endpoints legados de Agent, Quiz, Cenários, HeyGen e
  mídia; parte desse código ainda não aplica autorização por tenant;
- aplicar limites de upload, requisição e custo de IA;
- testar restauração de backup;
- executar uma suíte de isolamento entre pelo menos dois tenants;
- validar exportações SCORM sem depender de URLs privadas temporárias.

O código preparado localmente já protege projetos, criação e consulta de jobs,
uploads PPT em partes, exportações e renders de whiteboard por `companyId`.
Isso reduz os pontos críticos, mas não representa ainda uma certificação de
segurança do sistema inteiro.

## Modo seguro inicial no Render

O contêiner de produção inicia com os módulos legados de IA desativados:

```dotenv
ENABLE_LEGACY_AI_ROUTES=false
ENABLE_PUBLIC_TUTOR=false
```

Nesse modo, autenticação, empresas, usuários, projetos e os módulos já
revisados ficam disponíveis, mas Agent, Quiz, Cenários, HeyGen e outras rotas
legadas de geração permanecem fechadas. Ative-as somente depois de concluir os
testes de isolamento entre tenants.

O primeiro administrador também não usa mais senha padrão. A criação só
acontece quando as duas variáveis abaixo estiverem configuradas, e a senha
precisa ter pelo menos 16 caracteres:

```dotenv
BOOTSTRAP_ADMIN_EMAIL=admin@scormify.com
BOOTSTRAP_ADMIN_PASSWORD=<segredo forte armazenado no Render>
```

Depois do primeiro acesso e da troca de senha, remova
`BOOTSTRAP_ADMIN_PASSWORD` do ambiente.
