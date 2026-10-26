"""Visual-quality regressions, separate from the original invariant suite."""
import json
from pathlib import Path
from copy import deepcopy
import unittest

from engine.analysis import analyze
from engine.groups import label_pair, valid_label_pair
from engine.horizontal import _measured_unit
from engine.quality import evaluate, repair
from engine.resize import resize
from engine.typography import measure_text
from tools.quality_cases import wide_cases
from tests.test_engine import composition, text, shape

ROOT=Path(__file__).resolve().parents[1]


class VisualQualityTests(unittest.TestCase):
    def test_compact_rotated_label_stays_attached(self):
        source=composition(rotation=17)
        analysis=analyze(source)
        unit=next(u for u in analysis['units'] if 'button' in u['element_ids'])
        original={e['id']:e for e in source['elements']}
        built=_measured_unit(unit,original,110,9)
        self.assertIsNotNone(built)
        members,height=built
        self.assertTrue(valid_label_pair([original[i] for i in unit['element_ids']],members))
        self.assertFalse(measure_text(next(e for e in members if e['type']=='text'))['overflow_y'])
        detached=deepcopy(members)
        next(e for e in detached if e['type']=='text')['x']+=30
        self.assertFalse(valid_label_pair([original[i] for i in unit['element_ids']],detached))

    def test_compaction_does_not_generalize_to_arbitrary_groups(self):
        source=composition()
        members=[e for e in source['elements'] if e.get('group_id')=='']
        self.assertIsNotNone(label_pair(members))
        members.append(text('extra'))
        self.assertIsNone(label_pair(members))
        members.pop();members[0]['rotation']=10
        self.assertIsNone(label_pair(members))

    def test_microscopic_text_cost_and_headline_reversal(self):
        source=dict(canvas=dict(width=500,height=300),elements=[text('headline',w=450,h=80,size=40),text('body',y=150,w=450,h=60,size=20)])
        a=analyze(source)
        small=deepcopy(source);readable=deepcopy(source)
        for e in small['elements']:e['font_size']=6
        for e in readable['elements']:e['font_size']=12
        qs,qr=evaluate(source,small,a),evaluate(source,readable,a)
        self.assertGreater(qs['penalties']['microscopic'],20)
        self.assertEqual(qr['penalties']['microscopic'],0)
        self.assertGreater(qs['score'],qr['score'])
        reversed_hierarchy=deepcopy(source)
        reversed_hierarchy['elements'][0]['font_size']=9
        reversed_hierarchy['elements'][1]['font_size']=10
        self.assertGreater(evaluate(source,reversed_hierarchy,a)['penalties']['headline_prominence'],0)

    def test_product_recognition_cost(self):
        source=composition();a=analyze(source)
        normal=resize(source,dict(width=900,height=200));small=deepcopy(normal)
        image=next(e for e in small['elements'] if e['type']=='image')
        image['height']*=.2;image['width']*=.2
        self.assertGreater(evaluate(source,small,a)['penalties']['image_recognition'],
                           evaluate(source,normal,a)['penalties']['image_recognition'])

    def test_repair_retains_compact_layout_font_sizes(self):
        name,task=wide_cases('tuning')[-1]
        source=task['source'];a=analyze(source)
        out=resize(source,task['target_canvas']);fixed=repair(source,out,a)
        self.assertFalse(evaluate(source,fixed,a)['hard_errors'])
        self.assertEqual([e['font_size'] for e in out['elements'] if e['type']=='text'],
                         [e['font_size'] for e in fixed['elements'] if e['type']=='text'])

    def test_substantial_reflow_keeps_adjacent_copy_coherent(self):
        source=dict(canvas=dict(width=800,height=1000),elements=[shape('base',w=800,h=1000),
            text('title',80,360,640,100,'A better way to begin',44),
            text('body',80,470,640,70,'Thoughtful details for every day.',22)])
        target=dict(width=1000,height=250)
        result=resize(source,target)
        t,b=[e for e in result['elements'] if e['type']=='text']
        self.assertLess(b['y']-t['y']-t['height'],max(t['font_size'],b['font_size']))
        self.assertGreater(t['font_size'],b['font_size'])
        self.assertFalse(evaluate(source,result,analyze(source))['hard_errors'])

    def test_wide_tuning_design_preserves_content_with_readable_compromise(self):
        _,task=wide_cases('tuning')[-1]
        before=deepcopy(task)
        result=resize(task['source'],task['target_canvas'])
        self.assertEqual(task,before)
        self.assertFalse(evaluate(task['source'],result,analyze(task['source']))['hard_errors'])
        sizes=[e['font_size'] for e in result['elements'] if e['type']=='text']
        self.assertGreaterEqual(min(sizes),8)
        original={e['id']:e for e in task['source']['elements']}
        for e in result['elements']:
            for key in ('content','font_family','asset_id','group_id','rotation','opacity'):
                self.assertEqual(e.get(key),original[e['id']].get(key))

    def test_real_asset_controls_have_no_missing_images(self):
        for _,task in wide_cases('real-controls'):
            for e in task['source']['elements']:
                if e['type']=='image':self.assertTrue((ROOT/'brand_kit/assets'/e['asset_id']).is_file())


if __name__=='__main__':unittest.main()
