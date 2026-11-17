import {authHeaders} from '../contexts/AuthContext';

export function previewError(error){
 if(error?.name==='AbortError')return '';
 return error?.previewMessage||'Não foi possível preparar a prévia. Confira sua conexão e tente novamente. O curso não foi alterado.';
}
function fail(message,recreate=false){const error=new Error(message);error.previewMessage=message;error.recreatePreview=recreate;return error;}
async function check(response){
 if(response.ok)return response;
 if([401,403].includes(response.status))throw fail('Sua sessão expirou ou não tem acesso a este curso. Entre novamente antes de abrir a prévia.');
 if(response.status===404)throw fail('O curso ou a tarefa da prévia não foi encontrado. Reabra o curso e tente novamente.',true);
 if(response.status===400){const body=await response.json().catch(()=>({}));throw fail(typeof body.detail==='string'?body.detail:'Esta modalidade não está disponível para este curso.');}
 throw fail('O servidor não conseguiu preparar a prévia agora. Aguarde um pouco e tente novamente; o curso foi preservado.');
}
export function abortableDelay(ms,signal){
 return new Promise((resolve,reject)=>{const abort=()=>{clearTimeout(timer);reject(new DOMException('Cancelado','AbortError'));};const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},ms);if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});});
}
export async function prepareSinglePagePreview(api,id,{signal,onProgress=()=>{},jobId,onJobStarted=()=>{},fetcher=fetch,delay=abortableDelay,now=Date.now}={}){
 let job={jobId};
 if(!jobId){const start=await check(await fetcher(`${api}/api/projects/${encodeURIComponent(id)}/preview-singlepage`,{method:'POST',headers:authHeaders(),signal}));job=await start.json();}
 if(!job.jobId)throw fail('O servidor não retornou a tarefa de prévia. Tente novamente.',true);
 onJobStarted(job.jobId);
 const deadline=now()+600000;let failures=0;
 while(now()<deadline){
  let response;
  try{response=await fetcher(`${api}/api/job/${encodeURIComponent(job.jobId)}`,{headers:authHeaders(),signal});
   if(response.status>=500)throw new Error('temporary');
  }catch(error){if(error.name==='AbortError')throw error;if(++failures>12)throw fail('A conexão com o servidor foi interrompida. Tentar novamente retoma esta mesma prévia, sem gerar outra. O curso foi preservado.');onProgress({message:'Conexão instável; tentando consultar a mesma prévia…'});await delay(Math.min(2000*failures,8000),signal);continue;}
  await check(response);failures=0;const status=await response.json();onProgress(status);
  if(['failed','error'].includes(status.status))throw fail('A geração da prévia falhou. Tente novamente ou consulte o suporte com o horário desta tentativa. Nenhum slide foi alterado.',true);
  if(['completed','done'].includes(status.status)){
   const path=status.result?.downloadUrl;if(!path?.startsWith('/api/exports/'))throw fail('A prévia não retornou um arquivo válido. Tente novamente.');
   const document=await check(await fetcher(`${api}${path}`,{headers:authHeaders(),signal}));const html=await document.text();
   if(!/<(?:!doctype\s+html|html)\b/i.test(html))throw fail('O servidor retornou um conteúdo inválido para a prévia. Tente novamente.');
   return html;
  }
  await delay(2000,signal);
 }
 throw fail('A prévia demorou mais que o esperado. O processamento pode continuar no servidor; tente novamente mais tarde. O curso foi preservado.');
}
