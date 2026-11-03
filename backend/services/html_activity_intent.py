"""Deterministic activity routing, independent of course subject and AI calls."""
import re,unicodedata


def html_activity_kind(prompt,activity_type='simulation'):
    if activity_type=='visualization':return 'visualization'
    text=''.join(c for c in unicodedata.normalize('NFKD',str(prompt or '').lower()) if not unicodedata.combining(c))
    if re.search(r'estudos?\s+de\s+caso|analise\s+de\s+caso|case\s+stud(?:y|ies)',text):return 'case-study'
    if re.search(r'\bsimul(?:adores?|acao|ations?|ators?)\b',text):return 'simulation'
    # The Guiado form describes the feature as a visual demonstration. It must
    # not require the author to know the internal magic word "simulador".
    if re.search(r'\b(?:demonstracao|demonstration|animacao|visualizacao)\b[^.!?\n]{0,80}\b(?:visual|guiad[ao]|didatic[ao]|guided|didactic)\b',text):return 'simulation'
    if re.search(r'\b(?:guided|didactic)\s+(?:visual\s+)?demonstration\b',text):return 'simulation'
    return 'html'
