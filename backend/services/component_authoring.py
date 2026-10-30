"""Deterministic authoring bridge. Never accepts or executes authored HTML."""
import copy
import json
from html.parser import HTMLParser


def read_model(source):
    if not isinstance(source, str) or len(source) > 120000:
        raise ValueError('Modelo de origem inválido ou maior que 120 KB')
    raw = json.loads(source)
    if not isinstance(raw, dict):
        raise ValueError('Use um simulador do motor de regras')
    return raw


def compose(source, project):
    from services.rule_simulators import validate_rules, render_rules
    raw = read_model(source)
    # Ignore only presentation; every rule is revalidated and preserved.
    for key in ('visual', 'visualProject', 'visualNotice'):
        raw.pop(key, None)
    spec = validate_rules(raw)
    spec['visualProject'] = copy.deepcopy(project)
    return {'html': render_rules(spec)}


class ModelParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'scormify-simulator-plan':
            self.count += 1
            self.active = True

    def handle_data(self, value):
        if self.active:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False


def stored_model(html):
    if not isinstance(html, str) or len(html) > 1500000:
        raise ValueError('Simulador armazenado inválido')
    parser = ModelParser()
    parser.feed(html)
    if parser.count != 1:
        raise ValueError('Este item ainda não utiliza o motor de regras compatível')
    return read_model(''.join(parser.parts))


def same_rules(first, second):
    ignored = {'visual', 'visualProject', 'visualNotice', 'checks', 'verification'}
    return {k:v for k,v in first.items() if k not in ignored} == {k:v for k,v in second.items() if k not in ignored}
