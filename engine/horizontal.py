"""Measured wide layouts: media rails, compact labels and text-first allocation.

The source/candidate schema stays unchanged. Each arrangement is sized from
actual font requirements at a proposed shared readability level; it is rejected
if those requirements do not fit, rather than silently shrinking each piece.
"""
from copy import deepcopy
import math

from engine.geometry import bounds, place_uniform
from engine.groups import label_pair, label_center
from engine.typography import measure_text


def _font_size(element, unit, level):
    # Preserve prominence, while compressing extreme source font-size ratios.
    factor = 1.5 if unit['role'] == 'headline' else .85 if unit['role'] == 'fine_print' else 1.
    return max(1., min(element['font_size'] * 1.25, math.floor(level * factor)))


def _measured_unit(unit, original, width, level):
    """Build a local unit with measured height, or reject an impossible width."""
    members = [deepcopy(original[i]) for i in unit['element_ids']]
    if width <= 1:
        return None
    pair = label_pair(members)
    if pair:
        bg, text = pair
        cx, cy = label_center(bg, text)
        size = _font_size(text, unit, level)
        padding = max(1., size * .16)
        angle = math.radians(bg.get('rotation', 0))
        # Iterate the unrotated width to reserve room for the rotated height.
        bw = width
        for _ in range(6):
            tw = bw * (1 - 2 * abs(cx - .5)) - 2 * padding
            if tw <= 0 or not .1 < cy < .9:
                return None
            probe = dict(text, font_size=size, width=tw, height=1e9)
            m = measure_text(probe)
            if m['overflow_x'] or m['overflow_y']:
                return None
            th = m['height'] + .15
            bh = (th + 2 * padding) / (1 - 2 * abs(cy - .5))
            bg.update(x=0., y=0., width=bw, height=bh)
            text.update(x=cx*bw-tw/2, y=cy*bh-th/2, width=tw, height=th, font_size=size)
            x,y,rw,rh = bounds(members, rotated=True)
            if rw <= width + 1e-6:
                for e in members:
                    e['x'] -= x; e['y'] -= y
                return members, rh
            bw -= (rw-width) / max(.2, abs(math.cos(angle))) + .1
        return None
    if len(members) == 1 and members[0]['type'] == 'text' and not members[0].get('rotation',0):
        e = members[0]
        e.update(x=0.,y=0.,width=width,height=1e9,font_size=_font_size(e,unit,level))
        m = measure_text(e)
        if m['overflow_x'] or (e.get('max_lines') is not None and m['line_count']>e['max_lines']):
            return None
        e['height'] = m['height'] + .15
        return members,e['height']
    # Rigid groups and rotated standalone text: keep the original transform.
    _,_,w,h = bounds(members,rotated=True)
    place_uniform(members,(0,0,width,h*width/w))
    for e in members:
        if e['type']=='text':
            e['font_size']=_font_size(original[e['id']],unit,level)
            m=measure_text(e)
            if m['overflow_x'] or m['overflow_y']:
                return None
    return members,bounds(members,rotated=True)[3]


def _write(by_id, built, x, y):
    members,height = built
    for e in members:
        e=deepcopy(e)
        e['x']+=x; e['y']+=y
        by_id[e['id']].update(e)
    return height


def _stack_text(units,original,width,level,gap):
    built=[_measured_unit(u,original,width,level) for u in units]
    if any(b is None for b in built):
        return None
    return built,sum(b[1] for b in built)+gap*max(0,len(built)-1)


def _label_rows(units,original,width,level,gap,rows):
    if not units:
        return [],0.
    rows=min(rows,len(units))
    groups=[units[i*len(units)//rows:(i+1)*len(units)//rows] for i in range(rows)]
    result,total=[],0.
    for row in groups:
        weights=[]
        for u in row:
            labels=[original[i] for i in u['element_ids'] if original[i]['type']=='text']
            demands=[measure_text(dict(e,width=1e6,height=1e6,font_size=_font_size(e,u,level)))['width'] for e in labels]
            weights.append(max(demands+[level*3])+level)
        available=width-gap*(len(row)-1)
        if available<=0:
            return None
        cells=[]
        for u,weight in zip(row,weights):
            w=available*weight/sum(weights)
            b=_measured_unit(u,original,w,level)
            if b is None:
                return None
            cells.append((b,w))
        height=max(b[1] for b,w in cells)
        result.append((cells,height))
        total+=height
    return result,total+gap*(rows-1)


def _draw_rows(by_id,built,x,y,gap):
    for cells,height in built:
        cursor=x
        for b,width in cells:
            _write(by_id,b,cursor,y+(height-b[1])/2)
            cursor+=width+gap
        y+=height+gap


def _media(units,original,rectangle,level,gap,mode,by_id):
    """Give a dominant portrait/square image full height, stack companions.

    Alternate all-row and all-column arrangements support image counts/aspects
    beyond logo+product compositions. Missing assets are treated like all images.
    """
    x,y,w,h=rectangle
    if not units:
        return True
    pictures=[u for u in units if all(original[i]['type']=='image' for i in u['element_ids'])]
    if mode=='hero' and len(pictures)>=2:
        hero=max(pictures,key=lambda u:(u['importance']*u['source_bounds'][2]*u['source_bounds'][3],-u['source_bounds'][1],-u['source_bounds'][0]))
        others=[u for u in units if u is not hero]
        hw=min(w*.48,h*hero['source_bounds'][2]/hero['source_bounds'][3])
        if not _media([hero],original,(x,y,hw,h),level,gap,'column',by_id):
            return False
        return _media(others,original,(x+hw+gap,y,w-hw-gap,h),level,gap,'column',by_id)
    if mode=='row' and len(units)>1:
        widths=[u['source_bounds'][2]/max(1.,u['source_bounds'][3]) for u in units]
        available=w-gap*(len(units)-1)
        if available<=0:return False
        for u,weight in zip(units,widths):
            uw=available*weight/sum(widths)
            if not _media([u],original,(x,y,uw,h),level,gap,'column',by_id):return False
            x+=uw+gap
        return True
    built=[]
    flexible=[]
    required=gap*(len(units)-1)
    for u in units:
        if u in pictures:
            flexible.append(u)
        else:
            b=_measured_unit(u,original,w,level)
            if b is None:return False
            built.append((u,b));required+=b[1]
    if required>=h:return False
    heights={u['key']:b[1] for u,b in built}
    # Allocate image heights by their natural aspect, not one arbitrary equal row.
    natural={u['key']:min(h,w*u['source_bounds'][3]/u['source_bounds'][2]) for u in flexible}
    if flexible:
        for u in flexible:
            heights[u['key']]=(h-required)*natural[u['key']]/sum(natural.values())
    cursor=y
    for u in units:
        uh=heights[u['key']]
        if u in flexible:
            members=[deepcopy(original[i]) for i in u['element_ids']]
            place_uniform(members,(x,cursor,w,uh))
            for e in members:by_id[e['id']].update(e)
        else:
            _write(by_id,next(b for unit,b in built if unit is u),x,cursor)
        cursor+=uh+gap
    return True


def horizontal_candidates(source,target,analysis,prepare):
    if target['width']/target['height'] < 2.:
        return []
    original={e['id']:e for e in source['elements']}
    units=[u for u in analysis['units'] if u['role'] not in ('background','decoration')]
    pictures=[u for u in units if u['role']=='image']
    texts=[u for u in units if len(u['element_ids'])==1 and original[u['element_ids'][0]]['type']=='text' and not original[u['element_ids'][0]].get('rotation',0)]
    labels=[u for u in units if u not in pictures and u not in texts]
    if not texts:
        return []
    # Keep title/copy/fine print reading order even when source order is shuffled.
    texts.sort(key=lambda u:({'headline':0,'fine_print':2}.get(u['role'],1),u['source_bounds'][1],u['source_bounds'][0],u['key']))
    cw,ch=target['width'],target['height']
    margin,gap=min(cw,ch)*.02,min(cw,ch)*.012
    x,y,w,h=margin,margin,cw-2*margin,ch-2*margin
    candidates=[]
    rotated=[u for u in labels if any(original[i].get('rotation',0) for i in u['element_ids'])]
    for move_rotated in (False,True) if rotated and pictures else (False,):
        media=pictures+(rotated if move_rotated else [])
        actions=[u for u in labels if not move_rotated or u not in rotated]
        widths=[0.] if not media else sorted(set(min(w*.45,h*f) for f in (1.2,1.8,2.4,3.)))
        for mw in widths:
            tw=w-mw-(gap if mw else 0)
            for mode in ('hero','row','column') if len(media)>1 else ('column',):
                for rows in range(1,min(3,len(actions))+1) if actions else (1,):
                    def attempt(level):
                        text_build=_stack_text(texts,original,tw,level,gap)
                        label_build=_label_rows(actions,original,tw,level,gap,rows)
                        if text_build is None or label_build is None:return None
                        tb,th=text_build;lb,lh=label_build
                        total=th+lh+(gap if actions else 0)
                        if total>h:return None
                        design,by_id=prepare(source,target,analysis)
                        if not _media(media,original,(x,y,mw,h),level,gap,mode,by_id):return None
                        tx=x+mw+(gap if mw else 0)
                        # Distribute unused vertical space between blocks, not
                        # inside giant empty text boxes or oversized buttons.
                        extra=(h-total)/max(1,len(tb)+(1 if actions else 0))
                        cursor=y+extra/2
                        for b in tb:
                            _write(by_id,b,tx,cursor)
                            cursor+=b[1]+gap+extra
                        if actions:_draw_rows(by_id,lb,tx,y+h-lh,gap)
                        return design
                    # Every successful probe is measured. The shared level
                    # protects all labels/copy instead of shrinking them ad hoc.
                    lo,hi=5.,min(36.,max(e['font_size'] for e in source['elements'] if e['type']=='text'))
                    best=None
                    for _ in range(8):
                        middle=(lo+hi)/2
                        result=attempt(middle)
                        if result is None:hi=middle
                        else:best=result;lo=middle
                    if best is not None:candidates.append(best)
    return candidates


def coherent_text_candidates(source, target, analysis, candidates):
    """Compact adjacent source copy into a block after a substantial reflow.

    Geometry changes only; no fonts are shrunk. The original alternatives stay
    in the search, and validation rejects a block that collides with other units.
    """
    from engine.relationships import text_links, text_gap
    change=abs(math.log((target['width']/target['height']) /
                        (source['canvas']['width']/source['canvas']['height'])))
    if change <= .35:
        return []
    links=text_links(source,analysis)
    clusters=[]
    for a,b in links:
        if clusters and clusters[-1][-1]==a:clusters[-1].append(b)
        else:clusters.append([a,b])
    result=[]
    for candidate in candidates:
        design=deepcopy(candidate)
        by_id={e['id']:e for e in design['elements']}
        changed=False
        for ids in clusters:
            members=[by_id[i] for i in ids]
            if any(e.get('rotation',0) for e in members):continue
            if any(b['y'] < a['y']+a['height']-1e-5 for a,b in zip(members,members[1:])):continue
            left=max(e['x'] for e in members)
            right=min(e['x']+e['width'] for e in members)
            if right-left < .65*min(e['width'] for e in members):continue
            heights=[measure_text(e)['height']+.15 for e in members]
            gaps=[text_gap(a,b) for a,b in zip(members,members[1:])]
            total=sum(heights)+sum(gaps)
            top=min(e['y'] for e in members)
            bottom=max(e['y']+e['height'] for e in members)
            if bottom-top <= total+1:continue
            cursor=(top+bottom-total)/2
            for index,e in enumerate(members):
                e['y']=cursor;e['height']=heights[index]
                cursor+=heights[index]+(gaps[index] if index<len(gaps) else 0)
            changed=True
        if changed:result.append(design)
    return result
