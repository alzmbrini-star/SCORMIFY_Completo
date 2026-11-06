const labels = {
  content: 'Conteúdo', title: 'Capa', summary: 'Resumo', quiz: 'Questionário',
  game: 'Jogo', simulator: 'Simulador', scenario: 'Cenário de decisão',
  avatar_scene: 'Cena com avatar', infographic: 'Infográfico',
  flashcard: 'Cartões de revisão', timeline: 'Linha do tempo',
  case_study: 'Estudo de caso',
};

// Labels only: the API and generation engine retain their original type IDs.
export function agentSlideLabel(type) {
  return labels[type] || 'Atividade';
}
