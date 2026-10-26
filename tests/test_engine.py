"""Regression tests run with unittest and the actual local font backend."""
import json
import math
from pathlib import Path
import random
import socket
import unittest
from collections import Counter
from copy import deepcopy
from unittest.mock import patch

from engine.analysis import analyze
from engine.geometry import bounds, inside, polygon_overlap
from engine.layout import generate_candidates
from engine.quality import evaluate, repair
from engine.resize import resize
from engine.typography import fit_text, font_manager, measure_text
from engine.validation import schema_errors

ROOT = Path(__file__).resolve().parents[1]


def text(eid, x=20, y=20, w=400, h=70, content='Fresh ideas for every season', size=30, **extra):
    return dict(id=eid, type='text', x=x, y=y, width=w, height=h,
                content=content, font_family='Solstice Sans', font_size=size,
                color='rgba(255,255,255,1)', **extra)


def shape(eid, x=0, y=0, w=640, h=480, **extra):
    return dict(id=eid, type='shape', x=x, y=y, width=w, height=h,
                shape_type='rectangle', fill_color='rgba(30,20,40,1)', **extra)


def composition(n=3, rotation=0):
    canvas_height = max(480, 140+n*75)
    elements = [shape('back', h=canvas_height, z_index=0), text('title', y=25, size=38, font_weight='bold', z_index=2)]
    for i in range(n):
        elements.append(text(f'paragraph-{i}', y=110+i*75, h=60, size=18,
                             content=('A longer sentence with useful information. ' * (i+1)).strip(), z_index=2))
    elements.extend([shape('button', 440, 370, 160, 55, group_id='', z_index=1, rotation=rotation),
                     text('label', 450, 378, 140, 35, 'Explore', 18, group_id='', z_index=2, rotation=rotation),
                     dict(id='picture', type='image', x=450, y=110, width=160, height=200,
                          asset_id='unavailable-test-asset.png', fit='cover', z_index=1)])
    return dict(canvas=dict(width=640, height=canvas_height), elements=elements)


class EngineTests(unittest.TestCase):
    def assert_preserved(self, source, result, target):
        self.assertEqual(result['canvas'], target)
        self.assertEqual(Counter(e['id'] for e in source['elements']), Counter(e['id'] for e in result['elements']))
        self.assertFalse(schema_errors(result))
        original = {e['id']: e for e in source['elements']}
        analysis = analyze(source)
        for e in result['elements']:
            old = original[e['id']]
            for key in old.keys() | e.keys():
                if key not in ('x', 'y', 'width', 'height', 'font_size'):
                    self.assertEqual((key in old, old.get(key)), (key in e, e.get(key)))
            self.assertGreater(e['width'], 0)
            self.assertGreater(e['height'], 0)
            self.assertTrue(inside(e, target), e['id'])
            if e['type'] == 'image' and e['id'] not in analysis['background_ids']:
                self.assertAlmostEqual(e['width']/e['height'], old['width']/old['height'])
        self.assertFalse(evaluate(source, result, analysis)['hard_errors'])

    def test_all_samples_and_nested_immutability(self):
        for path in sorted((ROOT/'input').glob('*.json')):
            with self.subTest(sample=path.name):
                task = json.loads(path.read_text()); before = deepcopy(task)
                out = resize(task['source'], task['target_canvas'])
                self.assertEqual(task, before)
                self.assert_preserved(task['source'], out, task['target_canvas'])
                out['elements'][0]['asset_id'] = 'changed'
                for e in out['elements']:
                    if 'style_runs' in e:
                        e['style_runs'][0]['color'] = 'changed'
                self.assertEqual(task, before)

    def test_compositions_counts_and_aspects(self):
        for count in (1, 4, 8):
            for target in ({'width': 420, 'height': 900}, {'width': 720, 'height': 720},
                           {'width': 1100, 'height': 430}, {'width': 1200, 'height': 160}):
                with self.subTest(count=count,target=target):
                    source = composition(count, rotation=17)
                    self.assert_preserved(source, resize(source, target), target)

    def test_renamed_ids_and_shuffled_order(self):
        source = composition(4)
        target = dict(width=1000, height=400)
        expected = resize(source, target)
        rng = random.Random(53)
        mapping = {e['id']: f'opaque-{rng.randrange(10**9)}' for e in source['elements']}
        changed = deepcopy(source)
        for e in changed['elements']:
            e['id'] = mapping[e['id']]
            if e.get('group_id') is not None:
                e['group_id'] = 'opaque-group'
        rng.shuffle(changed['elements'])
        result = resize(changed, target)
        self.assert_preserved(changed, result, target)
        actual = {e['id']: e for e in result['elements']}
        for e in expected['elements']:
            for key in ('x','y','width','height','font_size'):
                if key in e:
                    self.assertAlmostEqual(e[key], actual[mapping[e['id']]][key], places=6)

    def test_groups_take_precedence(self):
        source = composition()
        a = analyze(source)
        group = next(u for u in a['units'] if 'button' in u['element_ids'])
        self.assertEqual(set(group['element_ids']), {'button','label'})
        self.assertEqual(Counter(i for u in a['units'] for i in u['element_ids']), Counter(e['id'] for e in source['elements']))
        source['elements'].append(text('stranger', 445, 375, 140, 35, group_id='different'))
        group = next(u for u in analyze(source)['units'] if 'button' in u['element_ids'])
        self.assertNotIn('stranger', group['element_ids'])

    def test_inferred_group_and_decoration(self):
        source = composition()
        for e in source['elements']:
            e.pop('group_id', None)
        source['elements'].append(shape('mist', 40, 40, 100, 100, opacity=.2, z_index=1))
        a=analyze(source)
        self.assertEqual(set(next(u['element_ids'] for u in a['units'] if 'button' in u['element_ids'])), {'button','label'})
        self.assertIn('mist',a['decoration_ids'])
        self.assertIn(('button','label'),a['intentional_overlap_pairs'])
        self.assertEqual(a['background_ids'],['back'])

    def test_long_text_and_runs(self):
        e=text('long',w=160,h=180,content='A long sentence with bold pieces and more words to wrap. '*4,
               style_runs=[dict(start=2,end=20,font_weight='bold',font_style='italic',color='rgba(255,0,0,1)')],
               letter_spacing=.4, line_height=1.3)
        before=deepcopy(e)
        self.assertTrue(measure_text(e)['overflow_y'])
        fitted=fit_text(e)
        m=measure_text(fitted)
        self.assertFalse(m['overflow_x'] or m['overflow_y'])
        self.assertIn('skia',m['measurement_method'])
        self.assertEqual(e,before)
        self.assertEqual({k:v for k,v in e.items() if k!='font_size'}, {k:v for k,v in fitted.items() if k!='font_size'})
        fitted['style_runs'][0]['color']='changed'
        self.assertEqual(e,before)

    def test_unbreakable_word_and_impossible_fit(self):
        e=text('word',w=2,h=1,content='W'*100)
        fitted=fit_text(e)
        self.assertEqual(fitted['font_size'],1.)
        self.assertTrue(measure_text(fitted)['overflow_x'])
        source=dict(canvas=dict(width=400,height=400),elements=[e])
        with self.assertWarnsRegex(RuntimeWarning,'No fully feasible'):
            out=resize(source,dict(width=1,height=1))
        self.assertEqual(out['elements'][0]['content'],e['content'])
        self.assertTrue(evaluate(source,out,analyze(source))['hard_errors'])

    def test_max_lines_and_explicit_breaks(self):
        e=text('lines',w=400,h=300,content='First line\nSecond line\nThird line',max_lines=2)
        self.assertTrue(measure_text(e)['overflow_y'])
        self.assertTrue(measure_text(fit_text(e))['overflow_y'])
        self.assertEqual(measure_text(e)['line_count'],3)

    def test_rotated_bounds_and_polygon_intersection(self):
        a=shape('a',0,0,100,10,rotation=45)
        self.assertFalse(inside(a,dict(width=100,height=100)))
        b=shape('b',0,0,100,10,rotation=45)
        self.assertAlmostEqual(polygon_overlap(a,b),1000)
        b['x']=200
        self.assertEqual(polygon_overlap(a,b),0)
        source=dict(canvas=dict(width=150,height=150),elements=[a])
        out=resize(source,dict(width=120,height=80))
        self.assert_preserved(source,out,dict(width=120,height=80))

    def test_validation_detects_independent_failures(self):
        source=composition(); target=dict(width=900,height=500)
        good=resize(source,target); analysis=analyze(source)
        changes = [lambda d:d['elements'].append(deepcopy(d['elements'][0])),
                   lambda d:d['elements'].pop(),
                   lambda d:d['elements'][1].update(content='rewritten'),
                   lambda d:d['elements'][1].update(opacity=0),
                   lambda d:d['elements'][1].update(font_family='different'),
                   lambda d:d['elements'][-1].update(width=1),
                   lambda d:d['elements'][1].update(x=-2),
                   lambda d:d['elements'][1].update(font_size=400),
                   lambda d:d['elements'][-2].update(x=800),
                   lambda d:d['elements'][1].update(width=float('nan'))]
        for change in changes:
            damaged=deepcopy(good); change(damaged)
            self.assertTrue(evaluate(source,damaged,analysis)['hard_errors'])
        malformed=deepcopy(good); malformed['elements'][0]['type']='text'
        self.assertTrue(evaluate(source,malformed,analysis)['hard_errors'])

    def test_unwanted_collision_not_excused_by_source(self):
        source=dict(canvas=dict(width=500,height=200),elements=[text('a',size=20),text('b',x=30,size=20)])
        self.assertEqual(analyze(source)['intentional_overlap_pairs'],[])
        self.assertTrue(any('overlap' in x for x in evaluate(source,source,analyze(source))['hard_errors']))

    def test_repair_restores_protected_fields_and_groups(self):
        source=composition(); a=analyze(source); good=resize(source,dict(width=900,height=500))
        damaged=deepcopy(good)
        damaged['elements'][1]['content']='wrong'
        damaged['elements'][-2]['x']+=12
        damaged['elements'][-1]['width']*=1.2
        before=deepcopy(damaged)
        fixed=repair(source,damaged,a)
        self.assertEqual(damaged,before)
        messages=evaluate(source,fixed,a)['hard_errors']
        self.assertFalse(any('protected' in x or 'group' in x or 'distorted' in x for x in messages),messages)

    def test_candidates_are_multiple_independent_complete_designs(self):
        source=composition(); a=analyze(source); before=deepcopy(source); original_a=deepcopy(a)
        candidates=generate_candidates(source,dict(width=1100,height=430),a)
        self.assertGreater(len(candidates),10)
        self.assertTrue(all(not schema_errors(c) for c in candidates))
        self.assertEqual(source,before); self.assertEqual(a,original_a)
        candidates[0]['elements'][0]['fill_color']='changed'
        self.assertNotEqual(candidates[1]['elements'][0]['fill_color'],'changed')
        self.assertEqual(source,before)

    def test_offline_and_deterministic(self):
        source=composition()
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
            first=resize(source,dict(width=750,height=480))
            second=resize(source,dict(width=750,height=480))
        self.assertEqual(first,second)

    def test_invalid_inputs_fail_clearly(self):
        source=composition()
        for target in (dict(width=0,height=40),dict(width=True,height=40),dict(width=40.5,height=40)):
            with self.assertRaises(ValueError): resize(source,target)
        source['elements'].append(deepcopy(source['elements'][0]))
        with self.assertRaisesRegex(ValueError,'unique'): resize(source,dict(width=500,height=500))
        with self.assertRaises(ValueError): fit_text(text('x'),0)

    def test_near_aspect_preserves_composition(self):
        source=dict(canvas=dict(width=640,height=480),elements=[shape('background'),text('large',100,100,400,80,size=38),text('small',100,300,400,50,size=20)])
        target=dict(width=680,height=510); out=resize(source,target)
        for old,new in zip(source['elements'],out['elements']):
            self.assertAlmostEqual((old['x']+old['width']/2)/640,(new['x']+new['width']/2)/680)
            self.assertAlmostEqual((old['y']+old['height']/2)/480,(new['y']+new['height']/2)/510)

    def test_text_only_image_only_and_background_only(self):
        sources = [dict(canvas=dict(width=640,height=480), elements=[text('a'),text('b',y=180,size=20)]),
                   dict(canvas=dict(width=640,height=480), elements=[shape('only')]),
                   dict(canvas=dict(width=640,height=480), elements=[
                       dict(id=f'photo-{i}',type='image',x=40+i*180,y=40,width=140,height=260,
                            asset_id='missing-gallery-asset.png',group_id='gallery' if i<2 else None)
                       for i in range(3)])]
        for source in sources:
            target=dict(width=350,height=600)
            self.assert_preserved(source,resize(source,target),target)

    def test_renderer_wrap_parity_and_ink(self):
        from renderer.converter.convert import convert_chameleon_to_crello
        e=text('mixed',w=180,h=200,content='Wide bold words and narrow text on several lines.',size=24,
               style_runs=[dict(start=0,end=8,font_weight='bold')])
        source=dict(canvas=dict(width=300,height=300),elements=[e])
        converted,_=convert_chameleon_to_crello(source,font_manager())
        measurement=measure_text(e)
        self.assertEqual(measurement['line_count'],len(converted['text'][0].split('\n')))
        self.assertGreater(measurement['ink_bounds'][2],0)
        self.assertGreater(measurement['ink_bounds'][3],0)

    def test_readability_and_spacing_are_real_penalties(self):
        source=dict(canvas=dict(width=640,height=480),elements=[text('a',size=30),text('b',y=180,size=20)])
        analysis=analyze(source)
        good=resize(source,source['canvas'])
        tiny=deepcopy(good)
        for e in tiny['elements']: e['font_size']=2.
        q1,q2=evaluate(source,good,analysis),evaluate(source,tiny,analysis)
        self.assertGreater(q2['penalties']['readability'],q1['penalties']['readability'])
        self.assertGreater(q2['score'],q1['score'])

    def test_small_max_size_and_empty_text(self):
        blank=text('empty',content='')
        self.assertEqual(measure_text(blank)['line_count'],0)
        self.assertEqual(measure_text(blank)['height'],0)
        with self.assertRaises(ValueError): resize(None,dict(width=100,height=100))
        source=composition();source['elements'][1]['width']=0
        with self.assertRaisesRegex(ValueError,'positive'): resize(source,dict(width=100,height=100))


if __name__ == '__main__':
    unittest.main()
