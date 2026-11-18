"""Conservative classification of advice only; never converts authored resources."""
import copy
import re
import unicodedata


def classify_suggestion(item):
    out = copy.deepcopy(item)
    if out.get('type') not in ('quiz', 'interactive_assessment'):
        return out
    text = ' '.join(str(out.get(k) or '') for k in ('description', 'suggestion'))
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    # A question set can mention a scenario without being a branching experience.
    branching = re.search(r'caminh\w*|ramifica\w*|desfechos? diferentes|branching', text)
    decisions = re.search(r'cenarios? de decisao|tomar decisoes|escolha.*consequenc|decisoes.*consequenc', text)
    if branching and decisions:
        out['classificationNote'] = 'Classificação ajustada: caminhos e consequências usam Cenário de decisão, não um banco de questões.'
        out['originalSuggestedType'] = out.get('originalSuggestedType', out['type'])
        out['type'] = 'scenario'
    return out


def normalize_analysis(result):
    out = copy.deepcopy(result or {})
    out['improvements'] = [classify_suggestion(i) for i in out.get('improvements', []) if isinstance(i, dict)]
    for row in (out.get('visualAnalysis') or {}).get('slides', []):
        row['improvements'] = [classify_suggestion(i) for i in row.get('improvements', []) if isinstance(i, dict)]
    return out
