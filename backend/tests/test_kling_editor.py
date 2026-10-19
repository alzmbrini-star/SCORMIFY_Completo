import ast
import copy
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from services.kling_editor import editor_video_placeholder


class HTTPError(Exception):
    def __init__(self, status, detail):
        self.status_code, self.detail = status, detail


def route_function(name, values):
    path=Path(__file__).resolve().parents[1]/'routes/kling.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
    fn.decorator_list=[]
    namespace={'Request':object,'Depends':lambda x:None,'require_auth':None,
               'HTTPException':HTTPError,'uuid':uuid,'_now':lambda:'now',**values}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[name]


class KlingEditorTests(unittest.IsolatedAsyncioTestCase):
    def test_slots_are_unique_bounded_and_do_not_include_prompt_html(self):
        for ratio in ('16:9','9:16','1:1'):
            slot, marker=editor_video_placeholder({'width':1920,'height':820},{'aspectRatio':ratio,'duration':10,'prompt':'<script>bad()</script>'})
            self.assertIn(f'data-kling-slide="{marker}"',slot['htmlContent'])
            self.assertNotIn('bad()',slot['htmlContent'])
            self.assertGreaterEqual(slot['x'],0)
            self.assertLessEqual(slot['x']+slot['width'],1920)
            self.assertLessEqual(slot['y']+slot['height'],820)
        self.assertNotEqual(editor_video_placeholder({}, {})[1],editor_video_placeholder({}, {})[1])
        with self.assertRaises(ValueError):editor_video_placeholder({}, {'duration':500})

    async def test_generation_persists_slot_and_submitting_state_before_provider_call(self):
        calls=[]
        class Collection:
            async def update_one(self, query, values):
                calls.append(copy.deepcopy(values))
        async def load(project_id,user):
            return {'course':{'slides':[{'id':'s1','elements':[]}]},'klingPending':[]}
        async def submit(project_id,item):
            self.assertEqual(calls[-1]['$push']['klingPending']['status'],'submitting')
            self.assertIn('course.slides.0.elements',calls[-1]['$push'])
            self.assertEqual(item['placeholderId'],calls[-1]['$push']['klingPending']['placeholderId'])
            return {'taskId':'mock-task','status':'submitted'}
        class Request:
            async def json(self):return {'projectId':'p1','slideId':'s1','prompt':'Cena educativa','insertPlaceholder':True,'duration':10}
        fn=route_function('kling_generate',{'db':SimpleNamespace(projects=Collection()),
             'load_authorized_project':load,'kling_ai':SimpleNamespace(is_configured=lambda:True),
             '_submit_pending':submit,'_safe_error':lambda exc:exc})
        result=await fn(Request(),{})
        self.assertEqual(result['taskId'],'mock-task')
        self.assertEqual(result['placeholder']['duration'],10)

    async def test_existing_active_job_rejected_without_resubmitting(self):
        async def load(*args):return {'course':{'slides':[{'id':'s1'}]},'klingPending':[{'slideId':'s1','status':'processing'}]}
        class Request:
            async def json(self):return {'projectId':'p1','slideId':'s1','prompt':'Cena'}
        fn=route_function('kling_generate',{'load_authorized_project':load,'kling_ai':SimpleNamespace(is_configured=lambda:True)})
        with self.assertRaises(HTTPError) as error:await fn(Request(),{})
        self.assertEqual(error.exception.status_code,409)

    async def test_old_completed_job_cannot_replace_new_editor_slot_by_fallback(self):
        slot,marker=editor_video_placeholder({}, {})
        class Collection:
            async def find_one(self,*args):return {'course':{'slides':[{'elements':[slot]}]}}
            async def update_one(self,*args):raise AssertionError('Old task must not replace new Editor slot')
        fn=route_function('_replace_placeholder',{'db':SimpleNamespace(projects=Collection())})
        self.assertFalse(await fn('p1','old-marker','old.mp4',0))

    async def test_completed_video_keeps_slot_id_and_existing_geometry(self):
        slot,marker=editor_video_placeholder({}, {})
        changes=[]
        class Collection:
            async def find_one(self,*args):return {'course':{'slides':[{'elements':[slot]}]}}
            async def update_one(self,q,values):changes.append(values)
        fn=route_function('_replace_placeholder',{'db':SimpleNamespace(projects=Collection())})
        self.assertTrue(await fn('p1',marker,'new.mp4',None))
        video=changes[0]['$set']['course.slides.0.elements.0']
        self.assertEqual(video['id'],slot['id'])
        self.assertEqual(video['width'],slot['width'])
        self.assertEqual(video['src'],'new.mp4')
        self.assertTrue(video['controls'])


if __name__ == '__main__':unittest.main()
