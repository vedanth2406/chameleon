"""Twelve hand-authored source compositions, independent of prior fixtures.

Intent annotations live outside the design and are never passed to the engine.
The flat schema has no parent-group field: nested-looking cards use containment
annotations, not invented schema fields. Assets are existing files or deliberately
missing references; no pixels are created or replaced by this suite.
"""
from itertools import combinations

INK = 'rgba(38,30,40,1)'
PAPER = 'rgba(249,243,228,1)'
ORANGE = 'rgba(221,91,40,1)'
BOTTLE = 'solstice_bottle.png'
LOGO = 'solstice_logo_lockup.png'


def text(key, x, y, w, h, copy, size=20, **style):
    return dict(id=key, type='text', x=x, y=y, width=w, height=h,
                content=copy, font_family='Solstice Sans', font_size=size,
                color=INK, z_index=5) | style


def image(key, x, y, w, h, asset=BOTTLE, **style):
    return dict(id=key, type='image', x=x, y=y, width=w, height=h,
                asset_id=asset, fit='contain', z_index=3, **style)


def shape(key, x, y, w, h, color=ORANGE, **style):
    return dict(id=key, type='shape', x=x, y=y, width=w, height=h,
                shape_type='rectangle', fill_color=color, z_index=1, **style)


def case(name, size, elements, targets, description, adversarial=False,
         layers=(), containers=(), missing=()):
    # The supplied logo has white lettering. Give it a dark shape backing,
    # without touching its pixels; the backing travels in its explicit group.
    for element in list(elements):
        if element.get('asset_id') == LOGO:
            group = element.setdefault('group_id', 'signature-mat:' + element['id'])
            mat = shape(element['id']+'-mat', element['x'], element['y'],
                        element['width'], element['height'], INK, group_id=group)
            mat['z_index'] = 2
            elements.append(mat)
    background = shape('paper', 0, 0, *size, PAPER)
    background['z_index'] = 0
    elements = [background] + elements
    # All shape-backed card/group layers are intentionally behind their members.
    intended = {tuple(sorted(p)) for p in layers}
    for a, b in combinations(elements[1:], 2):
        if a.get('group_id') is not None and a.get('group_id') == b.get('group_id') and 'shape' in (a['type'], b['type']):
            intended.add(tuple(sorted((a['id'], b['id']))))
    for parent, children in containers:
        intended.update(tuple(sorted((parent, child))) for child in children)
    return dict(name=name, description=description, adversarial=adversarial,
                source=dict(canvas=dict(zip(('width', 'height'), size)), elements=elements),
                targets=[dict(zip(('width', 'height'), target)) for target in targets],
                intent=dict(backgrounds=['paper'], decorative=[e['id'] for e in elements if e.get('opacity', 1) <= .35],
                            overlap_pairs=sorted(intended), containers=list(containers),
                            missing_ids=list(missing)))


def compositions():
    result = []
    e = [text('catalogue', 40, 30, 900, 55, 'Objects in three frames', 32)]
    for i, (w, h, asset, caption) in enumerate([(210, 300, BOTTLE, '01 / Tall study'),
                                               (280, 95, LOGO, '02 / Wordmark'),
                                               (230, 210, BOTTLE, '03 / Square study')]):
        x = 40 + i*320
        e += [image(f'print-{i}', x, 145, w, h, asset, group_id=f'frame-{i}'),
              text(f'caption-{i}', x, 490, 285, 50, caption, 18, group_id=f'frame-{i}')]
    result.append(case('gallery-triptych', (1000, 650), e, [(420, 900), (1200, 240)],
                       'Image-led triptych: three unequal image boxes with captions; no CTA.'))

    e = [text('masthead', 40, 30, 920, 105, 'Notes on the places where good conversations begin', 34,
              font_family='Solstice Serif', style_runs=[dict(start=0,end=5,font_weight='bold',color=ORANGE)])]
    for i, (title, body) in enumerate([
        ('Along the river', 'The path follows the water past the old ferry stop. Neighbours bring folding chairs, share stories, and watch the light settle on the reeds. Nothing here asks you to hurry.'),
        ('Around the table', 'A shared table makes space for small discoveries. Bring a familiar dish, leave room for an unexpected guest, and listen for the story behind each recipe.')]):
        x = 45+i*480
        e += [text(f'column-title-{i}', x, 160, 420, 50, title, 26, group_id=f'column-{i}'),
              text(f'column-copy-{i}', x, 225, 420, 260, body, 21, group_id=f'column-{i}'),
              image(f'column-image-{i}', x+90, 510, 230 if i == 0 else 300, 190 if i == 0 else 100,
                    BOTTLE if i == 0 else LOGO, group_id=f'column-{i}')]
    result.append(case('two-column-journal', (1000, 760), e, [(600, 900), (1200, 330)],
                       'Editorial masthead over two explicit multi-element columns, paragraphs and illustrations.'))

    e = [image('large-object', 25, 50, 390, 420),
         text('side-title', 445, 80, 275, 180, 'A little\nmore daylight', 34),
         text('side-copy', 445, 300, 260, 200, 'Keep a quiet corner for the things you enjoy. A good afternoon does not need a complicated plan.', 21),
         image('signature', 40, 680, 300, 100, LOGO),
         shape('note-panel', 430, 610, 280, 260, 'rgba(234,219,192,1)', group_id='margin-note'),
         text('note-number', 455, 640, 225, 60, '04', 40, group_id='margin-note'),
         text('note-label', 455, 720, 225, 100, 'Field notes\nEarly autumn', 22, group_id='margin-note')]
    result.append(case('asymmetric-field-poster', (760, 1000), e, [(1000, 420), (360, 760)],
                       'Large upper-left image, narrow right copy, isolated lower signature and inset note.'))

    e = []
    for i, (label, value, asset) in enumerate([('Arrival', '09:30 / Courtyard', LOGO),
                                              ('Workshop', '11:00 / Long room', BOTTLE),
                                              ('Shared table', '13:30 / Terrace', LOGO)]):
        y = 45+i*180
        e += [text(f'event-{i}', 40, y+25, 260, 45, label, 24, group_id=f'row-{i}'),
              text(f'location-{i}', 340, y+25, 360, 45, value, 20, group_id=f'row-{i}'),
              image(f'row-art-{i}', 760, y, 150, 95 if i != 1 else 135, asset, group_id=f'row-{i}')]
    result.append(case('programme-ledger', (960, 600), e, [(420, 900), (1280, 200)],
                       'Three horizontal schedule rows with equal-priority labels; no conventional headline or CTA.'))

    e = [text('programme', 45, 25, 800, 50, 'Inside the open studio', 30),
         shape('outer-mat', 30, 100, 840, 630, 'rgba(219,204,177,1)', opacity=.8)]
    children = []
    for i, (label, copy) in enumerate([('Listen', 'A table for stories and patient questions.'),
                                      ('Make', 'Simple materials and room to experiment.'),
                                      ('Share', 'Leave a note for the next person to arrive.')]):
        x=55+i*275; group=f'inner-{i}'
        members=[shape(f'card-{i}', x, 145, 245, 510, 'rgba(255,250,237,1)', group_id=group),
                 text(f'card-name-{i}', x+18, 175, 209, 45, label, 25, group_id=group),
                 image(f'card-art-{i}', x+38, 245, 170, 170, group_id=group),
                 text(f'card-copy-{i}', x+18, 470, 209, 135, copy, 18, group_id=group)]
        e += members; children += [m['id'] for m in members]
    result.append(case('nested-studio-cards', (900, 800), e, [(500, 1000), (1250, 300)],
                       'Three independent explicit cards visually nested inside one enclosing mat; flat schema, no parent group.',
                       containers=[('outer-mat', children)]))

    e = [text('collage-title', 45, 25, 700, 65, 'Collected on a slow afternoon', 31),
         shape('light-circle', 90, 160, 430, 430, 'rgba(240,167,67,1)', opacity=.25),
         image('front-bottle', 130, 160, 300, 390, rotation=-9),
         image('back-bottle', 220, 235, 330, 310, rotation=14, opacity=.72),
         image('floating-signature', 565, 115, 275, 90, LOGO),
         text('collage-note', 80, 610, 730, 50, 'Two studies, one shared pool of light.', 22)]
    e[1]['shape_type']='ellipse'
    result.append(case('transparent-overlap-study', (900, 700), e, [(500, 900), (1200, 260)],
                       'Intentionally overlapping ungrouped rotated foreground images, translucent image and decorative light.',
                       layers=[('front-bottle','back-bottle')]))

    e = []
    for i,(x,y,angle,title,body) in enumerate([(80,90,-10,'Morning','Doors open at nine.'),
                                             (395,230,8,'Midday','Meet by the windows.'),
                                             (80,400,-6,'Evening','Leave a story behind.')]):
        group=f'card-turn-{i}'
        e += [shape(f'turn-card-{i}',x,y,280,145,'rgba(240,216,169,1)',group_id=group,rotation=angle),
              text(f'turn-title-{i}',x+20,y+15,240,42,title,25,group_id=group,rotation=angle),
              text(f'turn-body-{i}',x+20,y+70,240,50,body,17,group_id=group,rotation=angle)]
    e += [image('right-emblem',740,55,190,70,LOGO),image('right-object',730,330,220,250)]
    result.append(case('rotating-noticeboard',(1000,650),e,[(480,900),(1200,220)],
                       'Staggered rotated three-member groups, with a separate right-hand image column.'))

    letter=('Thank you for keeping this little place full of life. Every borrowed chair, shared recipe, and unhurried conversation has helped it become a meeting point. '
            'Next month we will open the garden on Saturday mornings. Bring something you are making, a question you have been considering, or simply yourself. '
            'There will be a table in the shade and time to sit together. If the weather turns, we will move inside. '
            'We hope the space remains useful, welcoming, and a little surprising. Tell us what you would like to see here next.')
    e=[image('letterhead',275,40,250,80,LOGO),text('salutation',70,170,660,65,'Dear neighbours,',34),
       text('letter',70,280,660,420,letter,22),text('signoff',70,760,500,65,'With thanks,\nThe studio team',24),
       text('postscript',70,895,660,55,'P.S. The kettle is always on.',18)]
    result.append(case('community-letter',(800,1000),e,[(1000,500),(360,800)],
                       'Text-led correspondence: long paragraph, salutation and sign-off; no product or CTA.'))

    e=[shape('link-west',110,370,490,7,INK,rotation=-53,opacity=.3),
       shape('link-east',400,370,490,7,INK,rotation=53,opacity=.3),
       shape('link-base',280,610,450,7,INK,opacity=.3)]
    for i,(x,y,label) in enumerate([(390,55,'Observe'),(90,450,'Discuss'),(680,450,'Try again')]):
        group=f'node-{i}'
        node=shape(f'node-disc-{i}',x,y,220,240,'rgba(229,211,181,1)',group_id=group);node['shape_type']='ellipse'
        e += [node,image(f'node-icon-{i}',x+65,y+30,90,100,group_id=group),
              text(f'node-word-{i}',x+15,y+155,190,45,label,24,group_id=group,text_align='center')]
    result.append(case('three-node-process',(1000,800),e,[(1200,360),(480,960)],
                       'A triangular process diagram with peer nodes and translucent connectors; no hero hierarchy.'))

    e=[text('index-heading',45,35,1000,60,'Reference strings for the archive',28),
       text('code-a',45,145,1010,45,'ARCHIVE_'+'WIDE'*16+'_END',17),
       text('code-b',45,220,1010,45,'CounterrevolutionaryInterconnectionsWithoutAnyConvenientWordBoundary',21),
       text('index-note',260,340,790,95,'These labels must remain complete. They are identifiers, not headlines or marketing copy.',22),
       image('index-stamp',45,340,165,110,LOGO)]
    result.append(case('unbreakable-reference-index',(1100,500),e,[(300,900),(1000,120)],
                       'Adversarial: identifiers fit at source size but cannot wrap at spaces; narrow and shallow targets.',True))

    e=[text('inventory-heading',40,25,900,65,'Two objects awaiting a place',30)]
    for i,asset in enumerate([BOTTLE,'unavailable-archive-object.png']):
        y=135+i*270;group=f'inventory-{i}'
        e += [shape(f'inventory-card-{i}',40,y,920,230,'rgba(232,221,198,1)',group_id=group),
              image(f'inventory-art-{i}',60,y+20,180,180,asset,group_id=group),
              text(f'inventory-label-{i}',300,y+25,590,50,['Object received','Object still in transit'][i],26,group_id=group),
              text(f'inventory-copy-{i}',300,y+105,590,80,['Amber glass, paper label, and a familiar silhouette.','The catalogue reference is retained while its photograph is unavailable.'][i],20,group_id=group)]
    result.append(case('missing-inventory-pair',(1000,700),e,[(480,900),(1100,250)],
                       'Separate missing-asset control: two horizontal inventory cards, one real photograph reference and one absent.',
                       missing=['inventory-art-1']))

    e=[text('contact-sheet-title',35,25,890,55,'Six fragments of a working collection',30)]
    missing=[]
    for i,asset in enumerate([BOTTLE,LOGO,'unavailable-fragment-a.png',LOGO,BOTTLE,'unavailable-fragment-b.png']):
        x=40+(i%3)*310;y=125+(i//3)*325;group=f'tile-{i}'
        e += [image(f'tile-art-{i}',x,y,260,210 if i%2==0 else 135,asset,group_id=group),
              text(f'tile-label-{i}',x,y+240,265,50,f'Fragment {i+1:02d} / retained',18,group_id=group)]
        if asset.startswith('unavailable'):missing.append(f'tile-art-{i}')
    result.append(case('missing-contact-sheet',(960,800),e,[(800,500),(1200,100)],
                       'Adversarial density: six grouped image/caption tiles, two deliberately missing images; extreme shallow target.',True,
                       missing=missing))
    return result
