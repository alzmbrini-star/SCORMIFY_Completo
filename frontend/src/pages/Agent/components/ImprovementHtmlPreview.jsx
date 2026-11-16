import React from 'react';

export function previewDocument(html){
 const policy="<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: https: http:; media-src data: https: http:; frame-src https:; connect-src 'none'; form-action 'none'; base-uri 'none'\">";
 if(/<head(?:\s[^>]*)?>/i.test(html))return html.replace(/<head(?:\s[^>]*)?>/i,m=>m+policy);
 return `<!DOCTYPE html><html><head><meta charset="utf-8">${policy}<style>body{margin:0;padding:12px;font-family:Arial,sans-serif;color:#f8fafc;background:#0f172a;overflow:auto}button{cursor:pointer}</style></head><body>${html}</body></html>`;
}
export default function ImprovementHtmlPreview({htmlParts,label}){
 const parts=(htmlParts||[]).filter(v=>typeof v==='string'&&v.trim());
 if(!parts.length)return <p>Sem conteúdo de prévia.</p>;
 return <div className="space-y-2">{parts.map((html,i)=>/<[a-z!][\s\S]*>/i.test(html)?<iframe key={i} title={parts.length===1?label:`${label} — ${i+1}`} srcDoc={previewDocument(html)} sandbox="allow-scripts" referrerPolicy="no-referrer" className="w-full rounded-lg border border-slate-700 bg-slate-900" style={{height:560}}/>:<p key={i} className="text-sm whitespace-pre-wrap">{html}</p>)}</div>;
}
