// Build-time only: real Astryx components -> static HTML, no React/CDN in courses.
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {Card} from '@astryxdesign/core/Card';
import {Button} from '@astryxdesign/core/Button';
import {Theme} from '@astryxdesign/core/theme';
import {neutralTheme} from '@astryxdesign/theme-neutral/built';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import postcss from 'postcss';
const target=new URL('../../backend/services/astryx_assets/',import.meta.url);
await mkdir(target,{recursive:true});
const read=path=>readFile(new URL(`node_modules/${path}`,import.meta.url),'utf8');
const card=renderToStaticMarkup(React.createElement(Card,{elevation:'med',padding:6},'@@CONTENT@@'));
const confirm=renderToStaticMarkup(React.createElement(Button,{label:'Verificar resposta',variant:'primary',id:'ax-confirm',type:'button'}));
const reset=renderToStaticMarkup(React.createElement(Button,{label:'Tentar novamente',variant:'secondary',id:'ax-reset',type:'button'}));
const root=renderToStaticMarkup(React.createElement(Theme,{theme:neutralTheme,mode:'light'},'@@CONTENT@@'));
const license=await readFile(new URL('LICENSE.astryx.txt',import.meta.url),'utf8');
const css=[await read('@astryxdesign/core/src/reset.css'),await read('@astryxdesign/core/dist/astryx.css'),await read('@astryxdesign/theme-neutral/dist/theme.css')].join('\n');
if(/@import\s|url\((?!['"]?data:)/i.test(css))throw Error('Styles must be offline: review external references.');
await writeFile(new URL('components.json',target),JSON.stringify({version:'0.7.16',root,card,confirm,reset}));
await writeFile(new URL('astryx.css',target),`/* Astryx 0.7.16, Meta Platforms, MIT; see LICENSE.txt */\n${css}`);
await writeFile(new URL('LICENSE.txt',target),license);
// Course lessons use Theme and Card, not all 150+ components. Prune with a CSS
// parser and retain the transitive closure of referenced tokens. Never use the
// old whole-document "outline" regex that corrupts layered stylesheets.
const classes=new Set([...`${root}${card}`.matchAll(/class="([^"]+)"/g)].flatMap(m=>m[1].split(/\s+/)));
const sheet=postcss.parse(css);
sheet.walkComments(n=>n.remove());
sheet.walkRules(rule=>{
 const names=[...rule.selector.matchAll(/\.([a-zA-Z_][\w-]*)/g)].map(m=>m[1]);
 if(names.length&&!names.some(n=>classes.has(n)))rule.remove();
});
const refs=value=>[...value.matchAll(/var\(\s*(--[\w-]+)/g)].map(m=>m[1]);
const needed=new Set(['--font-family','--color-text-primary','--color-background-body']);
sheet.walkDecls(d=>{if(!d.prop.startsWith('--'))for(const v of refs(d.value))needed.add(v);});
let changed=true;
while(changed){changed=false;sheet.walkDecls(d=>{if(needed.has(d.prop))for(const v of refs(d.value)){if(!needed.has(v)){needed.add(v);changed=true;}}});}
sheet.walkDecls(d=>{if(d.prop.startsWith('--')&&!needed.has(d.prop))d.remove();});
sheet.walkAtRules(n=>{if(n.name==='property'&&!needed.has(n.params))n.remove();});
for(let i=0;i<4;i++)sheet.walk(n=>{if(n.nodes&&!n.nodes.length)n.remove();});
sheet.walk(n=>{n.raws.before='';if(n.type==='decl')n.raws.between=':';else if(n.nodes){n.raws.between='';n.raws.after='';n.raws.semicolon=false;}});
const compact=sheet.toString();
if(Buffer.byteLength(compact)>45000)throw Error('Astryx lesson CSS exceeded the per-slide storage budget.');
await writeFile(new URL('lesson.css',target),'/* Astryx 0.7.16 Theme/Card subset, MIT; see LICENSE.txt */\n'+compact);
console.log(`Offline lesson CSS: ${Buffer.byteLength(compact)} bytes (full laboratory CSS unchanged).`);
console.log('Astryx 0.7.16: static Theme, Card, Button and offline CSS generated.');
