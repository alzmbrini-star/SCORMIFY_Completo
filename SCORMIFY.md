# SCORMIFY — Plataforma de Criação de Cursos com IA

> Documentação oficial da plataforma · Última atualização: Julho/2026

**Scormify** é uma plataforma completa para criação, edição e exportação de conteúdo educacional interativo em formato SCORM. Transforme suas apresentações em experiências de aprendizagem envolventes com recursos avançados de multimídia, interatividade e avaliação.

---

## 📋 Visão Geral

| | |
|---|---|
| **Público** | Designers instrucionais, equipes de T&D, universidades corporativas |
| **Formatos de exportação** | SCORM 1.2, HTML Standalone, Single Page, Vídeo (MP4/WebM) |
| **Idioma** | Português (pt-BR) |
| **Stack** | React + FastAPI + MongoDB |
| **Acessibilidade** | VLibras (Língua Brasileira de Sinais) |

---

## 🤖 Agente IA — Criação Automática de Cursos

O Agente IA cria cursos completos a partir de um tema ou documento:

1. **Briefing**: informe tema, público-alvo, número de módulos e tom
2. **Storyboard**: a IA gera a estrutura completa (títulos, conteúdos, roteiros de narração)
3. **Fila de Aprovação** (opcional): o papel *Aprovador* revisa e edita textos antes da geração
4. **Configuração de Mídia**: escolha por slide — imagem IA, vídeo, avatar HeyGen, narração
5. **Geração**: slides prontos com design system moderno (temas "Clean" com Google Fonts)
6. **Retomada de Sessão**: reabra qualquer sessão do wizard pelo Dashboard, em qualquer etapa

### Recursos do Agente
- **Simuladores e jogos interativos** (HTML+JS) gerados por módulo, em tela cheia com auto-ajuste
- **Cenas de Avatar**: sugestão automática de cenas com avatar HeyGen (TTS nativo, fundo transparente, voz pt-BR)
- **Quizzes** com correção automática e rastreamento SCORM
- **Auto-contraste**: fundos escuros recebem texto claro automaticamente
- **Import de PDF/PPT**: gere cursos a partir de documentos existentes

---

## ✏️ Editor de Slides

Editor visual completo com timeline, camadas e propriedades por elemento.

### Elementos suportados
| Elemento | Descrição |
|---|---|
| **Texto / Texto com IA** | Editor rich-text com +30 fontes (Manrope, Sora, Space Grotesk, Fraunces, etc.), geração de conteúdo por prompt |
| **Imagem** | Upload, galeria do projeto, geração IA (Gemini Nano Banana, Leonardo AI, Krea AI) |
| **Vídeo** | Upload, YouTube/Vimeo, Bunny Stream, biblioteca de vídeos |
| **Áudio** | Narração TTS (ElevenLabs), upload, efeitos sonoros, trilha de fundo |
| **HTML interativo** | Cole código ou gere com IA (simuladores, infográficos, calculadoras) |
| **PDF** | Upload com 3 modos: visualizador completo, visualizador limpo (sem controles) ou somente páginas como imagens |
| **Flipbook** | URL externa (FlipHTML5/Issuu), PDF ou sequência de imagens |
| **Quiz** | Banco de questões com configuração de aprovação |
| **Cenário Ramificado** | Árvore de decisões com feedback e pontuação |
| **Botão / Formas / Anotações** | Elementos de interação e destaque |
| **Whiteboard** | Vídeo estilo "quadro branco" com desenho animado (ver abaixo) |

### Ferramentas do Editor
- **Analisador Estético**: análise visual do curso via IA (contraste, fontes, layout) com score 0-100 e correção em um clique
- **Temas Visuais**: aplique design systems completos em todos os slides
- **Cor do Texto em Massa**: altere cor/fonte/tamanho de todos os slides de uma vez
- **Sombra de Textos**: por slide ou curso inteiro
- **Biblioteca de Marca**: logos, cores e imagens da empresa (Brand Kit) com aplicação automática
- **Timeline**: controle de quando cada elemento aparece, com animações de entrada

---

## 🎬 Whiteboard (Vídeo de Quadro Branco)

Gera vídeos animados estilo "mão desenhando":

- Plano de desenho criado por IA (Claude Sonnet) a partir do texto do slide
- Biblioteca com **~2.000 ícones vetoriais** (objetos reais: árvores, casas, pessoas, etc.)
- Formas, setas e textos com geometria correta
- Efeito de zoom cinematográfico configurável
- Renderização isolada em subprocesso (estável em produção, saída 720p)

---

## 🎓 Recursos Pedagógicos

- **Tutor IA**: chatbot embutido nos cursos exportados que responde dúvidas sobre o conteúdo
- **Dashboard do Tutor IA**: perguntas mais frequentes por curso/empresa, drill-down e interações recentes
- **Gamificação**: badges configuráveis com upload de imagem, feedback por projeto
- **Quizzes SCORM**: nota mínima (mastery), tentativas e relatório via `cmi.interactions`
- **Cenários ativos**: aprendizagem baseada em decisões com consequências

---

## 📦 Exportação

| Formato | Características |
|---|---|
| **SCORM 1.2** | Pacote .zip completo: rastreamento de conclusão, notas, resume (lesson_location), suspend_data. Compatível com Moodle, TalentLMS, SAP SuccessFactors, etc. |
| **HTML Standalone** | Arquivo único auto-contido (imagens/PDFs embutidos em base64), funciona offline |
| **Single Page** | Curso em página única com rolagem, seções bloqueadas até interação, ideal para microlearning |
| **Vídeo MP4/WebM** | Geração 100% client-side (sem custo de servidor) |

Todos os exports incluem: Tutor IA (opcional), VLibras, gamificação, PDFs e mídias embutidas.

---

## 👥 Papéis e Permissões

| Papel | Acesso |
|---|---|
| **Super Admin** | Tudo: todas as empresas, usuários, migrações, limpeza de dados |
| **Company Admin** | Projetos e analytics da sua empresa |
| **Autor** | Criação e edição dos próprios cursos |
| **Aprovador** | Fila de aprovação de storyboards da sua empresa (revisão/edição de textos) |

**Notificações por e-mail (Resend)**: aprovação enviada/aprovada/rejeitada, curso gerado, resumo de atividade do Tutor IA — com preferências por usuário.

---

## 🔌 Integrações

| Serviço | Uso | Chave |
|---|---|---|
| **OpenAI GPT-4o / Gemini** | Geração de texto e imagens (Nano Banana) | Emergent LLM Key (embutida) |
| **Claude Sonnet** | Planos do Whiteboard | Emergent LLM Key (embutida) |
| **HeyGen** | Vídeos de avatar + TTS nativo | Chave do usuário |
| **ElevenLabs** | Narração de slides | Chave do usuário |
| **Leonardo AI** | Imagens premium (6 estilos) | Chave do usuário |
| **Krea AI** | 11 modelos de imagem curados (Flux, Imagen 4, Ideogram...) | Chave do usuário |
| **ConvertAPI** | Import de PowerPoint | Chave do usuário |
| **Resend** | E-mails transacionais | Configurada no .env |
| **Bunny Stream** | Hospedagem de vídeo | Embed do usuário |

---

## 🏗️ Arquitetura Técnica (resumo)

```
/app
├── backend (FastAPI + MongoDB)
│   ├── routes/        # agent, projects, export, heygen, leonardo, aesthetics...
│   └── services/      # ai_agent, scorm_exporter, html_exporter,
│                      # single_page_exporter, whiteboard_worker (subprocesso)
└── frontend (React + Shadcn/UI)
    └── src/pages/     # Editor, Agent, Dashboard, Admin
```

**Destaques de engenharia:**
- Renderização de Whiteboard em **subprocesso isolado** (proteção contra OOM em produção)
- Assets persistidos em **MongoDB (GridFS)** com fallback para disco (resiliente a storage efêmero)
- Elementos HTML interativos com **auto-fit** (conteúdo 960x540 escala e centraliza em qualquer superfície)
- Uploads em chunks para arquivos grandes (PPT/PDF)
- Conversão de PDF em imagens via **PyMuPDF** (até 30 páginas, 2x de resolução)

---

## 🚀 Fluxo de Trabalho Recomendado

1. **Crie** o curso com o Agente IA (ou importe PPT/PDF)
2. **Revise** via Fila de Aprovação (se aplicável)
3. **Refine** no Editor: mídias, quizzes, PDF de apoio, gamificação
4. **Analise** com o Analisador Estético e aplique correções
5. **Configure** Tutor IA e requisitos de conclusão
6. **Exporte** em SCORM e publique no seu LMS
7. **Acompanhe** dúvidas dos alunos no Dashboard do Tutor IA
