"""Bounded presentation-only animation declarations. Never alter rule state."""
import math


def validate_motions(raw, nodes):
    if not isinstance(raw,list) or not 1<=len(raw)<=24:raise ValueError('Use de 1 a 24 movimentos ilustrativos')
    definitions={n['id']:n for n in nodes};seen=set();result=[]
    for row in raw:
        fields={'node','kind','cx','cy','dx','dy','cycles','phase'}
        if not isinstance(row,dict) or set(row)!=fields:raise ValueError('Movimento ilustrativo exige node,kind,cx,cy,dx,dy,cycles,phase')
        ident=row['node'];kind=row['kind']
        if not isinstance(ident,str) or ident not in definitions or ident in seen or definitions[ident]['type']=='text':raise ValueError('Movimento ilustrativo precisa de objeto não textual único')
        if kind not in ('orbit','rotate','translate'):raise ValueError('Movimento ilustrativo não suportado')
        clean={'node':ident,'kind':kind}
        for key,lo,hi in (('cx',-800,1600),('cy',-450,900),('dx',-400,400),('dy',-225,225),('cycles',-8,8),('phase',0,360)):
            value=row[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Parâmetro de movimento inválido: '+key)
            clean[key]=value
        if abs(clean['cycles'])<.25:raise ValueError('Movimento precisa de cycles entre 0.25 e 8 em módulo')
        if kind in ('orbit','translate') and max(abs(clean['dx']),abs(clean['dy']))<1:raise ValueError('Movimento sem deslocamento')
        if kind=='orbit' and definitions[ident]['type'] not in ('group','circle','ellipse'):raise ValueError('Órbita exige grupo ou objeto com centro')
        seen.add(ident);result.append(clean)
    return result
