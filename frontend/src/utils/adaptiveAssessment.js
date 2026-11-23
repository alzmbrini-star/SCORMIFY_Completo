// Pure rule-based adaptation. No network, generated questions, or bank mutation.
export function createAdaptiveEngine() {
  function level(q) {
    const value=q&&q.difficulty;
    const names={easy:1,facil:1,'fácil':1,medium:2,medio:2,'médio':2,hard:3,dificil:3,'difícil':3};
    return names[String(value).toLowerCase()]||([1,2,3].includes(Number(value))?Number(value):2);
  }
  function topic(q) {return String(q.learningObjective||q.category||(Array.isArray(q.tags)?q.tags:[]).find(t=>t!=='ai-generated')||'').trim().toLowerCase();}
  function start(questions) {
    const result=questions.slice();
    const i=result.findIndex(q=>level(q)===2);
    if(i>0)result.unshift(result.splice(i,1)[0]);
    return result;
  }
  function next(questions,index,correct) {
    const result=questions.slice(),current=result[index];
    if(!current||index>=result.length-1)return result;
    const target=Math.max(1,Math.min(3,level(current)+(correct?1:-1)));
    const eligible=result.slice(index+1).some(q=>correct?level(q)>=level(current):level(q)<=level(current));
    let best=index+1,bestCost=Infinity;
    for(let i=index+1;i<result.length;i++){
      if(eligible && (correct?level(result[i])<level(current):level(result[i])>level(current)))continue;
      const same=topic(current)&&topic(result[i])===topic(current);
      const cost=Math.abs(level(result[i])-target)*2+(!correct&&!same?5:0);
      if(cost<bestCost){best=i;bestCost=cost;}
    }
    if(best!==index+1)result.splice(index+1,0,result.splice(best,1)[0]);
    return result;
  }
  function reinforce(q) {
    return String(q.reinforcement||q.explanation||'Revise o conceito desta questão e o feedback da resposta antes de continuar.');
  }
  return {level,topic,start,next,reinforce};
}
