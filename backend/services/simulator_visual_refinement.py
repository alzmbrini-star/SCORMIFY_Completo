"""Rebuild only the visual layer from bounded, revalidated rule JSON, never HTML."""
import json


async def refine_visual(source,prompt,context,complexity='advanced',visual_style='illustrated'):
    from services.rule_simulators import validate_rules,render_rules,single_action_shortcuts
    from services.simulator_experience import normalize_experience,options
    from services.rule_visuals import generate_visual
    from services.llm_config import simulator_generation_config
    if not isinstance(source,str) or len(source)>120000:raise ValueError('Modelo de origem inválido ou muito grande')
    raw=json.loads(source)
    if not isinstance(raw,dict):raise ValueError('Refino exige dados de um simulador do motor de regras')
    # Untrusted authored artwork/code is never executed or passed through.
    raw.pop('visual',None);raw.pop('visualNotice',None);raw.pop('visualProject',None)
    data=validate_rules(raw)
    if single_action_shortcuts(data):raise ValueError('O modelo de origem precisa de revisão lógica antes do refino visual')
    data['experience']=normalize_experience(raw.get('experience'),data,options(complexity,visual_style))
    provider,key,model=simulator_generation_config()
    if not key:raise ValueError('Configure a chave do provedor para refinar o cenário')
    import uuid
    visual,notice=await generate_visual(data,prompt,context,'visual-refine-'+uuid.uuid4().hex[:12],provider,key,model)
    if visual is None:raise ValueError('O refino visual não foi aprovado. '+notice+' A prévia anterior foi preservada.')
    data['visual']=visual
    return {'html':render_rules(data)}
