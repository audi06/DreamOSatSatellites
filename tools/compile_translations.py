"""Compile this project's singular gettext PO catalogs (Python 3, no dependencies).

For advanced PO features use GNU msgfmt instead.
"""
import ast
import gettext
import pathlib
import re
import struct

folder = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'DreamOSatSatellites' / 'locale'
for source in folder.glob('*.po'):
    messages = {}
    key = value = None
    field = None
    for line in source.read_text(encoding='utf-8').splitlines() + ['msgid ""']:
        if line.startswith('msgid '):
            if key is not None:
                messages[key] = value or ''
            key, value, field = ast.literal_eval(line[6:]), '', 'key'
        elif line.startswith('msgstr '):
            value, field = ast.literal_eval(line[7:]), 'value'
        elif line.startswith('"'):
            if field == 'key':
                key += ast.literal_eval(line)
            else:
                value += ast.literal_eval(line)
        elif line and not line.startswith('#'):
            raise ValueError('Unsupported PO syntax: ' + line)
    placeholders = re.compile(r'%(?:\([^)]+\))?[#0 +\-]*\d*(?:\.\d+)?[diouxXeEfFgGcrs]')
    for key, value in messages.items():
        if key and value and placeholders.findall(key) != placeholders.findall(value):
            raise ValueError('Translation placeholder mismatch: ' + key)
    pairs = sorted((k.encode('utf-8'), v.encode('utf-8')) for k, v in messages.items())
    count = len(pairs)
    start = 28 + count * 16
    originals = b''
    translations = b''
    ot = []
    tt = []
    for key, value in pairs:
        ot.append((len(key), start + len(originals)))
        originals += key + b'\0'
    for key, value in pairs:
        tt.append((len(value), start + len(originals) + len(translations)))
        translations += value + b'\0'
    blob = struct.pack('<7I', 0x950412de, 0, count, 28, 28 + count * 8, 0, 0)
    blob += b''.join(struct.pack('<2I', *p) for p in ot + tt) + originals + translations
    output = folder / source.stem / 'LC_MESSAGES' / 'DreamOSatSatellites.mo'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(blob)
    with output.open('rb') as handle:
        catalog = gettext.GNUTranslations(handle)
    assert catalog.gettext('Close') == messages['Close']
    print(source.stem, len(messages) - 1, 'translations verified')
