"""Read Iyo's reviewed dictionary and FY2026 calendar layouts (offline only)."""
from __future__ import annotations
from pathlib import Path
import re
import calendar
from collections import Counter
from datetime import date

CATEGORY_CODES = {'可燃': 'burnable', 'プラ': 'plastic_packaging', '紙類': 'paper',
                  'かん': 'cans', 'びん': 'bottles', '布類': 'textiles', 'ペット': 'pet_bottles',
                  '有害': 'hazardous', 'その他': 'non_burnable', '粗大': 'bulky', '禁止': 'not_collected'}

# These three printed typos were checked visually against the legend and cell
# color. Keep the original label in provenance; never apply fuzzy corrections.
REVIEWED_LABELS = {(2, '学習机', '租大'): '粗大',
                   (2, 'カラーボックス', '租大'): '粗大',
                   (9, '発砲スチロール ［プラマーク有り］', 'ブラ'): 'プラ'}

# 55 禁止 cells use this darker gray rather than the first-page legend's
# gray. Their explicit labels and rendered cells were reviewed. Enumerating
# all category rectangles (not filtering by legend colors) prevents omission.
PALETTE_VARIANTS = {'禁止': {(0.4460, 0.4430, 0.4440)}}


def clean(value):
    return ' '.join(value.split()).strip()


def extract_items(path: Path):
    import pymupdf
    rows = []
    document = pymupdf.open(path)
    legend = {}
    for drawing in document[0].get_drawings():
        if drawing['fill'] and 32 < drawing['rect'].width < 33 and 14 < drawing['rect'].height < 16:
            label = re.sub(r'\s+', '', document[0].get_text(clip=drawing['rect']))
            if label in CATEGORY_CODES:
                legend[label] = tuple(round(c, 4) for c in drawing['fill'])
    if set(legend) != set(CATEGORY_CODES):
        raise ValueError('Dictionary legend is incomplete')
    for page_number, page in enumerate(document):
        if abs(page.rect.width - 1190.55) > .1 or abs(page.rect.height - 841.89) > .1:
            raise ValueError('Unexpected Iyo dictionary layout')
        drawings = page.get_drawings()
        headers = sorted([drawing['rect'] for drawing in drawings if drawing['fill']
            and 249 < drawing['rect'].width < 251 and 11 < drawing['rect'].height < 13], key=lambda r: r.x0)
        if len(headers) != 4:
            raise ValueError(f'Expected four item tables on dictionary page {page_number + 1}')
        for header in headers:
            cells = [drawing['rect'] for drawing in drawings if drawing['fill']
                and 30 < drawing['rect'].width < 32 and header.x0+93 < drawing['rect'].x0 < header.x0+96
                and drawing['rect'].y0 >= header.y1 and drawing['rect'].height > 10]
            cells.sort(key=lambda rect: rect.y0)
            seen = set()
            for rect in cells:
                bounds = tuple(round(c, 2) for c in rect)
                if bounds in seen:
                    raise ValueError('Duplicate dictionary cell')
                seen.add(bounds)
                label = re.sub(r'\s+', '', page.get_text(clip=rect))
                item = clean(page.get_text(clip=pymupdf.Rect(header.x0-1,rect.y0-.4,rect.x0,rect.y1+.4)))
                original_label = label
                label = REVIEWED_LABELS.get((page_number+1, item, label), label)
                if label not in CATEGORY_CODES:
                    headings = [drawing['rect'] for drawing in drawings if drawing['fill'] and drawing['rect'].width > 200
                        and drawing['rect'].contains(pymupdf.Point((rect.x0+rect.x1)/2,(rect.y0+rect.y1)/2))]
                    if re.fullmatch('[あ-ん]', label) and headings:
                        continue
                    raise ValueError(f'Unknown classification {label!r}, page {page_number+1}, {bounds}')
                color = next(tuple(round(c, 4) for c in d['fill']) for d in drawings
                             if d['fill'] and d['rect'] == rect)
                if color != legend[label] and color not in PALETTE_VARIANTS.get(label, set()):
                    raise ValueError(f'Classification color disagrees with text: {item}')
                note = clean(page.get_text(clip=pymupdf.Rect(rect.x1,rect.y0-.4,header.x1+4,rect.y1+.4)))
                if not item:
                    raise ValueError(f'Missing item, page {page_number+1}, {bounds}')
                rows.append({'item_id':f'iy-{len(rows)+1:04}', 'item':item, 'category':CATEGORY_CODES[label],
                    'source_category':label, 'original_label': original_label, 'note':note,
                    'source_page':page_number+1, 'source_rect':list(bounds)})
    return rows


def calendar_observations(path: Path):
    """Read actual date glyphs, fills and lower-cell text, independently of rules.

    Explicit year-end tables are reviewed separately. A shared 6th-week cell
    cannot prove both dates' collections; return it for a header-rule check.
    Geometry/font checks deliberately reject a revised official layout.
    """
    import pymupdf
    document = pymupdf.open(path)
    if len(document) != 2:
        raise ValueError('Expected two calendar pages')
    observations = {}
    for page_no, page in enumerate(document):
        if abs(page.rect.width-1190.55) > .1 or abs(page.rect.height-1683.78) > .1:
            raise ValueError('Unexpected calendar geometry')
        spans = [s for b in page.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
        glyphs = [s for s in spans if s['text'].isdigit() and 1 <= int(s['text']) <= 31
                  and s['bbox'][1] > 550 and any(abs(s['size']-size) < .02 for size in (12.96, 9.85))]
        panels = {}
        for span in glyphs:
            x, y, x1, y1 = span['bbox']
            panel = (0 if x < 420 else 1 if x < 800 else 2) + (3 if y > 850 else 0)
            panels.setdefault(panel, []).append(span)
        if set(panels) != set(range(6)):
            raise ValueError('Missing calendar month')
        drawings = page.get_drawings()
        textpage = page.get_textpage()
        fill_labels = {}
        # Some official cells contain older colored rectangles underneath the
        # final background. Visible pixels, not the list of PDF drawing objects,
        # decide which of these rectangles is actually shown to readers.
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False)
        samples = pix.samples
        def visible_colors(rect):
            pixels = Counter(tuple(samples[(y*pix.width+x)*3:(y*pix.width+x)*3+3])
                for y in range(max(0, int(rect.y0)+1), min(pix.height, int(rect.y1)), 2)
                for x in range(max(0, int(rect.x0)+1), min(pix.width, int(rect.x1)), 2))
            return {rgb for rgb, count in pixels.items() if count >= 4}
        def visible(color, pixels):
            rgb = tuple(round(c*255) for c in color)
            return any(max(abs(a-b) for a,b in zip(rgb,pixel)) <= 3 for pixel in pixels)
        for panel, values in panels.items():
            month = (page_no*6+panel+3) % 12+1
            year = 2026 if month >= 4 else 2027
            if sorted(int(s['text']) for s in values) != list(range(1, calendar.monthrange(year, month)[1]+1)):
                raise ValueError(f'Missing/duplicate official date labels: {year}-{month}')
            main = [s for s in values if s['size'] > 12]
            ys = sorted({round(s['bbox'][1], 1) for s in main})
            step = ys[1]-ys[0]
            if not 35 < step < 55:
                raise ValueError('Unexpected calendar row spacing')
            # Fit weekday centers from full-size date labels; verify every glyph.
            centers = {}
            for s in main:
                d = date(year, month, int(s['text']))
                centers.setdefault((d.weekday()+1)%7, []).append((s['bbox'][0]+s['bbox'][2])/2)
            centers = {w: sum(xs)/len(xs) for w, xs in centers.items()}
            for s in values:
                d = date(year, month, int(s['text']))
                w = (d.weekday()+1)%7
                week = (date(year, month, 1).weekday()+1)%7+d.day-1
                row = min(week//7, 4)
                top = ys[0]+row*step
                cx = centers[w]
                if abs((s['bbox'][0]+s['bbox'][2])/2-cx) > (22 if s['size'] < 10 else 2) or abs(s['bbox'][1]-top) > 18:
                    raise ValueError(f'Date glyph contradicts Gregorian grid: {d}, {s["bbox"]}, center={cx}, top={top}, step={step}')
                top_band = pymupdf.Rect(cx-21, top, cx+21, top+18)
                lower = pymupdf.Rect(cx-21, top+21, cx+21, top+step-1)
                visible_lower = visible_colors(lower)
                visible_top = visible_colors(top_band)
                fills = []
                for drawing in drawings:
                    if drawing['fill'] is None:
                        continue
                    rect = drawing['rect']
                    overlap = rect & lower
                    if overlap.width > 20 and overlap.height > 3:
                        color = tuple(round(c, 3) for c in drawing['fill'])
                        if color not in ((1., 1., 1.), (0.135, 0.094, 0.082)) and visible(color, visible_lower):
                            key = tuple(rect)
                            if key not in fill_labels:
                                fill_labels[key] = re.sub(r'\s+', '', page.get_textbox(rect+(-.2,-.2,.2,.2), textpage=textpage))
                            fills.append((color, fill_labels[key]))
                top_colors = {tuple(round(c, 3) for c in drawing['fill']) for drawing in drawings
                              if drawing['fill'] and (drawing['rect'] & top_band).width > 20
                              and (drawing['rect'] & top_band).height > 10
                              and visible(drawing['fill'], visible_top)}
                # Two dates share a fifth-row square in May, August and January.
                first = (date(year, month, 1).weekday()+1)%7
                shared = first+calendar.monthrange(year, month)[1] > 35 and row == 4 and w < first+calendar.monthrange(year, month)[1]-35
                observations[d.isoformat()] = {'fills': fills, 'top_colors': top_colors,
                    'text': re.sub(r'\s+', '', page.get_textbox(lower+(-1,-.4,1,.4), textpage=textpage)),
                    'shared_cell': shared, 'source_page': page_no+1}
    if len(observations) != 365:
        raise ValueError('Calendar must contain 365 distinct fiscal-year dates')
    return observations


IYO_COLORS = {(0.929, .733, .356): {'bottles'}, (.406,.703,.490): {'pet_bottles','non_burnable','hazardous'},
              (.815,.848,.456): {'textiles'}, (.915,.648,.710): {'cans'}, (.624,.664,.797): {'paper'}}
FUTAMI_COLORS = {(.379,.678,.528): 'A', (.916,.743,.360): 'B', (.862,.592,.188): 'C',
                 (.385,.702,.811): 'D', (.895,.632,.703): 'E', (.743,.637,.458): 'F', (.604,.642,.792): 'G'}
NAKA_COLORS = {(.713,.848,.921): 'sare', (.894,.709,.351): 'naka', (.754,.824,.532): 'ide'}


def observed_types(observation, day, area):
    """Interpret the official legend/geographic header, not Nth-week rules."""
    region = area['rule_profile_id']
    d = date.fromisoformat(day)
    codes = set()
    if region in ('iyo', 'futami'):
        if (.984,.970,.864) in observation['top_colors'] and d.isoweekday() in area['burnable_weekdays']:
            codes.add('burnable')
        if (.822,.906,.952) in observation['top_colors'] and d.isoweekday() == area['plastic_weekday']:
            codes.add('plastic_packaging')
    for color, text in observation['fills']:
        if region == 'iyo' and d.isoweekday() == area['nonburnable_weekday']:
            codes.update(IYO_COLORS.get(color, set()))
        elif region == 'futami' and FUTAMI_COLORS.get(color) == area['official_group']:
            codes.update(['bottles','cans','hazardous','non_burnable'])
        elif region == 'nakayama':
            text = observation['text']
            if color == (.964,.946,.760) and '燃える' in text:
                codes.add('burnable')
            if NAKA_COLORS.get(color) == area['official_group']:
                if 'プラスチック' in text:
                    codes.add('plastic_packaging')
                if '燃えない' in text:
                    codes.update(['bottles','cans','hazardous','non_burnable'])
                if 'ペットボトル' in text:
                    codes.update(['pet_bottles','textiles'])
            if color == (.805,.808,.898) and '紙類' in text:
                codes.add('paper')
    if region == 'futami':
        label = '下灘' if area['subregion'] == 'lower' else '上灘'
        if label in observation['text']:
            if 'ペットボトル' in observation['text']:
                codes.add('pet_bottles')
            if '布' in observation['text'] and '紙類' in observation['text']:
                codes.update(['textiles','paper'])
    if area.get('unverified_collection_types'):
        codes -= set(area['unverified_collection_types'])
        if (d.day-1)//7+1 != 2:
            codes -= {'cans','textiles'}
    return sorted(codes)


def year_end_types(source_dir, area):
    """Read the dated exception table (including merged cells and blank dates).

    Table boundaries were checked on each original PDF. This extraction does
    not read calendar_rules.json overrides or compute weekday occurrences.
    """
    import pymupdf
    layouts = {
        'iyo': ('r8iyo.pdf', [261.6,355.8,451.4,581.2,675.1,769.4,863.7,957.8,1052,1146],
                [848.2,876.9,905.2,933.3,961.5,990.4]),
        'futami': ('r8hutami.pdf', [282.3,374,466,595,686.7,778.3,870.5,962.9,1054.7,1146.7],
                   [835.9,858.2,880.5,902.8,925.2,947.4,969.7,992]),
        'nakayama': ('r8nakayama.pdf', [312.4,443.2,574.1,745.9,876.6,1007.1,1138.1],
                     [860.7,903.2,945.4,987.6])}
    profile = area['rule_profile_id']
    filename, xs, ys = layouts[profile]
    page = pymupdf.open(source_dir/filename)[1]
    if profile == 'iyo':
        row = {'iyo-south':0,'iyo-hiraoka':0,'iyo-central':1,'iyo-north':2,'iyo-west':3,'iyo-east':4}[area['id'][6:]]
    elif profile == 'futami':
        row = ord(area['official_group'])-ord('A')
    else:
        row = {'sare':0,'naka':1,'ide':2}[area['official_group']]
    closed = ''.join(page.get_text(clip=pymupdf.Rect(xs[2],ys[0],xs[3],ys[-1])).split())
    if closed != '収集休み':
        raise ValueError('Official year-end closure table changed')
    dates = ['2026-12-29','2026-12-30',None,'2027-01-04','2027-01-05','2027-01-06']
    if profile != 'nakayama':
        dates += ['2027-01-07','2027-01-08','2027-01-09']
    result = {day: [] for day in ['2026-12-31','2027-01-01','2027-01-02','2027-01-03']}
    for column, day in enumerate(dates):
        if day is None:
            continue
        y0,y1 = (ys[0],ys[-1]) if profile=='nakayama' and column in (1,5) else (ys[row],ys[row+1])
        rect = pymupdf.Rect(xs[column]+.7,y0+.4,xs[column+1]-.7,y1-.4)
        text = re.sub(r'\s+', '', page.get_text(clip=rect))
        codes = set()
        for label,code in [('燃えるごみ','burnable'),('びん類','bottles'),('布類','textiles'),
                           ('かん類','cans'),('紙類','paper'),('ペットボトル','pet_bottles'),
                           ('その他','non_burnable'),('有害','hazardous')]:
            if label in text:
                codes.add(code)
        if 'プラスチック製容器包装' in text or 'プラ容器包装' in text:
            codes.add('plastic_packaging')
        if text and not codes:
            raise ValueError(f'Unrecognized year-end table cell: {filename}, {row}, {day}, {text}')
        result[day] = sorted(codes)
    return result
