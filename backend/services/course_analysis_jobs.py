"""Liveness of analysis workers, separate from the immutable source course."""
from datetime import datetime, timezone


def interrupted(cached, deployment_revision='', now=None):
    if not cached.get('runId'):
        return True  # A pre-lease job cannot survive deployment of this worker.
    if deployment_revision and cached.get('deploymentRevision') != deployment_revision:
        return True
    try:
        heartbeat = datetime.fromisoformat((cached.get('heartbeatAt') or cached['updatedAt']).replace('Z', '+00:00'))
        return ((now or datetime.now(timezone.utc)) - heartbeat).total_seconds() > 120
    except (KeyError, ValueError, TypeError):
        return True


INTERRUPTED_MESSAGE = ('A execução anterior foi interrompida ou o servidor reiniciou. '
    'Use Retomar análise para reaproveitar as leituras válidas e tentar somente as pendentes. '
    'O curso não foi alterado.')
