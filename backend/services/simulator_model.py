"""Domain-independent numeric simulation contract; no subject/layout templates."""
import json
import math
import itertools
from pathlib import Path
import re


def compile_identifiers(raw):
    """Compile model labels/IDs to safe identities without guessing references."""
    if not isinstance(raw,dict):return raw
    result=dict(raw)
    mapping={}
    for key in ('inputs','outputs'):
        rows=raw.get(key)
        if not isinstance(rows,list):continue
        used={row['id'] for row in rows if isinstance(row,dict) and isinstance(row.get('id'),str) and re.fullmatch('[a-z][a-z0-9_]{0,39}',row['id'])}
        seen=set();compiled=[]
        for index,row in enumerate(rows):
            path=f'causalModel.{key}[{index}].id'
            if not isinstance(row,dict):raise ValueError(path+': variável inválida')
            identifier=row.get('id')
            if not isinstance(identifier,str) or not identifier.strip() or len(identifier)>120:
                raise ValueError(path+': informe um identificador textual não vazio, até 120 caracteres')
            if identifier in seen:
                raise ValueError(path+': identificador repetido; cada variável precisa de identidade distinta e as fórmulas devem usar o ID correspondente')
            seen.add(identifier)
            safe=identifier
            if not re.fullmatch('[a-z][a-z0-9_]{0,39}',safe):
                safe=f'{key[:-1]}_auto_{index+1}'
                while safe in used:safe+='x'
                used.add(safe)
            compiled.append(dict(row,id=safe))
            if key=='inputs':mapping[identifier]=safe
        result[key]=compiled
    def expression(value,path,depth=0):
        if depth>16:raise ValueError(path+': expressão causal muito profunda')
        if not isinstance(value,dict):return value
        if set(value)=={'input'}:
            reference=value['input']
            if not isinstance(reference,str) or reference not in mapping:
                raise ValueError(path+': referência input inexistente; use exatamente um ID de causalModel.inputs')
            return {'input':mapping[reference]}
        if isinstance(value.get('args'),list):
            return dict(value,args=[expression(arg,f'{path}.args[{i}]',depth+1) for i,arg in enumerate(value['args'])])
        return value
    if isinstance(result.get('outputs'),list):
        result['outputs']=[dict(row,expression=expression(row.get('expression'),f'causalModel.outputs[{i}].expression')) for i,row in enumerate(result['outputs'])]
    return result


def calculate(expression, inputs, depth=0):
    if depth > 16:
        raise ValueError('Expressão causal muito profunda')
    if type(expression) in (int,float) and math.isfinite(expression):
        return expression
    if not isinstance(expression,dict):
        raise ValueError('Expressão causal inválida')
    if set(expression) == {'input'} and expression['input'] in inputs:
        return inputs[expression['input']]
    op, args = expression.get('op'), expression.get('args')
    if set(expression) != {'op','args'} or op not in ('add','sub','mul','div','min','max') or not isinstance(args,list) or not 2 <= len(args) <= 12:
        raise ValueError('Use operações add/sub/mul/div/min/max e 2 a 12 argumentos')
    values = [calculate(arg,inputs,depth+1) for arg in args]
    if op == 'add':result=sum(values)
    elif op == 'mul':result=math.prod(values)
    elif op == 'min':result=min(values)
    elif op == 'max':result=max(values)
    elif op == 'sub':result=values[0]-sum(values[1:])
    else:
        result=values[0]
        for divisor in values[1:]:
            if abs(divisor) < 1e-9:raise ValueError('Divisão por zero no modelo causal')
            result/=divisor
    if not math.isfinite(result) or abs(result)>1e12:
        raise ValueError('Resultado causal fora do intervalo seguro')
    return result


def validate_model(raw):
    if not isinstance(raw,dict):raise ValueError('Inclua causalModel com inputs e outputs')
    raw=compile_identifiers(raw)
    inputs,outputs=raw.get('inputs'),raw.get('outputs')
    if not isinstance(inputs,list) or not 2<=len(inputs)<=8 or not isinstance(outputs,list) or not 2<=len(outputs)<=8:
        raise ValueError('Defina 2 a 8 entradas e 2 a 8 resultados no modelo causal')
    clean={'inputs':[],'outputs':[]}
    for key,rows in [('inputs',inputs),('outputs',outputs)]:
        ids=set()
        for row in rows:
            if not isinstance(row,dict) or not re.fullmatch('[a-z][a-z0-9_]{0,39}',str(row.get('id',''))) or row['id'] in ids:
                raise ValueError('IDs causais devem ser únicos, alfanuméricos e começar com letra')
            ids.add(row['id'])
            item={'id':row['id']}
            for field in ('label','unit'):
                value=row.get(field)
                if not isinstance(value,str) or not value.strip() or len(value)>100:raise ValueError('Informe rótulo e unidade de cada variável causal')
                item[field]=value.strip()
            if key=='inputs':
                for field in ('min','max','initial'):
                    value=row.get(field)
                    if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e6:raise ValueError('Limites causais devem ser números finitos')
                    item[field]=value
                if not item['min']<=item['initial']<=item['max'] or item['min']==item['max']:raise ValueError('Intervalo causal inválido')
            else:
                item['expression']=row.get('expression')
                reason=row.get('explanation')
                if not isinstance(reason,str) or not reason.strip() or len(reason)>800:raise ValueError('Explique a relação causal de cada resultado')
                item['explanation']=reason.strip()
            clean[key].append(item)
    baseline={item['id']:item['initial'] for item in clean['inputs']}
    # Exercise each input at minimum/maximum, plus joint corners. Reject dead
    # outputs/inputs before asking the model to render a scene.
    scenarios=[baseline]
    for item in clean['inputs']:
        for value in (item['min'],item['max']):scenarios.append(dict(baseline,**{item['id']:value}))
    scenarios += [dict(zip(baseline,values)) for values in itertools.product(*[(i['min'],i['max']) for i in clean['inputs']])]
    results=[[calculate(o['expression'],state) for o in clean['outputs']] for state in scenarios]
    for index,output in enumerate(clean['outputs']):
        if max(row[index] for row in results)-min(row[index] for row in results)<=max(1e-6,abs(results[0][index])*.01):
            raise ValueError('Indicador sem impacto das decisões: '+output['label'])
    for index,item in enumerate(clean['inputs']):
        low,high=results[1+2*index:3+2*index]
        if all(abs(a-b)<=1e-6 for a,b in zip(low,high)):
            raise ValueError('Controle sem consequência nos resultados: '+item['label'])
    clean['verification']={'scenarios':len(scenarios),'inputInfluence':True,'outputSensitivity':True}
    return clean


def inject_model(document, model):
    import re
    model=validate_model(model)
    payload=json.dumps(model,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    runtime=(Path(__file__).parent/'export_assets'/'simulator-model.js').read_text(encoding='utf-8')
    script='<script data-causal-runtime="1">'+runtime.replace('__CAUSAL_MODEL__',payload)+'</script>'
    return re.sub(r'</head>',lambda _:script+'</head>',document,count=1,flags=re.I)
