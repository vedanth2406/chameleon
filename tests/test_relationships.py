"""Positive relationships and counterexamples, using real supplied asset alpha."""
from collections import Counter
from copy import deepcopy
import random
import unittest

from engine.analysis import analyze
from engine.layout import generate_candidates
from engine.quality import evaluate, repair
from engine.resize import resize
from engine.spatial_relationships import STRONG, supported_pairs
from tools.generalization import preserved, metrics
from tools.generalization_cases import compositions as reviewed
from tools.relationship_cases import compositions


def strong(source, field):
    return [r for r in analyze(source)[field] if r['confidence'] >= STRONG]


class RelationshipTests(unittest.TestCase):
    def test_reviewed_and_new_relationships_survive_reflow(self):
        cases = [f for f in reviewed() if f['name'] in ('nested-studio-cards', 'transparent-overlap-study')]
        cases += compositions()[:2]
        for f in cases:
            for target in f['targets']:
                with self.subTest(case=f['name'], target=target):
                    source = f['source']; before = deepcopy(source)
                    out = resize(source, target); m = metrics(f, out)
                    self.assertEqual(source, before)
                    for key in ('lost_containment', 'lost_intended_layers', 'overflows',
                                'preservation_errors', 'schema_errors', 'group_errors',
                                'bounds_errors', 'ink_bounds_errors', 'semantic_collisions'):
                        self.assertFalse(m[key], (key, m[key]))
                    self.assertFalse(m['evaluation']['hard_errors'])
                    self.assertGreaterEqual(m['min_font_size'], 12)

    def test_accidental_overlap_requires_repair_not_exemption(self):
        f = compositions()[2]; source = f['source']; a = analyze(source)
        self.assertFalse(a['layers'])
        self.assertTrue(any('overlap' in e for e in evaluate(source, source, a)['hard_errors']))
        for target in f['targets']:
            out = resize(source, target)
            self.assertFalse(evaluate(source, out, a)['hard_errors'])
            self.assertFalse(metrics(f, out)['semantic_collisions'])

    def test_background_decorations_and_nearby_groups_stay_independent(self):
        f = compositions()[3]; a = analyze(f['source'])
        self.assertFalse(a['containers']); self.assertFalse(a['layers'])
        self.assertIn('paper', a['background_ids'])
        self.assertEqual(set(a['decoration_ids']), {'wash', 'disk'})
        units = [set(u['element_ids']) for u in a['units']]
        self.assertIn({'one', 'one-note'}, units)
        self.assertIn({'two', 'two-note'}, units)
        s = compositions()[0]['source']; r = strong(s, 'containers')[0]
        self.assertNotIn('aside-card', r['child_ids'])
        self.assertNotIn('aside-label', r['child_ids'])

    def test_container_requires_fill_stacking_and_multiple_complete_units(self):
        base = compositions()[0]['source']
        for patch in ({'fill_color': 'rgba(0,0,0,0)'}, {'opacity': .4},
                      {'shape_type': 'ellipse'}, {'z_index': 10}, {'rotation': 12},
                      {'x': 0, 'y': 0, 'width': 860, 'height': 650, 'z_index': 0}):
            s = deepcopy(base); next(e for e in s['elements'] if e['id'] == 'panel').update(patch)
            self.assertFalse(strong(s, 'containers'), patch)
        s = deepcopy(base)
        # A partial explicit unit may not be peeled into a container.
        next(e for e in s['elements'] if e['id'] == 'caption-1')['x'] = 700
        self.assertFalse(strong(s, 'containers'))

    def test_ambiguous_panel_remains_soft(self):
        s = deepcopy(compositions()[0]['source'])
        next(e for e in s['elements'] if e['id'] == 'panel')['x'] = 0
        next(e for e in s['elements'] if e['id'] == 'panel')['width'] = 525
        a = analyze(s)
        self.assertTrue(a['containers'])
        self.assertFalse(strong(s, 'containers'))
        self.assertFalse(supported_pairs(a, {e['id']: e for e in s['elements']}))
        out = deepcopy(s); next(e for e in out['elements'] if e['id'] == 'panel')['x'] = 800
        self.assertGreater(evaluate(s, out, a)['penalties']['containment'], 0)

    def test_layering_needs_multiple_signals_and_visible_content(self):
        base = compositions()[1]['source']
        self.assertEqual(len(strong(base, 'layers')), 1)
        for changes in ('no-rotation', 'no-compositing', 'missing', 'explicit-group', 'text-conflict'):
            s = deepcopy(base); images = [e for e in s['elements'] if e['type'] == 'image']
            if changes == 'no-rotation':
                for e in images: e['rotation'] = 0
            if changes == 'no-compositing':
                for e in images: e['z_index'] = 3
            if changes == 'missing':
                for e in images: e['asset_id'] = 'absent-relationship-probe.png'
            if changes == 'explicit-group':
                images[0]['group_id'] = 'explicit'
                next(e for e in s['elements'] if e['type'] == 'text')['group_id'] = 'explicit'
            if changes == 'text-conflict':
                next(e for e in s['elements'] if e['id'] == 'note').update(x=130, y=180)
            self.assertFalse(strong(s, 'layers'), changes)

    def test_box_padding_overlap_is_not_visible_layering(self):
        s = deepcopy(compositions()[1]['source'])
        next(e for e in s['elements'] if e['id'] == 'right-view').update(x=315, y=230)
        s['elements'] = [e for e in s['elements'] if e['id'] != 'note']
        a = analyze(s)
        self.assertTrue(a['layers'])
        self.assertEqual(a['layers'][0]['visible_overlap_fraction'], 0)
        self.assertFalse(strong(s, 'layers'))

    def test_competing_enclosures_do_not_absorb_the_design(self):
        s = deepcopy(compositions()[0]['source'])
        outer = deepcopy(next(e for e in s['elements'] if e['id'] == 'panel'))
        outer.update(id='outer', x=20, y=90, width=560, height=530)
        s['elements'].append(outer)
        a = analyze(s)
        self.assertEqual(len(a['containers']), 2)
        self.assertEqual(len(strong(s, 'containers')), 1)
        self.assertEqual(strong(s, 'containers')[0]['container_id'], 'panel')
        # Unrelated content covered by an expanded mat is still a collision.
        out = deepcopy(s)
        next(e for e in out['elements'] if e['id'] == 'panel')['width'] = 800
        self.assertTrue(any('aside' in e and 'overlap' in e for e in evaluate(s, out, a)['hard_errors']))

    def test_loss_costs_and_exemptions_are_pair_specific(self):
        s = compositions()[1]['source']; a = analyze(s)
        separated = deepcopy(s)
        next(e for e in separated['elements'] if e['id'] == 'right-view')['x'] = 470
        self.assertGreater(evaluate(s, separated, a)['penalties']['layering'], 50)
        damaged = deepcopy(s)
        next(e for e in damaged['elements'] if e['id'] == 'note').update(x=130, y=180)
        self.assertTrue(any('overlap' in e for e in evaluate(s, damaged, a)['hard_errors']))
        # Same exact box/angle creates a new occlusion, not a sanctioned overlap.
        by = {e['id']: e for e in deepcopy(s)['elements']}
        for k in ('x', 'y', 'width', 'height', 'rotation'): by['right-view'][k] = by['left-view'][k]
        self.assertNotIn(frozenset(('left-view', 'right-view')), supported_pairs(a, by))

    def test_inference_never_closes_layer_graph_transitively(self):
        s = deepcopy(compositions()[1]['source'])
        extra = deepcopy(next(e for e in s['elements'] if e['id'] == 'left-view'))
        extra.update(id='third', x=260, y=285, z_index=5)
        s['elements'].append(extra)
        a = analyze(s); counts = Counter(i for r in a['layers'] if r['confidence'] >= STRONG for i in r['element_ids'])
        self.assertTrue(counts)
        self.assertEqual(max(counts.values()), 1)

    def test_renaming_shuffle_and_candidate_immutability(self):
        for f in compositions()[:2]:
            source = f['source']; target = f['targets'][1]
            expected = resize(source, target); modified = deepcopy(source)
            rng = random.Random(974); mapping = {e['id']: f'r-{rng.randrange(10**10)}' for e in modified['elements']}
            for e in modified['elements']:
                e['id'] = mapping[e['id']]
                if e.get('group_id') is not None: e['group_id'] = 'renamed:'+e['group_id']
            rng.shuffle(modified['elements']); actual = {e['id']: e for e in resize(modified, target)['elements']}
            for e in expected['elements']:
                for k in ('x', 'y', 'width', 'height', 'font_size'):
                    if k in e: self.assertAlmostEqual(e[k], actual[mapping[e['id']]][k], places=6)
            a = analyze(source); before = deepcopy((source, target, a))
            candidates = generate_candidates(source, target, a)
            for c in candidates:
                fixed = repair(source, c, a)
                self.assertFalse(preserved(source, fixed))
            self.assertEqual((source, target, a), before)
            candidates[0]['elements'][0]['x'] = -500
            self.assertEqual((source, target, a), before)


if __name__ == '__main__':
    unittest.main()
