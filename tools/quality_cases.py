"""Wide-layout development fixtures. Reserve holdout cases until tuning is frozen."""
from tests.test_engine import text, shape


def wide_design(title, sentences, badges, images, target, rotated=True, real_only=False):
    body = ' '.join(sentences)
    elements = [shape('paper',w=1000,h=1250,z_index=0),
                text('lead',80,470,840,200,title,44) ]
    # Fixture helpers intentionally use the supplied fonts and assets; runtime
    # code must never branch on these names or strings.
    elements[1].update(font_family='Solstice Serif',font_weight='bold',text_align='center',z_index=4)
    elements.append(text('copy',80,690,840,170,body,24,text_align='left',z_index=4))
    assets = [('solstice_bottle.png',350,350),('solstice_logo_lockup.png',320,100),('solstice_bottle.png' if real_only else 'unavailable-wide-fixture.png',150,90)]
    for i,(asset,w,h) in enumerate(assets[:images]):
        elements.append(dict(id=f'visual-{i}',type='image',asset_id=asset,x=60+i*310,y=50,width=w,height=h,fit='contain',z_index=2))
    for i,caption in enumerate(badges):
        x,y = 40+(i%3)*320,900+(i//3)*95
        angle = -9 if rotated and i==0 else 0
        elements.extend([shape(f'panel-{i}',x,y,290,62,group_id=f'unit-{i}',z_index=2,rotation=angle),
                         text(f'caption-{i}',x+8,y+13,274,36,caption,20,group_id=f'unit-{i}',z_index=3,rotation=angle,text_align='center',font_weight='bold')])
        elements[-2]['fill_color']='rgba(215,85,40,1)'
    elements.append(text('terms',45,1190,910,40,'Details and availability vary. Please read the full offer before ordering.',13,z_index=4,text_align='center'))
    return dict(source=dict(canvas=dict(width=1000,height=1250),elements=elements),target_canvas=dict(zip(('width','height'),target)))


def wide_cases(split='tuning'):
    if split == 'tuning':
        return [
            ('wide-short',wide_design('Make room for a brighter morning', ['A fresh collection for everyday adventures.'],['DISCOVER','NEW SEASON'],2,(960,144))),
            ('wide-editorial',wide_design('Thoughtful essentials for days that take you somewhere unexpected',
                ['Designed with careful details and enduring materials, each piece is made to feel familiar from the very first day.',
                 'Explore the full collection and find something that belongs in your daily routine.'],
                ['CRAFTED WITH CARE','FREE DELIVERY','SHOP THE COLLECTION'],2,(1200,180))),
            ('wide-crowded',wide_design('Discover the new collection of thoughtful everyday essentials, made for brighter mornings and memorable evenings',
                ['Meet considered designs, balanced colors, and useful details that fit the rhythm of a busy day.',
                 'Our latest collection brings together favorite materials and fresh ideas for every room.'],
                ['MEMBER BENEFITS','NEW ARRIVALS','SMALL RUN','EXPLORE','LEARN MORE'],3,(880,112)))
        ]
    if split == 'real-controls':
        return [
            ('real-portrait-control',wide_design('Thoughtful details for everyday living',
                ['Discover familiar materials, useful features, and fresh ideas for the changing season.'],
                ['DISCOVER','BUILT TO LAST'],2,(620,940),False,True)),
            ('real-landscape-control',wide_design('A collection made for the everyday',
                ['Explore carefully chosen essentials with balanced colors and lasting materials.'],
                ['NEW COLLECTION','SHOP NOW','VIEW DETAILS'],3,(1440,360),False,True))
        ]
    if split == 'holdout':
        return [
            ('reserved-wide-a',wide_design('A fresh perspective', ['Useful details. Lasting materials. A collection for every day.'],['EXPLORE NOW'],1,(1050,125),False)),
            ('reserved-wide-b',wide_design('Discover carefully crafted designs for the places, people, and moments that matter most',
                ['From early starts to quiet afternoons, find thoughtfully chosen pieces that make the everyday feel a little more special.',
                 'Visit our collection to explore colors, materials, and details selected with care.'],
                ['NEW EDITION','MEMBER OFFER','FIND YOUR FAVORITE','EXPLORE THE RANGE'],3,(1360,170))),
            ('reserved-wide-c',wide_design('Start something beautiful today',
                ['Consider a different way to bring useful design into your home. Each item offers a considered balance of comfort, durability, and character.',
                 'Browse our selection and discover new favorites for the changing season.',
                 'Thoughtful choices for a welcoming home and a more comfortable everyday routine.'],
                ['LIMITED RUN','VIEW DETAILS','SHOP NOW','LOCAL DESIGN','MORE COLORS','NEW'],2,(1024,128),False)),
            ('reserved-real-d',wide_design('Small details make a lasting difference',
                ['Explore our collection of familiar materials and thoughtful features, designed to bring comfort into the everyday.',
                 'Find your next favorite piece and make room for a fresh perspective.'],
                ['NEW THIS WEEK','EXPLORE','VIEW THE COLLECTION'],3,(1260,126),True,True))
        ]
    raise ValueError(split)
