"""Strict offline readers for Ikata's reviewed guide and FY2026 PDFs.

Calendar dates come from printed date/symbol pairs, not an inferred recurrence.
An independent pass addresses raster cells by weekday/month geometry and compares
their backgrounds with the nine rendered legend swatches (including blank days).
Dictionary rows use individual PDF sub-rectangles, not a compound path's bounding
box. Every label is also counted in the text layer and checked against its colour.
"""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date
from pathlib import Path
import re

CATEGORY_CODES = {'可燃': 'burnable', '埋立': 'landfill', 'びん': 'bottles', 'かん': 'cans',
                  'ペット': 'pet_bottles', 'プラ': 'plastic_packaging', '発泡': 'styrofoam',
                  '紙': 'paper_textiles', '有害': 'hazardous', '粗大': 'bulky', '禁止': 'not_collected'}
SYMBOLS = {'燃': 'burnable', '埋': 'landfill', 'ビン': 'bottles', '缶': 'cans',
           'PET': 'pet_bottles', 'プラ': 'plastic_packaging', '発': 'styrofoam',
           '紙': 'paper_textiles', '有': 'hazardous'}
DICTIONARY_PARTS = ('10413.pdf', '10414.pdf', '10415.pdf', '10416.pdf', '10417.pdf')
# Only these exact printed cells differ from the legend. Page 27's battery
# wording is contradicted by the explicit prohibitions on guide pages 14/49;
# ikata_data applies that independently documented category correction.
REVIEWED_PALETTE_VARIANTS = {
    (27, '乾電池（ボタン型・充電式）', '有害'): (.901, .0, .07),
    (39, '入浴剤の容器（プラスチック製）', 'プラ'): (.0, .55, .811),
}


def page_lines(page):
    return [line for block in page.get_text('rawdict')['blocks'] for line in block.get('lines', [])]


def text_in(lines, rect):
    """Keep overhanging glyphs by their centres; preserve wrapped row text."""
    import pymupdf
    return ''.join(''.join(c['c'] for s in line['spans'] for c in s['chars']
        if rect.contains(pymupdf.Point((c['bbox'][0]+c['bbox'][2])/2,
                                      (c['bbox'][1]+c['bbox'][3])/2))) for line in lines).strip()


def dictionary_page(page, palette=None, printed_page=None):
    import numpy as np
    import pymupdf
    lines = page_lines(page)
    cells = []
    for drawing in page.get_drawings():
        for command in drawing['items']:
            if command[0] == 're':
                rect = command[1]
                if 31 < rect.width < 33 and rect.height > 24:
                    cells.append((rect, drawing['fill']))
    keys = [tuple(round(v, 2) for v in r) for r, _ in cells]
    if len(keys) != len(set(keys)) or not cells:
        raise ValueError('Missing or duplicate dictionary row rectangles')
    # Count the independent white classification text layer, including rows that
    # would have been lost by an incorrect geometry filter.
    labels = [re.sub(r'\s+', '', ''.join(c['c'] for c in span['chars']))
              for line in lines for span in line['spans'] if span['color'] == 0xffffff
              and span['bbox'][3]-span['bbox'][1] < 12]
    labels = Counter(label for label in labels if label in CATEGORY_CODES)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    rows = []
    for rect, fill in sorted(cells, key=lambda pair: (round(pair[0].x0), pair[0].y0)):
        label = re.sub(r'\s+', '', text_in(lines, rect))
        if label not in CATEGORY_CODES or fill is None:
            raise ValueError(f'Unknown dictionary label: {label!r}')
        item = text_in(lines, pymupdf.Rect(rect.x0-112.7, rect.y0, rect.x0+2, rect.y1))
        if palette is not None:
            expected_fill = REVIEWED_PALETTE_VARIANTS.get((printed_page, item, label), palette[label])
            if max(abs(a-b) for a, b in zip(fill, expected_fill)) > .002:
                raise ValueError(f'Dictionary label/legend colour mismatch: {printed_page} {item}')
        # Left strip has neither the white category text nor row border.
        rendered = rgb[int((rect.y0+3)*2):int((rect.y1-3)*2),
                       int((rect.x0+1)*2):int((rect.x0+3)*2)]
        expected = np.array(fill)*255
        if not len(rendered) or np.max(abs(np.median(rendered.reshape(-1, 3), axis=0)-expected)) > 3:
            raise ValueError('Dictionary label background/raster mismatch')
        note = text_in(lines, pymupdf.Rect(rect.x1-2, rect.y0, rect.x1+110, rect.y1))
        if not item:
            raise ValueError('Dictionary item is empty')
        rows.append({'item': item, 'source_category': label, 'category': CATEGORY_CODES[label],
                     'note': note, 'rect': [round(v, 3) for v in rect]})
    if Counter(r['source_category'] for r in rows) != labels:
        raise ValueError('Dictionary classification text count differs from row geometry')
    return rows


def extract_items(source: Path):
    import pymupdf
    rows = []
    full = pymupdf.open(source/'14759.pdf')
    first = pymupdf.open(source/DICTIONARY_PARTS[0])[0]
    palette = {}
    for drawing in first.get_drawings():
        for command in drawing['items']:
            if command[0] == 're' and drawing['fill']:
                rect = command[1]
                if 230 < rect.y0 < 340 and 40 < rect.width < 45:
                    label = re.sub(r'\s+', '', first.get_text(clip=rect))
                    palette[label] = drawing['fill']
    if set(palette) != set(CATEGORY_CODES):
        raise ValueError('Dictionary legend is incomplete')
    page_index = 22
    for filename in DICTIONARY_PARTS:
        for part_page, page in enumerate(pymupdf.open(source/filename), 1):
            extracted = dictionary_page(page, palette, page_index+1)
            # The currently published full guide and all five dictionary parts
            # must agree on every item, category and note, not just row counts.
            full_rows = dictionary_page(full[page_index], palette, page_index+1)
            fields = ('item', 'source_category', 'note')
            if [[r[k] for k in fields] for r in extracted] != [[r[k] for k in fields] for r in full_rows]:
                raise ValueError(f'Full/partial dictionary editions differ on page {page_index+1}')
            for row_number, row in enumerate(extracted, 1):
                rows.append({**row, 'item_id': f'ik-p{page_index+1:02}-{row_number:02}',
                             'source_page': page_index+1, 'source_file': filename, 'part_page': part_page})
            page_index += 1
    if page_index != 48:
        raise ValueError('Dictionary pages 23–48 are incomplete')
    return rows


def calendar_days(path: Path):
    import numpy as np
    import pymupdf
    doc = pymupdf.open(path)
    if len(doc) != 1 or abs(doc[0].rect.width-841.89) > .1:
        raise ValueError('Unexpected calendar layout')
    page = doc[0]
    words = page.get_text('words')
    headers = [w for w in words if re.match(r'\d+月\u3000ごみは', w[4])]
    if len(headers) != 12 or {int(w[4].split('月')[0]) for w in headers} != set(range(1, 13)):
        raise ValueError('Missing calendar month headers')
    if any('午前８時まで' not in w[4] for w in headers):
        raise ValueError('Collection cutoff changed')
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    # Use the rendered light background of each labelled legend, not hard-coded
    # RGB values that assume PDF CMYK and screen RGB are identical.
    palette = {}
    for symbol, code in SYMBOLS.items():
        word = next(w for w in words if w[4] == symbol and 100 < w[1] < 173)
        x, y = (word[0]+word[2])/2, (word[1]+word[3])/2
        containers = [d['rect'] for d in page.get_drawings() if d['fill']
                      and 100 < d['rect'].width < 102 and d['rect'].contains(pymupdf.Point(x, y))]
        if len(containers) != 1:
            raise ValueError('Calendar legend cannot be located')
        r = containers[0]
        palette[code] = rgb[round((r.y0+2)*2), round((r.x0+35)*2)].astype(int)
    result, audit = {}, {'printed_dates': 0, 'raster_cells': 0, 'symbol_counts': Counter(), 'closed_dates': []}
    seen_date_words = set()
    seen_symbols = set()
    for header in headers:
        month = int(header[4].split('月')[0]); year = 2026 if month >= 4 else 2027
        # Month/weekday addressing is independent of the date glyph's position.
        x0, y0 = header[0]-11.989, header[1]+34.892
        weekday_offset = (date(year, month, 1).weekday()+1) % 7
        for day in range(1, calendar.monthrange(year, month)[1]+1):
            row, col = divmod(weekday_offset+day-1, 7)
            cell = pymupdf.Rect(x0+col*53.856, y0+row*20.412, x0+(col+1)*53.856, y0+(row+1)*20.412)
            inside = [(i, w) for i, w in enumerate(words) if cell.contains(pymupdf.Point((w[0]+w[2])/2, (w[1]+w[3])/2))]
            dates = [(i, w) for i, w in inside if w[4].isdigit()]
            if len(dates) != 1 or dates[0][1][4] != str(day):
                raise ValueError(f'Date glyph/weekday mismatch {path.name} {year}-{month}-{day}')
            seen_date_words.add(dates[0][0])
            codes = set()
            for i, word in inside:
                if word[4] in SYMBOLS:
                    codes.add(SYMBOLS[word[4]]); seen_symbols.add(i)
                elif not word[4].isdigit() and word[4] != '休':
                    raise ValueError(f'Unknown collection symbol: {word[4]}')
            patch = rgb[round((cell.y0+2)*2):round((cell.y1-2)*2),
                        round((cell.x0+2)*2):round((cell.x1-2)*2)].astype(int)
            raster = raster_types(patch, palette)
            if codes != raster:
                raise ValueError(f'PDF symbol/raster mismatch {path.name} {year}-{month}-{day}: {codes} != {raster}')
            key = date(year, month, day).isoformat()
            if any(w[4] == '休' for _, w in inside):
                if codes:
                    raise ValueError('Closed day has a collection')
                audit['closed_dates'].append(key)
            result[key] = sorted(codes)
            audit['printed_dates'] += 1; audit['raster_cells'] += 1
            audit['symbol_counts'].update(codes)
    if len(seen_date_words) != 365 or len(result) != 365:
        raise ValueError('Incomplete fiscal-year calendar')
    # Do not ignore labels or date glyphs outside the expected grid.
    actual_dates = {i for i, w in enumerate(words) if w[4].isdigit() and w[1] > 200}
    actual_symbols = {i for i, w in enumerate(words) if w[4] in SYMBOLS and w[1] > 200}
    if actual_dates != seen_date_words or actual_symbols != seen_symbols:
        raise ValueError('Unassigned calendar dates or collection symbols')
    audit['closed_dates'].sort()
    audit['symbol_counts'] = dict(sorted(audit['symbol_counts'].items()))
    return dict(sorted(result.items())), audit


def raster_types(pixels, palette):
    """Recognise each visible light legend colour, retaining split/multi bands."""
    import numpy as np
    if pixels.size == 0:
        raise ValueError('Empty raster cell')
    return {code for code, color in palette.items()
            if np.mean(np.max(abs(pixels-color), axis=-1) <= 3) > .12}
