"""Small, explicit contracts for teaching-slide batches; never fabricate missing slides."""
import json


def teaching_prompt(batch, config, source, story_bible=None):
    if not all(s.get('type') in ('title', 'content', 'summary') for s in batch):
        return None
    items = [{k: s[k] for k in ('id', 'title', 'type', 'purpose', 'moduleName',
              'sourceRefs', 'sourceExcerpt', 'sourceRequired', 'requiredImagePrompt',
              'guidedStage', 'guidedUnitId', 'storyContext', 'narrativeBeat',
              'imageRole', 'linkedSceneTitle') if k in s} for s in batch]
    journey = config.get('visualCourseMode') == 'illustrated_journey'
    return f'''Gere SOMENTE os {len(batch)} slides de ensino solicitados, em português do Brasil.
Curso: {config.get('title', '')}. Nível: {config.get('depth', 'intermediario')}.
Estes são slides de explicação, capa ou síntese. Não crie jogos, simuladores, avaliações,
novas unidades nem outros slides. As atividades do percurso são produzidas separadamente.
Retorne um objeto JSON válido com a chave "slides" e exatamente {len(batch)} objetos,
na ordem dos IDs solicitados. Preserve cada id, title, type e moduleName.
Não inclua comentários ou Markdown fora do JSON. Escape aspas e quebras de linha nos textos.

FONTE DE REFERÊNCIA (não é uma lista de slides adicionais):
{source}

Slides a gerar: {json.dumps(items, ensure_ascii=False)}

CONTRATO DE CONTEÚDO:
- Para cada conteúdo desenvolva especificamente sourceExcerpt/sourceRefs e purpose,
  com explicação, exemplo aplicável e cuidados. Não apenas anuncie o assunto.
- Use 70–140 palavras visíveis, título curto e até três pontos ou cards. Conserve
  regras, ressalvas e informações da fonte. Não invente ações ou automações do produto.
- Capa: nome real do curso, apresentação e objetivo; síntese: conclusões das unidades.
- Não acrescente dados fictícios como se fossem regras reais. Exemplos devem ser identificados.
- Use elementos de texto com HTML de corpo (h1/h2/p/ul/li), nunca scripts ou documento
  HTML completo. Contraste legível. Varie composições sem substituir explicações por rótulos.
- Para sourceRequired não use conteúdo genérico nem uma instrução ao professor no lugar da lição.
- Preserve marcadores [IMG:arquivo.png] integralmente, quando atribuídos à tela.
- imageKeywords: copie requiredImagePrompt se existir; senão proponha uma imagem pertinente
  em inglês, sem texto. Não recrie capturas originais da interface.
- narrationScript: explique os pontos da tela; notes: cuidados do instrutor. quizQuestions: [].
- Cada slide deve conter elements não vazio, por exemplo
  {{"id":"ID_SOLICITADO","title":"Título","type":"content","moduleName":"Unidade",
  "elements":[{{"type":"text","content":"<h2>Título</h2><p>Explicação desenvolvida...</p>",
  "position":"left","width":1050,"height":680}}],"narrationScript":"Explicação falada",
  "notes":"Cuidados","imageKeywords":"contextual illustration","quizQuestions":[]}}.
{('JORNADA VISUAL: mantenha personagens e ambiente da bíblia, narrativeBeat, imageRole e linkedSceneTitle. Inclua learnerAction, três visualEvidence e journeyLayout variados. Bíblia: '+json.dumps(story_bible or {}, ensure_ascii=False)) if journey else ''}
Antes de responder conte os objetos e confira os IDs. Não omita nem duplique uma tela.'''


def decode_batch(response, requested):
    """Accept harmless wrappers, but require a complete, unambiguous slide batch."""
    if not isinstance(response, str):
        raise ValueError('Resposta do lote não é texto JSON.')
    stripped = response.strip()
    if stripped.startswith('```'):
        stripped = stripped.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        raw, end = json.JSONDecoder().raw_decode(stripped)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError('JSON incompleto ou inválido no lote; retorne somente o objeto slides completo.') from exc
    if stripped[end:].strip():
        raise ValueError('Retorne somente um objeto JSON, sem texto adicional após o lote.')
    rows = raw.get('slides') if isinstance(raw, dict) else None
    if not isinstance(rows, list) or len(rows) != len(requested) or not all(isinstance(s, dict) for s in rows):
        count = len(rows) if isinstance(rows, list) else 0
        raise ValueError(f'O lote exige {len(requested)} slides completos; foram recebidos {count}. Não gere o curso inteiro nem omita telas.')
    expected = [s.get('id') for s in requested]
    received = [s.get('id') for s in rows]
    if all(expected) and any(received):
        if len(set(received)) != len(rows) or set(received) != set(expected):
            raise ValueError('Os IDs retornados não correspondem exatamente aos slides solicitados.')
        by_id = {s['id']: s for s in rows}
        rows = [by_id[ident] for ident in expected]
    return {'slides': rows}
