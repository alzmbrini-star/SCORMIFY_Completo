import './scenarioPresentation';
// DOM-only runtime: no React renderer or extra test dependency is required.
const within=root=>{
 const role=(kind,name)=>Array.from(root.querySelectorAll(({button:'button',dialog:'[role="dialog"]',heading:'h1,h2,h3,h4,h5,h6'})[kind])).find(e=>!name||(e.getAttribute('aria-label')||e.textContent)===name);
 return {getByRole:(kind,opts={})=>{const e=role(kind,opts.name);if(!e)throw new Error('Missing '+kind+' '+opts.name);return e;},queryByRole:(kind,opts={})=>role(kind,opts.name)||null,getByText:text=>{const e=Array.from(root.querySelectorAll('*')).find(e=>e.textContent===text);if(!e)throw new Error('Missing '+text);return e;}};
};
const screen=within(document.body),fireEvent={click:e=>{e.focus();e.click();},keyDown:(e,opts)=>e.dispatchEvent(new KeyboardEvent('keydown',{...opts,bubbles:true}))};

const scenario={title:'Distribuição de tarefas',context:'Objetivo: Distribuir as tarefas com equilíbrio.\n\n- Prazo curto\n- Manter **qualidade**\n<img src=x onerror=alert(1)>',characters:[{name:'Carlos Silva',role:'Gerente de Projetos',personality:'Pragmático e atento à equipe.'},{name:'Ana Costa',role:'Desenvolvedora Sênior',personality:'Criativa e proativa.'}],nodes:[{id:'start',narrative:'Carlos recebe um projeto urgente.',choices:[{id:'a',text:'Conversar com a equipe',feedback:'Boa escolha',is_optimal:true,next_node_id:'end'}]},{id:'end',is_ending:true}]};
let host,controller;
beforeEach(()=>{const error=console.error;jest.spyOn(console,'error').mockImplementation((...args)=>{if(String(args[0]).includes('Could not parse CSS stylesheet'))return;error(...args);});host=document.createElement('div');document.body.append(host);});
afterEach(()=>{controller?.destroy();host.remove();jest.restoreAllMocks();});
test('Context has smaller scoped typography, sections, bold names and indented lists without changing decisions',()=>{
 const original=JSON.stringify(scenario),complete=jest.fn();controller=window.ScormifyScenario.mount(host,scenario,{onComplete:complete});
 fireEvent.click(screen.getByRole('button',{name:'Consultar contexto'}));
 const dialog=screen.getByRole('dialog',{name:'Contexto da situação'});
 expect(dialog.classList.contains('sc-context-card')).toBe(true);
 ['Contexto geral','Situação desta cena','Personagens envolvidos'].forEach(name=>expect(within(dialog).getByRole('heading',{name})).toBeTruthy());
 expect(within(dialog).getByText('Carlos Silva').tagName).toBe('STRONG');
 expect(within(dialog).getByText('Objetivo:').tagName).toBe('STRONG');
 expect(within(dialog).getByText('qualidade').tagName).toBe('STRONG');
 expect(within(dialog).getByText('Prazo curto').tagName).toBe('LI');
 expect(within(dialog).getByText('<img src=x onerror=alert(1)>')).toBeTruthy();
 expect(dialog.querySelector('img')).toBeNull();
 expect(controller.state.view().history).toHaveLength(0);expect(complete).not.toHaveBeenCalled();
 fireEvent.click(within(dialog).getByRole('button',{name:'Fechar'}));
 expect(screen.queryByRole('dialog')).toBeNull();
 expect(document.activeElement.textContent).toBe('Consultar contexto');
 expect(JSON.stringify(scenario)).toBe(original);
 expect(window.ScormifyScenario.css).toContain('.sc-context-card{font-size:.86em');
});
test('Context follows font/contrast controls, current scene and supports dismissal without saving changes',()=>{
 controller=window.ScormifyScenario.mount(host,scenario);fireEvent.click(screen.getByRole('button',{name:'A+'}));
 const font=host.style.getPropertyValue('--sc-font');fireEvent.click(screen.getByRole('button',{name:'Contraste'}));
 fireEvent.click(screen.getByRole('button',{name:'Consultar contexto'}));
 expect(host.classList.contains('sc-dark')).toBe(true);expect(host.style.getPropertyValue('--sc-font')).toBe(font);
 expect(screen.getByRole('dialog').textContent).toContain('Carlos recebe um projeto urgente.');
 fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'});expect(screen.queryByRole('dialog')).toBeNull();
 expect(controller.state.view().node.id).toBe('start');
});
test('Empty optional context is handled without empty sections',()=>{
 controller=window.ScormifyScenario.mount(host,{title:'Sem contexto',nodes:[{id:'s',choices:[]}]});
 fireEvent.click(screen.getByRole('button',{name:'Consultar contexto'}));
 expect(screen.getByRole('dialog').textContent).toContain('Nenhum contexto adicional informado.');
 expect(screen.queryByRole('heading',{name:'Personagens envolvidos'})).toBeNull();
});
