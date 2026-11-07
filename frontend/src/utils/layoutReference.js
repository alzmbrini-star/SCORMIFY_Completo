// Parse the JSON payload of our own HTML exports; never evaluate their scripts.
export function parseLayoutReference(text) {
  const marker=/\bvar\s+courseData\s*=\s*/g,match=marker.exec(text);
  if(!match) throw new Error('Este arquivo não contém os dados de um curso exportado pelo SCORMIFY.');
  const start=marker.lastIndex;let quoted=false,escape=false,depth=0;
  if(text[start]!=='{') throw new Error('Dados de referência inválidos.');
  for(let i=start;i<text.length;i++) {
    const c=text[i];
    if(quoted){if(escape)escape=false;else if(c==='\\')escape=true;else if(c==='"')quoted=false;continue;}
    if(c==='"')quoted=true;else if(c==='{')depth++;else if(c==='}'&&--depth===0){
      const course=JSON.parse(text.slice(start,i+1));
      if(!Array.isArray(course.slides))throw new Error('Referência sem slides.');
      return course;
    }
  }
  throw new Error('Arquivo de referência incompleto.');
}
