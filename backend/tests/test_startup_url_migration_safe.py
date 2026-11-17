"""Startup migration is streamed and only ever writes explicit URL leaves."""
import ast
import logging
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest

def helper(projects):
    tree=ast.parse((Path(__file__).resolve().parents[1]/'server.py').read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_run_migrate_urls')
    class Cursor:
        batch=None
        def batch_size(self,size):self.batch=size;return self
        def __aiter__(self):return self
        async def __anext__(self):
            try:return next(self.items)
            except StopIteration:raise StopAsyncIteration
    cursor=Cursor();cursor.items=iter(projects)
    collection=SimpleNamespace(find=lambda *a,**k:cursor,update_one=AsyncMock())
    scope={'db':SimpleNamespace(projects=collection),'logger':logging.getLogger('test'),'re':re}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<migration>','exec'),scope)
    return scope['_run_migrate_urls'],collection,cursor

@pytest.mark.asyncio
async def test_only_explicit_changed_urls_are_written_not_partial_course():
    fn,collection,cursor=helper([{'id':'p','course':{'slides':[{'backgroundImage':'https://old.invalid/api/projects/p/assets/bg.png','elements':[
       {'type':'html','htmlContent':'<img src="https://old.invalid/api/projects/p/assets/x.png">'},
       {'type':'image','src':'https://old.invalid/api/projects/p/assets/y.png'}]}]}}])
    await fn()
    assert cursor.batch==1
    updates=collection.update_one.await_args.args[1]['$set']
    assert set(updates)=={'course.slides.0.backgroundImage','course.slides.0.elements.0.htmlContent','course.slides.0.elements.1.src'}
    assert 'course' not in updates
    assert updates['course.slides.0.elements.1.src']=='/api/projects/p/assets/y.png'
    guard=collection.update_one.await_args.args[0]
    assert guard['course.slides.0.elements.1.src']=='https://old.invalid/api/projects/p/assets/y.png'

@pytest.mark.asyncio
async def test_already_relative_course_has_no_startup_write():
    fn,collection,cursor=helper([{'id':'p','course':{'slides':[{'elements':[{'type':'image','src':'/api/projects/p/assets/y.png'}]}]}}])
    await fn();collection.update_one.assert_not_awaited()
