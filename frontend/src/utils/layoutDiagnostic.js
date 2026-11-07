// Explicit user-downloaded snapshot for recovery investigation, not telemetry.
export function downloadLayoutDiagnostic(project) {
  const blob=new Blob([JSON.stringify({version:1,projectId:project.id,updatedAt:project.updatedAt,course:project.course})],{type:'application/json'});
  const href=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=href;a.download='scormify-diagnostico-enquadramento.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(href),1000);
}
