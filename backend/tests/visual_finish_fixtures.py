"""Diverse visual QA compositions only; never used to route generation by topic."""
from test_didactic_visualizations import fixture


def pilots():
    atom=fixture();atom['presentation']={'theme':'midnight','atmosphere':'studio','accent':'#4de3ff'}
    for n in atom['nodes']:
        n['appearance']={'material':'emissive' if n['id']=='electron' else 'matte' if n['type'] not in {'text','ellipse'} else 'flat','depth':'soft'}
    def node(key,kind,label,attrs,material='matte',depth='soft'):
        return {'id':key,'type':kind,'label':label,'explanation':label+'. Elemento de uma representação ilustrativa.',
                'attrs':attrs,'appearance':{'material':material,'depth':depth}}
    water={'title':'Explorando um circuito hidráulico','subtitle':'Componentes, conexões e rotação ilustrativa da bomba.',
      'learningGoal':'Identificar reservatório, bomba, tubulação e tanque de destino.',
      'scientificNote':'Esquema qualitativo, fora de escala. O movimento do rotor é ilustrativo; não calcula pressão, vazão ou rendimento.',
      'duration':12,'background':'#edf4fa','presentation':{'theme':'daylight','atmosphere':'technical','accent':'#2563eb'},'nodes':[
        node('pipe','path','Tubulação',{'d':'M220 280 H340 M460 280 H580 V210 H610','fill':'none','stroke':'#7894ad','strokeWidth':16},'flat','none'),
        node('reservoir','rect','Água do reservatório',{'x':70,'y':245,'width':150,'height':108,'rx':8,'fill':'#2da7da'},'liquid'),
        node('frame','rect','Reservatório',{'x':60,'y':190,'width':170,'height':175,'rx':12,'fill':'none','stroke':'#64748b','strokeWidth':5},'flat','none'),
        node('base','rect','Base da bomba',{'x':350,'y':335,'width':100,'height':24,'rx':7,'fill':'#7c91a4'},'metal'),
        node('pump','circle','Carcaça da bomba',{'x':400,'y':280,'r':60,'fill':'#6289a2','stroke':'#31546e','strokeWidth':4},'metal','raised'),
        node('rotor','polygon','Rotor',{'points':[[400,236],[414,269],[443,296],[408,294],[365,310],[387,275]],'fill':'#67d2e5'},'metal'),
        node('hub','circle','Eixo',{'x':400,'y':280,'r':12,'fill':'#e5f2fb'},'metal'),
        node('tank','rect','Tanque',{'x':610,'y':145,'width':135,'height':220,'rx':14,'fill':'#dbeaf4','stroke':'#64748b','strokeWidth':4},'glass'),
        node('volume','rect','Água no tanque',{'x':621,'y':272,'width':113,'height':81,'rx':7,'fill':'#2da7da'},'liquid'),
        node('label1','text','Reservatório',{'x':145,'y':163,'text':'Reservatório','fontSize':26,'anchor':'middle','fill':'#10243b'},'flat','none'),
        node('label2','text','Bomba',{'x':400,'y':190,'text':'Bomba','fontSize':26,'anchor':'middle','fill':'#10243b'},'flat','none'),
        node('label3','text','Tanque',{'x':677,'y':115,'text':'Tanque','fontSize':26,'anchor':'middle','fill':'#10243b'},'flat','none')],
      'motions':[{'node':'rotor','kind':'rotate','cx':400,'cy':280,'dx':0,'dy':0,'cycles':3,'phase':0}]}
    plant={'title':'Explorando as partes de uma planta','subtitle':'Observe folhas, caule e estruturas de sustentação.',
      'learningGoal':'Relacionar as formas visíveis às partes da planta. O destaque pulsante orienta a observação das folhas.',
      'scientificNote':'Ilustração simplificada, não uma simulação biológica. A pulsação é um recurso de destaque, não um comportamento físico das folhas.',
      'duration':10,'background':'#fbf6eb','presentation':{'theme':'warm','atmosphere':'natural','accent':'#3f7c47'},'nodes':[
        node('ground','ellipse','Superfície de apoio',{'x':400,'y':397,'rx':150,'ry':18,'fill':'#ded3bb'},'matte','none'),
        node('pot','polygon','Vaso',{'points':[[320,315],[480,315],[458,395],[342,395]],'fill':'#b87850'},'matte','raised'),
        node('soil','ellipse','Solo',{'x':400,'y':318,'rx':80,'ry':13,'fill':'#6c4f38'},'matte'),
        node('stem','path','Caule',{'d':'M400 320 C390 265 414 215 400 133','fill':'none','stroke':'#397a43','strokeWidth':11},'flat','none'),
        node('leaf_left','path','Folha à esquerda',{'d':'M400 236 C350 160 275 167 276 193 C278 240 352 264 400 236 Z','fill':'#5b9b54'},'matte'),
        node('vein_left','path','Nervura da folha',{'d':'M286 196 Q340 229 395 237','fill':'none','stroke':'#d9e8b1','strokeWidth':3},'flat','none'),
        node('leaf_right','path','Folha à direita',{'d':'M401 200 C435 132 510 133 515 156 C516 200 447 225 401 200 Z','fill':'#79b35d'},'matte'),
        node('vein_right','path','Nervura à direita',{'d':'M407 198 Q458 177 503 156','fill':'none','stroke':'#e1edbe','strokeWidth':3},'flat','none'),
        node('label','text','Folhas',{'x':570,'y':208,'text':'Folhas','fontSize':28,'fill':'#342b22'},'flat','none')],
      'motions':[{'node':'leaf_right','kind':'pulse','cx':0,'cy':0,'dx':0,'dy':0,'cycles':2,'phase':0}]}
    return atom,water,plant
