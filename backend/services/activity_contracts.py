"""Structural fields belong to the player; the model authors contextual content."""
STRATEGIES = {'risky': 0, 'partial': 1, 'grounded': 2}


def strategy_choices(value, position=0):
    if not isinstance(value, dict):
        return value  # Compatibility: legacy arrays are still strictly validated.
    if set(value) != set(STRATEGIES):
        raise ValueError('As estratégias devem conter exatamente risky, partial e grounded')
    if any(not isinstance(item, dict) for item in value.values()):
        raise ValueError('Cada estratégia deve ser um objeto com fala, reação e consequência')
    # Never infer quality from arbitrary list position or fabricate alternatives.
    keys = list(STRATEGIES)
    offset = position % len(keys)
    keys = keys[offset:] + keys[:offset]
    if position % 2: keys.reverse()
    return [dict(value[key], quality=STRATEGIES[key]) for key in keys]
