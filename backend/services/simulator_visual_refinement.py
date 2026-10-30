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
    previous=raw.pop('visual',None);raw.pop('visualNotice',None);raw.pop('visualProject',None)
    data=validate_rules(raw)
    if data.get('didacticMode')!='process-demo-v1' and single_action_shortcuts(data):raise ValueError('O modelo de origem precisa de revisão lógica antes do refino visual')
    if previous is not None:
        from services.rule_visuals import validate_visual
        try:data['_refinementVisual']=validate_visual(previous,data)
        except (ValueError,TypeError,KeyError):pass  # Invalid old artwork is never trusted or forwarded.
    data['experience']=normalize_experience(raw.get('experience'),data,options(complexity,visual_style))
    provider,key,model=simulator_generation_config()
    if not key:raise ValueError('Configure a chave do provedor para refinar o cenário')
    import uuid
    visual,notice=await generate_visual(data,prompt,context,'visual-refine-'+uuid.uuid4().hex[:12],provider,key,model)
    if visual is None:
        import logging
        logging.getLogger('server').warning('Visual refinement rejected: %s',notice[:1800])
        reason=('As mudanças da arte ainda ficaram pequenas ou desconectadas dos estados do modelo.'
                if 'mudança observável' in notice else 'A nova composição ainda não passou na validação didática ou técnica.')
        raise ValueError('O refino visual não foi aprovado. '+reason+' As regras e a prévia anterior foram preservadas. Nenhuma substituição foi aplicada.')
    data.pop('_refinementVisual',None)
    data['visual']=visual
    return {'html':render_rules(data)}
