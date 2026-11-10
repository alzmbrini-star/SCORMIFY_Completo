import {mergeRunwayProject} from './runwayJobs';
test('merge replaces only Runway slots, preserving unsaved layout and other elements',()=>{
  const text={id:'text',type:'text',text:'Edição não salva'};
  const prior={id:'p1',course:{slides:[{id:'s1',elements:[text,{id:'job',x:35,y:42,width:700,height:400,htmlContent:'<div data-runway-job="job">'}]}]}};
  const saved={id:'p1',runwayPending:[{id:'job',status:'completed'}],course:{slides:[{id:'s1',elements:[{id:'text',text:'Antigo'},{id:'job',provider:'runway',src:'/video.mp4',x:0}]}]}};
  const next=mergeRunwayProject(prior,saved);
  expect(next.course.slides[0].elements[0]).toBe(text);
  expect(next.course.slides[0].elements[1]).toMatchObject({src:'/video.mp4',x:35,width:700});
  expect(prior.course.slides[0].elements[1].src).toBeUndefined();
  expect(mergeRunwayProject(prior,{id:'other'})).toBe(prior);
});
