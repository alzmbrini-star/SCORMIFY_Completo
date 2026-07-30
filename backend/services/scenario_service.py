"""AI generation of interactive decision-tree learning scenarios."""
import os
import json
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger("server")


def generate_id():
    return str(uuid.uuid4())


async def generate_scenario_with_ai(config: dict) -> dict:
    """
    Generate a complete scenario decision tree using Gemini AI.

    Args:
        config: dict with keys: theme, objectives, audience, complexity,
                industry, duration_minutes, language

    Returns:
        dict with the complete scenario structure (nodes + choices)
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    legacy_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if openai_key:
        provider = "openai"
        model = (
            os.environ.get("OPENAI_SCENARIO_MODEL", "").strip()
            or os.environ.get("OPENAI_TEXT_MODEL", "").strip()
            or "gpt-4o"
        )
        api_key = openai_key
    elif gemini_key or legacy_key:
        provider = "gemini"
        model = os.environ.get("GEMINI_SCENARIO_MODEL", "").strip() or "gemini-2.5-flash"
        api_key = gemini_key or legacy_key
    else:
        raise ValueError(
            "Nenhuma chave de IA configurada. Cadastre OPENAI_API_KEY "
            "no backend do Render."
        )

    theme = config.get("theme", "")
    objectives = config.get("objectives", "")
    audience = config.get("audience", "")
    complexity = config.get("complexity", "intermediate")
    industry = config.get("industry", "")
    duration = config.get("duration_minutes", 15)
    language = config.get("language", "pt-BR")

    complexity_map = {
        "beginner": "simples com 3-4 nós de decisão e consequências diretas",
        "intermediate": "moderada com 5-7 nós de decisão, caminhos ramificados e consequências de médio prazo",
        "advanced": "complexa com 8-12 nós de decisão, múltiplas ramificações, dilemas éticos e consequências de longo prazo"
    }
    complexity_desc = complexity_map.get(complexity, complexity_map["intermediate"])

    system_message = f"""Você é um arquiteto de soluções educacionais corporativas especializado em criar cenários de aprendizagem ativa baseados em simulações realistas.

Sua tarefa é gerar um cenário interativo completo em formato JSON estruturado.

REGRAS CRÍTICAS:
1. Responda APENAS com JSON válido, sem markdown, sem explicações antes ou depois
2. O idioma do conteúdo deve ser: {language}
3. Cada nó (node) deve ter um ID único no formato "node_X"
4. O primeiro nó deve ter id "node_1"
5. Cada escolha (choice) deve apontar para um next_node_id válido OU ser null para nós finais
6. Nós finais devem ter is_ending: true e um score de 0 a 100
7. Crie personagens realistas com nome, cargo e personalidade
8. Inclua feedback construtivo em cada escolha explicando por que foi boa ou ruim
9. O cenário deve ter múltiplos finais possíveis (bom, regular, ruim)"""

    prompt = f"""Gere um cenário de aprendizagem ativa com as seguintes especificações:

**Tema**: {theme}
**Objetivos de Aprendizagem**: {objectives}
**Público-Alvo**: {audience}
**Setor/Indústria**: {industry or 'Corporativo geral'}
**Complexidade**: {complexity_desc}
**Duração Estimada**: {duration} minutos

O JSON deve seguir EXATAMENTE esta estrutura:
{{
  "title": "Título do Cenário",
  "description": "Descrição breve do cenário e seu contexto",
  "context": "Contexto corporativo detalhado: empresa fictícia, situação, desafio central",
  "characters": [
    {{
      "name": "Nome do Personagem",
      "role": "Cargo/Função",
      "personality": "Descrição breve da personalidade",
      "avatar_description": "Descrição visual do personagem para futura geração de avatar"
    }}
  ],
  "learning_objectives": ["Objetivo 1", "Objetivo 2"],
  "competencies_evaluated": ["Competência 1", "Competência 2"],
  "nodes": [
    {{
      "id": "node_1",
      "type": "narrative",
      "title": "Título da Cena",
      "narrative": "Texto narrativo descrevendo a situação. Pode incluir diálogos dos personagens entre aspas.",
      "character_speaking": "Nome do personagem ou null",
      "is_ending": false,
      "ending_type": null,
      "score": null,
      "choices": [
        {{
          "id": "choice_1_1",
          "text": "Texto da opção que o aluno pode escolher",
          "next_node_id": "node_2",
          "feedback": "Feedback explicando as consequências desta escolha",
          "is_optimal": false,
          "points": 10
        }}
      ]
    }},
    {{
      "id": "node_final_good",
      "type": "ending",
      "title": "Desfecho Positivo",
      "narrative": "Narrativa do desfecho positivo...",
      "character_speaking": null,
      "is_ending": true,
      "ending_type": "good",
      "score": 90,
      "choices": []
    }}
  ]
}}

IMPORTANTE:
- Crie pelo menos 3 finais diferentes (ending_type: "good", "neutral", "bad")
- Cada nó narrativo deve ter 2-4 escolhas
- As escolhas devem testar pensamento crítico, não ter respostas óbvias
- Inclua pelo menos um dilema onde todas as opções têm prós e contras
- A narrativa deve ser envolvente e realista para o contexto corporativo"""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"scenario-gen-{uuid.uuid4()}",
            system_message=system_message
        ).with_model(provider, model)
        if provider == "openai":
            chat = chat.with_params(
                temperature=0.4,
                response_format={"type": "json_object"},
            )

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)

        # Clean response - remove markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        scenario_data = json.loads(cleaned)

        # Validate structure
        if "nodes" not in scenario_data or not scenario_data["nodes"]:
            raise ValueError("AI response missing 'nodes' array")

        # Ensure all nodes have required fields
        for node in scenario_data["nodes"]:
            node.setdefault("id", generate_id())
            node.setdefault("type", "narrative")
            node.setdefault("title", "")
            node.setdefault("narrative", "")
            node.setdefault("character_speaking", None)
            node.setdefault("is_ending", False)
            node.setdefault("ending_type", None)
            node.setdefault("score", None)
            node.setdefault("choices", [])

            for choice in node.get("choices", []):
                choice.setdefault("id", generate_id())
                choice.setdefault("text", "")
                choice.setdefault("next_node_id", None)
                choice.setdefault("feedback", "")
                choice.setdefault("is_optimal", False)
                choice.setdefault("points", 0)

        logger.info(f"Scenario generated: {scenario_data.get('title', 'Untitled')} with {len(scenario_data['nodes'])} nodes")
        return scenario_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI scenario response as JSON: {e}")
        logger.error(f"Raw response: {response[:500] if response else 'empty'}")
        raise ValueError(f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Scenario generation error: {e}")
        raise
