(function(root){'use strict';
  // Bounded presentation only. No completion, score or slide-order changes.
  function indices(total,current){
    total=Math.max(0,Math.floor(Number(total)||0));current=Math.max(0,Math.min(total-1,Math.floor(Number(current)||0)));
    if(total<=9)return Array.from({length:total},function(_,i){return i;});
    var start=Math.max(1,Math.min(current-2,total-6)),end=Math.min(total-2,start+4),items=[0];
    if(start>1)items.push(null);
    for(var i=start;i<=end;i++)items.push(i);
    if(end<total-2)items.push(null);
    items.push(total-1);return items;
  }
  root.ScormifyNavigation={indices:indices};
  if(typeof module!=='undefined'&&module.exports)module.exports={indices:indices};
})(typeof window!=='undefined'?window:globalThis);
