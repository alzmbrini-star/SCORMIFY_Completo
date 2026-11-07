import {parseLayoutReference} from './layoutReference';
test('parses JSON only, including braces and escaped quotes in HTML strings',()=>{
 const c={slides:[{elements:[{htmlContent:'<p>{x} "hello"</p>'}]}]};
 expect(parseLayoutReference('<script>var courseData = '+JSON.stringify(c)+'; throw new Error("never run");</script>')).toEqual(c);
});
test('does not execute arbitrary javascript or accept incomplete references',()=>{
 expect(()=>parseLayoutReference('var courseData = alert("no")')).toThrow();
 expect(()=>parseLayoutReference('var courseData = {"slides":[')).toThrow();
 expect(()=>parseLayoutReference('var courseData = {"foo":1}')).toThrow();
});
