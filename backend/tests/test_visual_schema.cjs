const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),path=require('node:path');
const Ajv=require('../../frontend/node_modules/.pnpm/ajv@8.20.0/node_modules/ajv');
const backend=path.resolve(__dirname,'..'),python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const packet=JSON.parse(execFileSync(python,['-c',`import sys,json,copy
sys.path.insert(0,'tests')
from test_visual_teaching import teaching_fixture,scene_plan
from services.rule_simulators import validate_rules
from services.rule_visuals import validate_visual
from services.visual_schema import scene_schema,plan_schema,review_schema,omit_null_fields,format_for_stage
raw=teaching_fixture();data=validate_rules(raw);ids=[v['id'] for v in data['variables']]
schema=scene_schema(ids,[a['id'] for a in data['actions']])
visual=copy.deepcopy(raw['visual'])
for n in visual['nodes']:
 definition=schema['$defs']['node_'+n['type']]['properties']
 n['attrs']={key:n['attrs'].get(key) for key in definition['attrs']['properties']}
 n.setdefault('bindings',[]);n.setdefault('states',[]);n.setdefault('parent',None);n.setdefault('visibleWhen',None);n.setdefault('action',None)
 for state in n['states']:
  state['set']={key:state['set'].get(key) for key in definition['states']['items']['properties']['set']['properties']}
assert validate_visual(omit_null_fields(visual),data)==data['visual']
assert format_for_stage('gemini','test','-composition',data,{}) is None
assert format_for_stage('openai','gpt-4o','-composition',data,{})['json_schema']['strict'] is True
print(json.dumps({'schema':schema,'visual':visual,'planSchema':plan_schema(ids),'plan':scene_plan(),'reviewSchema':review_schema([n['id'] for n in visual['nodes']])}))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend},maxBuffer:5000000}));
const ajv=new Ajv({strict:false,allErrors:true}),check=ajv.compile(packet.schema);
assert.ok(check(packet.visual),JSON.stringify(check.errors));
for(const mutate of [v=>{v.nodes[5].bindings[0].property='fill';},v=>{v.nodes[5].bindings[0].var='invented';},v=>{v.nodes[5].attrs.script='alert(1)';}]){
 const visual=JSON.parse(JSON.stringify(packet.visual));mutate(visual);assert.equal(check(visual),false);
}
assert.ok(ajv.compile(packet.planSchema)(packet.plan));
assert.ok(ajv.compile(packet.reviewSchema)({approved:true,summary:'Relações coerentes.',issues:[]}));
function strictObjects(s){if(!s||typeof s!=='object')return;if(s.type==='object'){assert.equal(s.additionalProperties,false);assert.deepEqual([...s.required].sort(),Object.keys(s.properties).sort());}for(const v of Object.values(s)){if(Array.isArray(v))v.forEach(strictObjects);else if(v&&typeof v==='object')strictObjects(v);}}
strictObjects(packet.schema);strictObjects(packet.planSchema);strictObjects(packet.reviewSchema);
console.log('PASS constrained scene vocabulary: typed shape-specific attributes/bindings, exact variable IDs, recursive predicates, strict objects, null round-trip and provider fallback');
