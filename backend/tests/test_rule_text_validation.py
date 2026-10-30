import asyncio
import copy
import json
import unittest
from unittest.mock import AsyncMock, patch
from services.rule_simulators import validate_rules, generate_rule_simulator, RuleTextError
from test_process_demo import process_demo
from test_rule_simulators import fixtures


class RuleTextValidation(unittest.TestCase):
    def test_disabled_demo_failure_message_is_optional_without_mutating_source(self):
        for message in ('', '  ', None):
            raw=process_demo();raw['failure']={'when':False,'message':message}
            before=copy.deepcopy(raw);spec=validate_rules(raw)
            self.assertFalse(spec['failure']['when'])
            self.assertIn('reinicie',spec['failure']['message'])
            self.assertEqual(raw,before)
            self.assertEqual(validate_rules(spec),spec)
        raw=process_demo();raw['failure']={'when':False}
        self.assertFalse(validate_rules(raw)['failure']['when'])

    def test_no_default_for_active_failure_or_strict_challenge_or_wrong_type(self):
        raw=process_demo();raw['failure']={'when':True,'message':''}
        with self.assertRaises(RuleTextError) as caught:validate_rules(raw)
        self.assertEqual(caught.exception.details['field'],'failure.message')
        raw=fixtures()[0];raw['failure']={'when':False,'message':''}
        with self.assertRaises(RuleTextError):validate_rules(raw)
        raw=process_demo();raw['failure']={'when':False,'message':42}
        with self.assertRaises(RuleTextError):validate_rules(raw)

    def test_text_error_identifies_field_reason_and_length_without_echoing_text(self):
        for field,limit,value in [('goal.message',700,''),('scenes.processo.description',700,'x'*701),
                                  ('actions.avancar.feedback',500,None),('title',120,False)]:
            raw=process_demo()
            if field.startswith('goal.'):raw['goal']['message']=value
            elif field.startswith('scenes.'):raw['scenes'][0]['description']=value
            elif field.startswith('actions.'):raw['actions'][0]['feedback']=value
            else:raw[field]=value
            with self.assertRaises(RuleTextError) as caught:validate_rules(raw)
            self.assertEqual(caught.exception.details['field'],field)
            self.assertEqual(caught.exception.details['maxLength'],limit)
            self.assertIn(field,str(caught.exception))
            self.assertNotIn('x'*100,str(caught.exception))

    def test_valid_authored_failure_message_is_preserved(self):
        raw=process_demo();raw['failure']={'when':False,'message':'Observe novamente o movimento.'}
        self.assertEqual(validate_rules(raw)['failure']['message'],raw['failure']['message'])

    def test_generation_does_not_retry_for_unused_blank_failure_text(self):
        raw=process_demo();raw['failure']={'when':False,'message':''}
        calls=[]
        class Chat:
            def __init__(self,**kwargs):calls.append(kwargs)
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):return json.dumps(raw)
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch('services.rule_visuals.generate_visual',AsyncMock(return_value=(None,''))):
            result=asyncio.run(generate_rule_simulator('Demonstração de mecanismo','Curso','qa','openai','fake','model'))
        self.assertEqual(len(calls),1)
        self.assertTrue(result['spec']['verification']['solutionVerified'])


if __name__=='__main__':unittest.main()
