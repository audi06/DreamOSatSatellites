# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from . import _
import re
try:
    from html import unescape
except ImportError:
    from HTMLParser import HTMLParser
    unescape = HTMLParser().unescape
from .SatBeamsClient import SatBeamsClient, SatBeamsError, Request, urlopen


def clean(value):
    return ' '.join(unescape(re.sub(r'<[^>]*>', ' ', value)).split())


def table_rows(html):
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', html, re.I | re.S):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.I | re.S)
        if cells:
            yield cells, [clean(cell) for cell in cells]


class KingOfSatClient(SatBeamsClient):
    def _html(self, path):
        response = urlopen(Request('https://kingofsat.net/' + path,
            headers={'User-Agent': 'Mozilla/5.0'}), timeout=self.timeout)
        try:
            return response.read().decode('utf-8', 'replace')
        finally:
            response.close()

    def get_positions(self):
        groups = {}
        for cells, texts in table_rows(self._html('satellites')):
            match = re.search(r'href=[\"\'](?:https://kingofsat.net/)?/?pos-([0-9.]+)([EW])', ''.join(cells), re.I)
            if not match:
                continue
            value = float(match.group(1)) * (1 if match.group(2).upper() == 'E' else -1)
            pos = int(round(value * 10))
            names = re.findall(r'href=[\"\'][^\"\']*sat-[^\"\']*[\"\'][^>]*>(.*?)</a>', ''.join(cells), re.I | re.S)
            item = groups.setdefault(pos, {'orbital_position': pos, 'rounded_pos': value,
                'key': 'kos:%s' % pos, 'display': self._display_position(pos),
                'rounded_pos_display': self._display_position(pos), 'satellites': []})
            for name in names:
                name = clean(name)
                if name and not any(s['name'] == name for s in item['satellites']):
                    item['satellites'].append({'name': name, 'real_pos': value})
        if not groups:
            raise SatBeamsError(_("Could not read KingOfSat satellite table"))
        return [groups[key] for key in sorted(groups)]

    def get_transponders(self, position):
        value = float(position)
        path = 'pos-%s%s' % (('%g' % abs(value)), 'E' if value >= 0 else 'W')
        result = []
        html = self._html(path)
        if re.search(r'AUCUN\s+RESULTAT\s+TROUV|NO\s+RESULTS?\s+FOUND', clean(html), re.I):
            return []
        for cells, texts in table_rows(html):
            if len(texts) < 9 or not re.match(r'^\d+(?:\.\d+)?\s*°\s*[EW]$', texts[0]):
                continue
            if not re.match(r'^\d+(?:\.\d+)?$', texts[2]) or texts[3] not in ('H', 'V', 'L', 'R'):
                continue
            sr = re.search(r'(\d+)\s+(\d+/\d+|Auto)', texts[8], re.I)
            if not sr:
                continue
            if not texts[6].startswith('DVB-S'):
                continue
            satellite_link = re.search(r'<a\b[^>]*href=[\"\'][^\"\']*sat-[^\"\']*[\"\'][^>]*>(.*?)</a>', cells[1], re.I | re.S)
            satellite_name = clean(satellite_link.group(1)) if satellite_link else clean(re.sub(r'<sup\b[^>]*>.*?</sup>', '', cells[1], flags=re.I | re.S))
            result.append({'frequency': texts[2], 'symbol_rate': sr.group(1),
                'polarisation': texts[3], 'fec': sr.group(2), 'encoding': texts[6],
                'modulation': texts[7], 'satellite_name': satellite_name, 'position': value})
        if not result:
            raise SatBeamsError(_("KingOfSat transponder table is empty or has changed: ") + path)
        return result
