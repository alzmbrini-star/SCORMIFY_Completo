/** Production must not initialize the inherited invalid analytics account. */
const fs=require('fs'),path=require('path'),vm=require('vm');
test('production inline startup does not load legacy analytics or visual-edit helpers',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../public/index.html'),'utf8').replaceAll('%NODE_ENV%','production');
  const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
  const append=jest.fn(),create=jest.fn();
  const scope={window:{self:{},top:{}},document:{createElement:create,head:{appendChild:append}},setTimeout:jest.fn()};
  scripts.forEach(code=>vm.runInNewContext(code,scope));
  expect(create).not.toHaveBeenCalled();expect(append).not.toHaveBeenCalled();expect(scope.window.posthog).toBeUndefined();
  expect(html).not.toMatch(/<script src="https:\/\/assets.emergent.sh/);
  expect(html).toContain('vlibras-plugin.js');
});
