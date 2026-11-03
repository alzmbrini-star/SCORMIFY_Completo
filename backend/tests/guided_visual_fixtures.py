"""Only test plans; no topic routing or production art templates."""
def plan_for(visual,samples):
    first=next(n for n in visual['nodes'] if n['type']!='text')
    key=first['id']
    return {'setting':'Ambiente ilustrativo do teste.','focus':'Observar mudanças reais.',
            'composition':'Objeto principal legível sobre fundo contrastante.','artDirection':'Ilustração vetorial contextualizada.',
            'objects':[{'id':key,'label':first.get('label',key),'layer':'subject','features':['Contorno legível','Mudança perceptível'],
                        'explanation':'Objeto do processo demonstrado.','alwaysVisible':True}],
            'moments':[{'sampleIndex':s['sampleIndex'],'visibleObjects':[key],'change':'Observar a mudança dos objetos.'} for s in samples]}
