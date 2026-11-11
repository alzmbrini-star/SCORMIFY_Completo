const assert=require('node:assert/strict');
const {indices}=require('../services/export_assets/navigation-window.js');
for(const total of [0,1,2,8,9,10,97,500,10000]){
  const positions=total>0?[0,1,Math.floor(total/2),total-2,total-1]:[0];
  for(const current of positions){
    const list=indices(total,current),numbers=list.filter(x=>x!==null);
    assert(list.length<=9);
    assert.equal(new Set(numbers).size,numbers.length);
    assert(numbers.every(x=>x>=0&&x<total));
    if(total){assert.equal(numbers[0],0);assert.equal(numbers.at(-1),total-1);assert(numbers.includes(Math.min(total-1,Math.max(0,current))));}
    assert.deepEqual(numbers,[...numbers].sort((a,b)=>a-b));
  }
}
assert.deepEqual(indices(3,1),[0,1,2]);
assert.deepEqual(indices(97,7),[0,null,5,6,7,8,9,null,96]);
console.log('Bounded navigation passed for short and very long courses.');
