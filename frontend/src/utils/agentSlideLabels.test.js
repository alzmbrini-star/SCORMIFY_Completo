import {agentSlideLabel} from './agentSlideLabels';

test('structure displays Portuguese labels without changing technical IDs',()=>{
  const types=['content','title','summary','game','quiz','simulator','scenario','avatar_scene','infographic','flashcard','timeline','case_study'];
  expect(types.map(agentSlideLabel)).toEqual(['Conteúdo','Capa','Resumo','Jogo','Questionário','Simulador','Cenário de decisão','Cena com avatar','Infográfico','Cartões de revisão','Linha do tempo','Estudo de caso']);
  expect(types[3]).toBe('game');
  expect(agentSlideLabel('future_type')).toBe('Atividade');
});
