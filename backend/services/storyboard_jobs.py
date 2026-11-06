"""Durable storyboard leases and input-scoped, immutable batch checkpoints.

No queue/provider credentials required. Mongo is the source of truth; no automatic
AI restart on reads. A new POST is needed to resume an interrupted run.
"""
import asyncio
import copy
import hashlib
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

LEASE_SECONDS = 120
HEARTBEAT_SECONDS = 20
INTERRUPTED_MESSAGE = ('A geração foi interrompida ou perdeu a conexão com o servidor. '
                       'Sua estrutura e os lotes concluídos salvos foram preservados. '
                       'Clique em Aprovar e Gerar Storyboard para retomar. '
                       'Execuções antigas, sem lotes salvos, precisarão refazer o Storyboard.')


class StoryboardLeaseLost(RuntimeError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def input_fingerprint(content, structure, config):
    from services.agent_language import normalize_structure_language
    payload = {'version': 1, 'content': content,
               'structure': normalize_structure_language(structure, config), 'config': config}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), default=str).encode()).hexdigest()


def run_is_live(run, now=None):
    expires = (run or {}).get('leaseUntil')
    if isinstance(expires, datetime):
        expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
    return bool(run and run.get('status') == 'running' and isinstance(expires, datetime)
                and expires > (now or utcnow()))


def recover_session_view(session, run):
    """Read-only recovery view; don't modify persisted drafts or bill providers."""
    result = copy.deepcopy(session)
    if result.get('step') == 'storyboarding' and not run_is_live(run):
        result.update(step='structured', error=INTERRUPTED_MESSAGE, storyboardProgress=None,
                      storyboardRecovery={'status': 'interrupted',
                                          'savedBatches': len((run or {}).get('completedBatches') or [])})
    return result


def acquire_run(database, session_id, fingerprint, force=False, now=None):
    now = now or utcnow()
    previous = database.agent_storyboard_runs.find_one({'_id': session_id}) or {}
    if run_is_live(previous, now):
        return None
    cache_key = (previous.get('cacheKey') if previous.get('fingerprint') == fingerprint else None) or fingerprint
    if force:
        cache_key = fingerprint + ':' + uuid.uuid4().hex
    run = {'runId': uuid.uuid4().hex, 'fingerprint': fingerprint, 'cacheKey': cache_key,
           'status': 'running', 'leaseUntil': now + timedelta(seconds=LEASE_SECONDS),
           'updatedAt': now, 'completedBatches': (previous.get('completedBatches') or [])
           if previous.get('cacheKey') == cache_key else []}
    try:
        claimed = database.agent_storyboard_runs.find_one_and_update(
            {'_id': session_id, '$or': [{'status': {'$ne': 'running'}},
                                      {'leaseUntil': {'$lte': now}}, {'leaseUntil': {'$exists': False}}]},
            {'$set': run}, upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        return None  # Another request won the unique session lease.
    return claimed


class BatchStore:
    def __init__(self, database, session_id, run):
        self.db, self.session_id, self.run = database, session_id, run
        self.stop = threading.Event()
        self.lost = threading.Event()

    def owner_filter(self):
        return {'_id': self.session_id, 'runId': self.run['runId'], 'status': 'running'}

    def renew(self):
        now = utcnow()
        result = self.db.agent_storyboard_runs.update_one(
            dict(self.owner_filter(), leaseUntil={'$gt': now}),
            {'$set': {'leaseUntil': now + timedelta(seconds=LEASE_SECONDS), 'updatedAt': now}})
        if not result.matched_count:
            self.lost.set()
            raise StoryboardLeaseLost('A execução perdeu sua reserva. Retome a geração pelo Agente.')

    def check(self):
        if self.lost.is_set():
            raise StoryboardLeaseLost('Esta execução foi interrompida; nenhum lote será sobrescrito.')
        self.renew()

    def _key(self, index):
        return hashlib.sha256((self.session_id + ':' + self.run['cacheKey'] + ':' + str(index)).encode()).hexdigest()

    async def load(self, index, source_batch):
        def read():
            self.check()
            saved = self.db.agent_storyboard_batches.find_one({'_id': self._key(index)})
            if not saved or len(saved.get('slides') or []) != len(source_batch):
                return None
            ids = [s.get('id') for s in source_batch]
            if saved.get('sourceIds') != ids:
                return None
            return copy.deepcopy(saved['slides'])
        return await asyncio.to_thread(read)

    async def save(self, index, source_batch, slides):
        def write():
            self.check()
            if len(slides) != len(source_batch):
                raise ValueError('O lote do Storyboard está incompleto e não pode ser salvo.')
            self.db.agent_storyboard_batches.update_one(
                {'_id': self._key(index)}, {'$setOnInsert': {
                    'sessionId': self.session_id, 'cacheKey': self.run['cacheKey'],
                    'batch': index, 'sourceIds': [s.get('id') for s in source_batch],
                    'slides': copy.deepcopy(slides), 'createdAt': utcnow()}}, upsert=True)
            self.db.agent_storyboard_runs.update_one(self.owner_filter(), {'$addToSet': {'completedBatches': index}})
        await asyncio.to_thread(write)

    def heartbeat(self):
        while not self.stop.wait(HEARTBEAT_SECONDS):
            try:
                self.renew()
            except Exception:
                # Stop accepting writes if Mongo cannot confirm ownership.
                self.lost.set()
                return

    def __enter__(self):
        self.thread = threading.Thread(target=self.heartbeat, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()

    def finish(self, status):
        self.db.agent_storyboard_runs.update_one(self.owner_filter(),
            {'$set': {'status': status, 'updatedAt': utcnow(), 'leaseUntil': utcnow()}})
