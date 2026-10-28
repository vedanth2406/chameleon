"""Independent development probes. Intent annotations never enter the engine."""
from tools.generalization_cases import case, image, shape, text


def compositions():
    # A horizontal inset panel containing two vertically arranged explicit units,
    # plus a separate nearby group. Reflow is free BETWEEN, not within, groups.
    e = [text('heading', 45, 22, 700, 50, 'Field materials / two observations', 28),
         shape('panel', 40, 100, 510, 500, 'rgba(220,209,181,1)')]
    children = []
    for i, y in enumerate((130, 365)):
        ids = [f'object-{i}', f'caption-{i}']
        e += [image(ids[0], 65, y, 170, 200, group_id=f'row-{i}'),
              text(ids[1], 260, y+55, 260, 90,
                   ['Collected near the river. A study of light and distance.',
                    'Recorded in the evening. An ordinary object, seen again.'][i],
                   21, group_id=f'row-{i}')]
        children += ids
    e += [shape('aside-card', 600, 130, 210, 230, 'rgba(233,217,199,1)', group_id='aside'),
          text('aside-label', 620, 150, 170, 100, 'Notes from the field', 24, group_id='aside')]
    result = [case('inset-field-panel', (860, 650), e, [(480, 900), (1120, 340)],
                   'Two image/caption rows inside a panel; a third nearby group stays independent.',
                   containers=[('panel', children)])]

    # Opaque layers: differing z-order plus opposing rotations and actual asset
    # alpha envelopes, rather than the reviewed fixture's transparency cue.
    e = [text('line', 45, 30, 710, 60, 'Two views of the same object', 32),
         image('left-view', 100, 140, 280, 340, rotation=-12),
         image('right-view', 180, 210, 310, 300, rotation=17),
         text('note', 540, 230, 210, 150, 'Observe the edges. Follow the change in light.', 25)]
    e[2]['z_index'] = 4
    result.append(case('opaque-offset-study', (800, 620), e, [(440, 880), (1140, 320)],
                       'Opaque, independently stacked overlapping art with contrasting rotations.',
                       layers=[('left-view', 'right-view')]))

    e = [text('line', 40, 25, 650, 55, 'Independent observations', 30),
         image('one', 80, 145, 300, 300), image('two', 150, 205, 300, 300),
         text('note', 570, 180, 180, 180, 'These objects need their own space.', 24)]
    result.append(case('accidental-image-overlap', (800, 600), e, [(460, 900), (1140, 300)],
                       'Deliberate invalid-source control: similar opaque boxes overlap without compositing cues.',
                       adversarial=True))
    e = [shape('wash', 30, 100, 680, 440, 'rgba(237,158,83,1)', opacity=.25),
         shape('disk', 50, 120, 640, 400, 'rgba(222,204,184,1)'),
         text('line', 40, 25, 680, 55, 'Separate records', 30),
         image('one', 80, 160, 190, 250, group_id='first'),
         text('one-note', 80, 430, 210, 50, 'First record', 22, group_id='first'),
         image('two', 430, 160, 190, 250, group_id='second'),
         text('two-note', 430, 430, 210, 50, 'Second record', 22, group_id='second')]
    e[1]['shape_type'] = 'ellipse'
    e[1]['opacity'] = .3
    result.append(case('decorative-independent-records', (760, 600), e, [(460, 880), (1100, 310)],
                       'A wash and ellipse behind two nearby groups are decoration, not inferred enclosures.'))
    return result
