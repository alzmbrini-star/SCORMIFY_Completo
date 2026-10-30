"""Maintained contextual vector art. Pure projection; no theme routing or rules."""
import math


class Painter:
    def __init__(self,instance,style):
        self.i=instance;self.id=instance['id'];self.style=style
        self.ink='#dceafb' if style=='blueprint' else '#193b54'
        self.paper='#29475c' if style=='blueprint' else '#f8fbff'
        self.rows=[{'id':self.id,'type':'group','label':instance['label'],'attrs':dict(instance['position'])}]
    def node(self,key,kind,attrs,parent=None,**extra):
        row={'id':self.id+'_'+key,'type':kind,'label':self.i['label'],'parent':parent or self.id,'attrs':attrs,**extra}
        self.rows.append(row);return row
    def rect(self,key,x,y,w,h,fill,parent=None,**extra):
        return self.node(key,'rect',dict(x=x,y=y,width=w,height=h,fill=fill,**extra),parent)
    def path(self,key,d,fill,parent=None,**extra):return self.node(key,'path',dict(d=d,fill=fill,**extra),parent)
    def bind(self,row,prop,port,a,b):
        source=self.i['inputs'][port];lo,hi=source['range']
        if 'var' in source:row.setdefault('bindings',[]).append({'property':prop,'var':source['var'],'input':[lo,hi],'output':[a,b]})
        else:row['attrs'][prop]=a+(source['value']-lo)/(hi-lo)*(b-a)
    def when(self,port,op,fraction):
        source=self.i['inputs'][port];lo,hi=source['range'];threshold=math.ceil(lo+(hi-lo)*fraction)
        if 'var' in source:return {'op':op,'args':[{'var':source['var']},threshold]}
        return {'lt':source['value']<threshold,'ge':source['value']>=threshold,'eq':source['value']==threshold}[op]
    def action(self,row,slot):
        if self.i['actions'].get(slot):row['action']=self.i['actions'][slot]


def draw_context_component(instance,style):
    p=Painter(instance,style);kind=instance['component'];targets={}
    if kind=='workplace_backdrop':
        p.rect('wall',0,0,760,410,'#17344c' if style=='blueprint' else '#dfe9ed',rx=16)
        p.path('floor','M0 280 H760 V410 H0 Z','#102a40' if style=='blueprint' else '#b5c6cc')
        p.path('light','M380 0 H670 L760 290 H390 Z','#305c72' if style=='blueprint' else '#eff6f6')
        p.rect('window',340,24,344,200,'#4e7184',rx=7)
        p.rect('sky',350,34,324,180,'#86bdcf',rx=3)
        for j,(x,h) in enumerate([(366,66),(413,105),(470,83),(529,139),(595,94)]):
            p.rect('city'+str(j),x,214-h,38,h,'#5b8295')
        p.rect('mullion',502,34,8,180,'#dce8eb')
        p.rect('cross',350,132,324,7,'#dce8eb')
        p.rect('shelf',30,70,125,17,'#77929e',rx=3)
        p.rect('books',41,33,24,37,'#ce9c69',rx=2)
        p.rect('book2',71,27,18,43,'#4e9eab',rx=2)
        p.path('plant','M118 70 Q80 20 104 13 Q128 26 118 70 Q151 16 160 34 Q161 51 118 70','#327b71')
        p.path('desk_shadow','M72 350 L603 339 L715 393 H126 Z','#78909a')
        p.path('desk','M65 318 L602 305 L710 354 L116 374 Z','#b17f57',stroke='#78573e',strokeWidth=3)
        p.path('edge','M116 374 L710 354 V365 L116 386 Z','#8e6347')
    elif kind=='meeting_table':
        p.path('shadow','M7 38 L541 22 L650 85 H64 Z','#758f99')
        p.path('top','M0 13 L537 0 L645 49 L51 69 Z','#b98c62',stroke='#76543c',strokeWidth=3)
        p.path('edge','M51 69 L645 49 V60 L51 81 Z','#926548')
        p.path('grain','M110 35 L505 24 M170 52 L558 37','none',stroke='#d6ad7d',strokeWidth=2)
    elif kind=='harbor_backdrop':
        p.rect('sky',0,0,760,410,'#123650' if style=='blueprint' else '#c8e7ed',rx=16)
        p.path('hill','M0 124 Q83 31 180 110 Q290 5 395 108 Q550 21 760 126 V252 H0 Z','#477b85')
        p.path('distant','M0 174 Q127 100 247 161 Q475 70 760 154 V278 H0 Z','#70a3a6')
        p.rect('water',0,187,760,170,'#2d91af')
        for j,x in enumerate((30,194,395,605)):
            p.rect('ripple'+str(j),x,215+j*20,90,4,'#9de0e8',rx=2)
        p.path('bank','M0 340 L236 310 L760 335 V410 H0 Z','#365461' if style=='blueprint' else '#839d8e')
        p.rect('crane',645,42,9,125,'#526d76')
        p.path('jib','M560 55 H710 L649 23 Z','none',stroke='#526d76',strokeWidth=7)
        p.node('cable','line',dict(x=583,y=55,x2=583,y2=127,stroke='#526d76',strokeWidth=3))
        p.rect('load',569,127,28,22,'#d5ab69',rx=2)
    elif kind=='lock_channel':
        p.path('base','M0 220 H760 V260 H0 Z','#526b72')
        p.rect('low',0,180,215,50,'#2faed0')
        p.rect('high',520,90,240,140,'#36b9dc')
        water=p.rect('water',235,180,260,50,'#4ecfe5');p.bind(water,'y','level',180,90);p.bind(water,'height','level',50,140)
        top=p.rect('surface',235,180,260,5,'#b7f4fc');p.bind(top,'y','level',180,90)
        p.rect('low_line',0,180,215,5,'#b7f4fc');p.rect('high_line',520,90,240,5,'#b7f4fc')
        for port,x,slot in [('entry',214,'entry'),('exit',495,'exit')]:
            gate=p.node(port,'group',dict(x=x,y=0));p.action(gate,slot);parent=gate['id']
            p.rect(port+'_track',0,35,22,195,'#8b9ca0',parent,rx=3)
            blade=p.rect(port+'_blade',4,45,14,185,'#ffce73',parent,stroke='#b38536',strokeWidth=2)
            p.bind(blade,'height',port,185,30)
            p.rect(port+'_top',0,31,24,10,'#e0e9e8',parent,rx=2)
            targets[port]=blade['id']
        boat=p.node('boat','group',dict(x=50,y=155));p.bind(boat,'x','position',50,590);p.bind(boat,'y','level',155,65)
        boat['states']=[{'when':p.when('position','eq',0),'set':{'y':155}}, {'when':p.when('position','ge',1),'set':{'y':65}}]
        parent=boat['id']
        p.path('hull','M0 25 H115 L96 50 H22 Z','#e8a34c',parent,stroke='#855e32',strokeWidth=2)
        p.path('shade','M20 44 H101 L96 50 H22 Z','#bc762c',parent)
        p.rect('cabin',27,0,57,25,'#f4f6ec',parent,rx=4)
        p.rect('roof',24,0,64,6,'#597c91',parent,rx=2)
        for j in range(3):p.rect('glass'+str(j),34+j*15,10,10,10,'#3b8199',parent,rx=1)
        p.node('mast','line',dict(x=99,y=0,x2=99,y2=25,stroke='#cce8ee',strokeWidth=3),parent)
        p.node('flag','polygon',dict(points=[[99,0],[117,7],[99,12]],fill='#77d4bd'),parent)
        alert=p.node('alert','group',dict(x=210,y=3),visibleWhen=p.when('risk','ge',.5))
        p.rect('alert_bg',0,0,320,43,'#8e2535',alert['id'],rx=8)
        p.node('alert_text','text',dict(x=14,y=31,text='Operação insegura',fontSize=30,fill='#ffffff'),alert['id'])
        for key,x,text in [('a',25,'Bacia inferior'),('b',300,'Câmara'),('c',535,'Bacia superior')]:
            p.node('label'+key,'text',dict(x=x,y=286,text=text,fontSize=30,fill=p.ink if style=='blueprint' else '#102a43'))
        targets.update(level=water['id'],position=boat['id'],risk=alert['id'])
    elif kind=='conversation_person':
        long=instance.get('variant')=='long_hair';hair='#503c39' if long else '#263e4d'
        coat='#ae7055' if long else '#397e92';skin='#e7b28e' if long else '#c98d6c'
        p.path('chair','M24 160 Q18 136 42 133 H169 Q190 140 183 166 L174 292 H35 Z','#355365')
        if long:p.path('hair_back','M65 65 Q44 3 106 8 Q166 14 154 96 L161 160 H51 Z',hair)
        p.path('jacket','M55 134 Q96 118 140 135 Q169 151 177 233 L169 294 H33 L35 203 Q33 151 55 134 Z',coat,stroke='#345365',strokeWidth=3)
        p.path('shirt','M82 129 H119 L111 235 H94 Z','#ecf2ef')
        p.path('lapel','M61 137 L85 127 L102 163 L80 186 Z','#6b9eaa' if not long else '#ce9175')
        p.path('lapel2','M120 127 L147 141 L126 185 L109 163 Z','#2c657a' if not long else '#96583f')
        p.rect('neck',84,102,39,34,skin,rx=10)
        p.path('face','M61 47 Q67 19 104 20 Q143 23 146 53 L140 95 Q126 122 103 123 Q76 118 66 94 Z',skin,stroke='#9d6a51',strokeWidth=2)
        p.path('hair','M61 66 Q45 28 78 13 Q124 -1 145 28 L150 65 L135 54 L127 33 Q104 53 68 45 Z',hair)
        p.path('nose','M104 66 L100 85 L112 87','none',stroke='#a36d55',strokeWidth=2)
        for j,x in enumerate((84,123)):
            p.node('eye'+str(j),'ellipse',dict(x=x,y=69,rx=4,ry=3,fill='#263845'))
        brow=p.path('brows','M77 58 Q84 54 92 58 M116 58 Q123 54 131 58','none',stroke=hair,strokeWidth=3)
        brow['states']=[{'when':p.when('engagement','lt',.25),'set':{'d':'M77 54 L92 60 M116 60 L131 54'}}]
        mouth=p.path('mouth','M91 101 Q105 105 119 101','none',stroke='#75473e',strokeWidth=3)
        mouth['states']=[{'when':p.when('engagement','lt',.25),'set':{'d':'M91 105 Q105 93 119 105'}},
                         {'when':p.when('engagement','ge',.65),'set':{'d':'M90 97 Q105 116 120 97'}}]
        p.path('left_arm','M50 153 Q19 170 28 220 L73 238 L84 218 L56 204 L65 167 Z',coat,stroke='#345365',strokeWidth=3)
        arm=p.path('gesture','M147 154 Q169 154 184 181 L203 163 L216 177 Q191 218 174 205 L140 184 Z',coat,stroke='#345365',strokeWidth=3)
        arm['states']=[{'when':p.when('engagement','lt',.25),'set':{'d':'M147 154 Q183 161 185 208 L125 232 L116 210 L160 195 L140 184 Z'}}]
        hand=p.path('hand','M201 163 L205 147 Q209 137 212 144 L212 156 L219 151 L219 172 L214 179 Z',skin)
        hand['states']=[{'when':p.when('engagement','lt',.25),'set':{'d':'M127 211 L108 208 L98 219 L119 232 L130 227 Z'}}]
        p.path('left_hand','M73 219 L93 221 L101 235 L77 241 L68 234 Z',skin)
        p.rect('seam',104,242,4,43,'#345365',rx=2)
        targets={'engagement':mouth['id']}
    elif kind=='evidence_folder':
        p.path('folder','M5 32 H76 L91 46 H224 V150 H5 Z','#ba925f',stroke='#82633d',strokeWidth=3)
        papers=p.node('pages','group',dict(x=18,y=43));p.bind(papers,'y','review',43,5)
        p.rect('page_back',8,6,185,94,'#d4dee5',papers['id'],rx=4)
        p.rect('page',0,0,185,94,'#f8fbfc',papers['id'],rx=4,stroke='#a7bdca',strokeWidth=2)
        for j,w in enumerate((128,150,108)):p.rect('text'+str(j),17,20+j*18,w,4,'#698b9e',papers['id'],rx=2)
        p.path('front','M5 85 L224 74 V151 H5 Z','#d6ae73',stroke='#997549',strokeWidth=3)
        seal=p.node('seal','group',dict(x=168,y=89),visibleWhen=p.when('agreement','ge',1))
        p.node('disc','circle',dict(x=0,y=0,r=24,fill='#288675',stroke='#b4ead9',strokeWidth=3),seal['id'])
        p.path('check','M-12 0 L-3 10 L14 -10','none',seal['id'],stroke='#ffffff',strokeWidth=5)
        p.action(p.rows[0],'inspect')
        targets={'review':papers['id'],'agreement':seal['id']}
    elif kind=='planning_board':
        p.rect('shadow',9,9,448,266,'#74929f',rx=14)
        p.rect('board',0,0,448,266,p.paper,rx=14,stroke='#7695a5',strokeWidth=3)
        for j,x in enumerate((16,157,298)):
            p.rect('column'+str(j),x,45,130,199,'#1a3549' if style=='blueprint' else '#dce8ed',rx=7)
        for j,(x,label) in enumerate(((16,'A fazer'),(157,'Próxima'),(298,'Feito'))):
            p.node('head'+str(j),'text',dict(x=x+5,y=30,text=label,fontSize=28,fill=p.ink))
        for j,slot in enumerate(('plan','execute','review')):
            card=p.node('task'+str(j),'group',dict(x=22,y=58+j*59));p.action(card,slot)
            card['label']=('Etapa 1: planejar','Etapa 2: executar','Etapa 3: revisar')[j]
            card['states']=[{'when':p.when('stage','ge',(j+1)/3),'set':{'x':304}},
                            {'when':p.when('stage','eq',j/3),'set':{'x':163}}]
            p.rect('card'+str(j),0,0,116,49,'#316f86',card['id'],rx=7,stroke='#9fceda',strokeWidth=2)
            p.node('tasktxt'+str(j),'text',dict(x=39,y=36,text='0'+str(j+1),fontSize=32,fill='#ffffff'),card['id'])
        quality=p.path('quality','M380 245 L407 218 L414 225 L387 252 Z','none',stroke='#d09558' if style=='blueprint' else '#9f6127',strokeWidth=4)
        quality['states']=[{'when':p.when('quality','ge',1),'set':{'d':'M380 235 L391 246 L416 218','stroke':'#46b89b' if style=='blueprint' else '#288675'}}]
        targets={'stage':p.id+'_task0','quality':quality['id']}
    elif kind=='time_budget':
        p.rect('top',18,5,164,17,'#638596',rx=6);p.rect('base',18,229,164,17,'#638596',rx=6)
        p.path('glass','M39 24 H161 Q166 77 115 123 Q166 175 161 225 H39 Q34 175 85 123 Q34 77 39 24 Z','#cce6ed',stroke='#608699',strokeWidth=4)
        sand=p.path('upper','M45 40 H155 Q153 81 100 114 Q47 81 45 40 Z','#a56e25')
        sand['states']=[{'when':p.when('remaining','lt',.17),'set':{'d':'M98 112 H102 L100 114 Z'}},
                        {'when':p.when('remaining','lt',.5),'set':{'d':'M75 85 H125 L100 114 Z'}},
                        {'when':p.when('remaining','lt',.84),'set':{'d':'M55 64 H145 Q137 94 100 114 Q63 94 55 64 Z'}}]
        lower=p.path('lower','M48 216 H152 L150 222 H50 Z','#a56e25')
        lower['states']=[{'when':p.when('remaining','lt',.17),'set':{'d':'M44 213 Q100 132 156 213 L153 221 H47 Z'}},
                         {'when':p.when('remaining','lt',.5),'set':{'d':'M46 214 Q100 164 154 214 L153 221 H47 Z'}},
                         {'when':p.when('remaining','lt',.84),'set':{'d':'M48 215 Q100 190 152 215 L152 221 H48 Z'}}]
        p.path('shine','M49 35 Q48 75 81 103 M49 210 Q51 175 79 149','none',stroke='#f4fcff',strokeWidth=5)
        p.rect('post_a',22,24,7,199,'#88a5b2',rx=3);p.rect('post_b',171,24,7,199,'#88a5b2',rx=3)
        targets={'remaining':sand['id']}
    else:raise ValueError('Componente contextual não registrado')
    return p.rows,targets
