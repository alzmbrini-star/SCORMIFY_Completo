"""User-scoped simulator creation permission; legacy users retain access."""
import copy

MESSAGE='A criação de simuladores não está habilitada para seu usuário. Solicite a permissão à Administração.'

def can_create_simulators(user):
    if not user:return False
    if user.get('role')=='super_admin' or 'super_admin' in (user.get('roles') or []):return True
    return (user.get('permissions') or {}).get('createSimulators',True) is True

def require_simulators(user):
    if not can_create_simulators(user):
        from fastapi import HTTPException
        raise HTTPException(403,MESSAGE)

def permission_patch(body):
    """Allow-list and validate admin input; never accept arbitrary permissions."""
    if 'permissions' not in body:return {}
    value=body['permissions']
    if not isinstance(value,dict) or set(value)-{'createSimulators'}:raise ValueError('Permissão de usuário inválida')
    if 'createSimulators' in value and type(value['createSimulators']) is not bool:raise ValueError('Criar simuladores deve ser verdadeiro ou falso')
    return {f'permissions.{key}':v for key,v in value.items()}

def simulator_request(request):
    from services.html_activity_intent import html_activity_kind
    return bool(request.get('sourceSimulator')) or html_activity_kind(request.get('prompt',''),request.get('simulatorActivityType','simulation')) in {'simulation','visualization'}

def restrict_config(config,user):
    result=copy.deepcopy(config or {})
    result['simulatorsAllowed']=can_create_simulators(user)
    if not result['simulatorsAllowed']:
        result['enabledResources']=dict(result.get('enabledResources') or {},simulator=False)
    return result

def restrict_structure(structure,user):
    result=copy.deepcopy(structure)
    if can_create_simulators(user):return result
    for module in result.get('modules',[]):
        for slide in module.get('slides',[]):
            if slide.get('type')=='simulator':
                slide['type']='content'
                for key in ('htmlContent','elements','requiredMechanic','simulatorSpec'):slide.pop(key,None)
    return result
