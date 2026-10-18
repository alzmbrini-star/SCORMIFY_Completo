"""Safe, actionable errors for background storyboard generation."""


class StoryboardActivityError(RuntimeError):
    def __init__(self, activity_type, title, cause):
        self.activity_type = activity_type
        self.activity_title = str(title or 'Atividade')[:150]
        self.cause = cause
        super().__init__(f'{activity_type}: {self.activity_title}: {type(cause).__name__}: {cause}')


def storyboard_error_message(error):
    cause = error.cause if isinstance(error, StoryboardActivityError) else error
    raw = str(cause).lower()
    activity = (f'O {error.activity_type} “{error.activity_title}”' if isinstance(error, StoryboardActivityError)
                else 'O storyboard')
    if isinstance(cause, TimeoutError) or 'timed out' in raw or 'timeout' in raw:
        return activity + ' excedeu o tempo de resposta da IA. Tente novamente; sua estrutura foi preservada.'
    if any(term in raw for term in ('quota', 'budget', 'insufficient_quota', 'billing')):
        return 'A cota ou o saldo do provedor de IA foi atingido. Verifique o faturamento da integração antes de tentar novamente.'
    if any(term in raw for term in ('502', 'badgateway', '503', 'service unavailable')):
        return 'O serviço de IA está temporariamente indisponível. Tente novamente em alguns minutos.'
    if isinstance(error, StoryboardActivityError) and isinstance(cause, ValueError):
        return activity + ' não passou na validação: ' + str(cause)[:400] + '. Sua estrutura foi preservada.'
    return activity + ' não pôde ser gerado. Tente novamente; se persistir, consulte os logs do serviço. Sua estrutura foi preservada.'
