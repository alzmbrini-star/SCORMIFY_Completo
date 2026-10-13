"""AI-authored learning scenarios rendered by a tested, offline visual runtime."""
import asyncio
import itertools
import json
import math
import re
from pathlib import Path

from emergentintegrations.llm.chat import LlmChat, UserMessage
from services.llm_config import simulator_generation_config

TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "simulators" / "visual_lab.html"
SPEC_PROMPT = """Você é designer instrucional. Planeje uma simulação em português brasileiro.
Retorne somente JSON; não gere HTML, código, fórmulas nem URLs. O motor visual já existe.
Escolha template resources para distribuir orçamento/esforço entre 3 áreas (total 100),
decisions para praticar 3 a 5 decisões profissionais com efeitos acumulados, ou pump
somente para bomba hidráulica/água. Nunca transforme outros equipamentos em bomba.
Todo texto deve ser específico ao tema e às situações do conteúdo fornecido.
Modelo obrigatório:
{"template":"resources|decisions|pump","title":"Título curto",
"subtitle":"Contexto concreto em até 180 caracteres",
"mission":"Objetivo prático em até 200 caracteres",
"briefing":"Orientação para experimentar e comparar alternativas em até 350 caracteres",
"debrief":"Síntese e pergunta de reflexão em até 400 caracteres"}
Para resources acrescente:
"areas":[{"name":"Área curta","description":"O que este investimento melhora e seu custo de oportunidade"}, ... 3 áreas],
"metrics":[{"name":"Indicador curto","weights":[90,40,10]}, ... 3 indicadores].
Cada weight vai de 0 a 100 e representa a contribuição ILUSTRATIVA de investir tudo naquela área.
Escolha pesos com trade-offs reais: nenhuma área domina todas as outras. Os indicadores
são a média ponderada das alocações. Não invente probabilidades de retenção, saúde ou segurança.
Para decisions acrescente:
"metrics":[{"name":"Indicador"}, ... 3 indicadores],
"steps":[{"title":"Situação concreta","context":"Problema e restrição, até 280 caracteres",
"choices":[{"label":"Ação até 90 caracteres","effects":[15,-10,5],
"feedback":"Consequência e explicação causal até 280 caracteres"}, ... 3 escolhas]}, ... 3 a 5 etapas].
Os efeitos são pontos ilustrativos entre -20 e 20. Cada escolha tem ganho E custo.
Varie os efeitos e não use alternativas obviamente absurdas ou uma resposta certa de quiz.
Para pump não acrescente áreas, métricas ou etapas: o motor ilustra reservatório, tubulação,
rotor, válvula e tanque, com velocidade/altura/abertura ajustáveis e modelo simplificado.
A missão da bomba é elevar o tanque a 50 L com vazão >=30 L/min e potência <=1,2 kW;
o relógio é acelerado em 10x. Diga que é um modelo didático, não dimensionamento técnico.
Todos os outros modelos também usam índices ilustrativos, não previsões científicas.
Não use nomes de pessoas reais nem afirmações de precisão física que o motor não oferece.
"""


def _text(value, name, limit=400):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"Campo {name} deve conter texto de 1 a {limit} caracteres")
    return value.strip()


def _numbers(values, low, high):
    if not isinstance(values, list) or len(values) != 3 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        or not low <= v <= high for v in values
    ):
        raise ValueError("Indicadores precisam de três valores numéricos no intervalo permitido")
    return values


def validate_spec(raw):
    """Reject incomplete scenarios; never substitute a generic quiz on failure."""
    if not isinstance(raw, dict) or raw.get("template") not in {"pump", "resources", "decisions"}:
        raise ValueError("Modelo de simulador inválido")
    result = {"template": raw["template"]}
    for key, limit in [("title", 90), ("subtitle", 180), ("mission", 200), ("briefing", 350), ("debrief", 400)]:
        result[key] = _text(raw.get(key), key, limit)
    if result["template"] == "pump":
        return result
    metrics = raw.get("metrics")
    if not isinstance(metrics, list) or len(metrics) != 3 or not all(isinstance(m, dict) for m in metrics):
        raise ValueError("São necessários três indicadores")
    result["metrics"] = [{"name": _text(m.get("name"), "indicador", 36)} for m in metrics]
    if result["template"] == "resources":
        areas = raw.get("areas")
        if not isinstance(areas, list) or len(areas) != 3 or not all(isinstance(a, dict) for a in areas):
            raise ValueError("São necessárias três áreas de investimento")
        result["areas"] = [{"name": _text(a.get("name"), "área", 36),
                            "description": _text(a.get("description"), "descrição", 200)} for a in areas]
        for target, metric in zip(result["metrics"], metrics):
            target["weights"] = _numbers(metric.get("weights"), 0, 100)
        weights = [m["weights"] for m in result["metrics"]]
        for a, b in itertools.combinations(range(3), 2):
            if not (any(w[a] > w[b] for w in weights) and any(w[a] < w[b] for w in weights)):
                raise ValueError("Cada área deve oferecer ganhos e custos de oportunidade distintos")
    else:
        steps = raw.get("steps")
        if not isinstance(steps, list) or not 3 <= len(steps) <= 5:
            raise ValueError("São necessárias de três a cinco situações")
        result["steps"] = []
        for step in steps:
            if not isinstance(step, dict) or not isinstance(step.get("choices"), list) or len(step["choices"]) != 3:
                raise ValueError("Cada situação precisa de três escolhas")
            clean = {"title": _text(step.get("title"), "situação", 90),
                     "context": _text(step.get("context"), "contexto", 280), "choices": []}
            for choice in step["choices"]:
                if not isinstance(choice, dict):
                    raise ValueError("Escolha inválida")
                effects = _numbers(choice.get("effects"), -20, 20)
                if not min(effects) < 0 < max(effects):
                    raise ValueError("Cada decisão deve apresentar ganho e custo")
                clean["choices"].append({"label": _text(choice.get("label"), "ação", 90),
                    "effects": effects, "feedback": _text(choice.get("feedback"), "feedback", 280)})
            if len({tuple(c["effects"]) for c in clean["choices"]}) != 3:
                raise ValueError("Escolhas precisam de consequências diferentes")
            result["steps"].append(clean)
    return result


def render_simulator(spec):
    spec = validate_spec(spec)
    # Never interpolate model text into executable JS or markup.
    payload = json.dumps(spec, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.read_text(encoding="utf-8").replace("__SIMULATOR_SPEC__", payload)


async def generate_visual_simulator(prompt, context="", session_id="visual-simulator"):
    provider, key, model = simulator_generation_config()
    if not key:
        raise RuntimeError(f"Configure {provider.upper()}_API_KEY para gerar simuladores")
    chat = LlmChat(api_key=key, session_id=session_id, system_message=SPEC_PROMPT).with_model(provider, model).with_params(temperature=0.35, max_tokens=5000)
    request = f"Pedido: {prompt[:5000]}\nConteúdo de referência: {context[:6500]}"
    last_error = ""
    for attempt in range(2):
        response = await asyncio.wait_for(chat.send_message(UserMessage(text=request)), timeout=90)
        try:
            raw = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", str(response).strip(), flags=re.I))
            spec = validate_spec(raw)
            return {"html": render_simulator(spec), "spec": spec}
        except (ValueError, TypeError) as exc:
            last_error = str(exc)
            request = f"Revise o JSON completo para o mesmo pedido. Problema de validação: {last_error}.\n{request}"
    raise ValueError("O cenário gerado não atingiu o padrão didático. Tente novamente. " + last_error)
