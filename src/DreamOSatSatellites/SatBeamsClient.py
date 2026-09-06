# -*- coding: utf-8 -*-
from __future__ import absolute_import
from . import _

import json
import math
import re
import unicodedata
import os
import shutil
import ssl
import time
from xml.etree import ElementTree as ET

try:
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - Python 2 fallback for older images
    from urllib import urlencode
    from urllib2 import Request, urlopen


API_ROOT = "https://satbeams.com/api/v1"
POSITIONS_URL = API_ROOT + "/positions"
CHANNELS_URL = API_ROOT + "/channels"
USER_AGENT = "Enigma2-SatBeamsSatellites/1.0"


class SatBeamsError(Exception):
    pass


def orbital_tenths(raw_position):
    """Convert SatBeams' 0..359 longitude to Enigma2's signed tenths."""
    value = float(raw_position)
    if value > 180.0:
        value -= 360.0
    return int(round(value * 10.0))


def position_query_value(raw_position):
    value = float(raw_position)
    if value.is_integer():
        return str(int(value))
    return ("%.1f" % value).rstrip("0").rstrip(".")


def real_position_sort_key(position):
    """Sort by precise signed longitude, retaining rounded API query IDs."""
    values = []
    for satellite in position.get("satellites") or []:
        try:
            value = float(satellite.get("real_pos"))
        except (TypeError, ValueError):
            continue
        if math.isnan(value) or math.isinf(value):
            continue
        if value > 180.0:
            value -= 360.0
        values.append(value)
    fallback = position["orbital_position"] / 10.0
    return (min(values) if values else fallback, fallback)


def _number(value, multiplier=1):
    try:
        return int(round(float(value) * multiplier))
    except (TypeError, ValueError):
        return 0


POLARISATION = {
    "H": 0,
    "HORIZONTAL": 0,
    "V": 1,
    "VERTICAL": 1,
    "L": 2,
    "LEFT": 2,
    "LHC": 2,
    "R": 3,
    "RIGHT": 3,
    "RHC": 3,
}

FEC = {
    "AUTO": 0,
    "1/2": 1,
    "2/3": 2,
    "3/4": 3,
    "5/6": 4,
    "7/8": 5,
    "8/9": 6,
    "3/5": 7,
    "4/5": 8,
    "9/10": 9,
    "6/7": 10,
    "NONE": 15,
}

MODULATION = {
    "AUTO": 0,
    "QPSK": 1,
    "8PSK": 2,
    "16QAM": 3,
    "QAM16": 3,
    "16APSK": 4,
    "32APSK": 5,
}


class SatBeamsClient(object):
    def __init__(self, timeout=25, page_size=40):
        self.timeout = timeout
        self.page_size = page_size

    def _get_json(self, url):
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            context = ssl.create_default_context()
            response = urlopen(request, timeout=self.timeout, context=context)
            raw = response.read()
        except Exception as error:
            raise SatBeamsError(_("API connection error: %s") % error)

        try:
            if not isinstance(raw, str):
                raw = raw.decode("utf-8-sig")
            payload = json.loads(raw)
        except Exception as error:
            raise SatBeamsError(_("Invalid JSON response: %s") % error)

        if not isinstance(payload, dict) or payload.get("status") != 0:
            raise SatBeamsError(_("SatBeams returned an unsuccessful response"))
        return payload.get("data")

    def get_positions(self):
        rows = self._get_json(POSITIONS_URL)
        if not isinstance(rows, list):
            raise SatBeamsError(_("Unexpected satellite list format"))

        result = []
        for row in rows:
            if not isinstance(row, dict) or row.get("rounded_pos") is None:
                continue
            item = dict(row)
            item["orbital_position"] = orbital_tenths(row["rounded_pos"])
            item["key"] = str(row.get("rounded_pos_id", row["rounded_pos"]))
            actual_positions = sorted(set(
                orbital_tenths(satellite["real_pos"])
                for satellite in row.get("satellites") or []
                if satellite.get("real_pos") is not None
            ))
            item["display"] = " / ".join(self._display_position(value)
                for value in actual_positions) or self._display_position(item["orbital_position"])
            result.append(item)

        result.sort(key=real_position_sort_key)
        return result

    def get_transponders(self, position):
        offset = 0
        total = None
        collected = []

        for _page in range(100):
            query = urlencode(
                {
                    "sort": "freq",
                    "dir": "asc",
                    "position": position_query_value(position),
                    "limit": self.page_size,
                    "offset": offset,
                    "init_filters": 1 if offset == 0 else 0,
                }
            )
            data = self._get_json(CHANNELS_URL + "?" + query)
            if not isinstance(data, dict):
                raise SatBeamsError(_("Unexpected frequency list format"))

            returned_position = data.get("position") or {}
            if isinstance(returned_position, dict) and returned_position.get("rounded_pos") is not None:
                if orbital_tenths(returned_position["rounded_pos"]) != orbital_tenths(position):
                    raise SatBeamsError(_("API returned a different satellite position; please retry"))

            page = data.get("transponders") or []
            if not isinstance(page, list):
                raise SatBeamsError(_("Unexpected transponder list format"))
            collected.extend(page)

            try:
                total = int(data.get("total", len(collected)))
            except (TypeError, ValueError):
                total = len(collected)
            offset += len(page)
            if not page or offset >= total:
                break
        else:
            raise SatBeamsError(_("API pagination limit exceeded"))

        return collected

    @staticmethod
    def _display_position(tenths):
        direction = "E" if tenths >= 0 else "W"
        return "%.1f° %s" % (abs(tenths) / 10.0, direction)


def satellite_name(position, transponders):
    def normalize(value):
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii').strip()

    names = []
    for satellite in position.get("satellites") or []:
        name = normalize(satellite.get("name") or "")
        if name and name not in names:
            names.append(name)
    for transponder in transponders:
        name = normalize(transponder.get("satellite_name") or "")
        for known in sorted(names, key=len, reverse=True):
            if name.startswith(known + " ") and re.match(r'^\d+$', name[len(known):].strip()):
                name = known
                break
        if name and name not in names:
            names.append(name)

    pos = position["orbital_position"]
    label = "%.1f%s" % (abs(pos) / 10.0, "E" if pos >= 0 else "W")
    names.sort()
    parts = [name.split(' ', 1) for name in names]
    if parts and all(len(part) == 2 and part[0] == parts[0][0] for part in parts):
        body = parts[0][0] + ' ' + '/'.join(part[1] for part in parts)
    else:
        body = ' / '.join(names)
    result = label + (' ' + body if body else '')
    if len(result) > 64:
        result = result[:61].rstrip(' /') + '...'
    return result


def transponder_attributes(row):
    frequency = _number(row.get("frequency"), 1000)
    symbol_rate = _number(row.get("symbol_rate"), 1000)
    if frequency <= 0 or symbol_rate <= 0:
        return None

    polarisation = str(row.get("polarisation") or "").strip().upper()
    if polarisation not in POLARISATION:
        return None

    encoding = str(row.get("encoding") or "DVB-S").strip().upper()
    # OE 2.6 images do not all expose DVB-S2X as a distinct XML enum.
    # Treat S2X as S2 so that the generated file remains loadable everywhere.
    system = 0 if encoding == "DVB-S" else 1
    modulation_name = str(row.get("modulation") or "").strip().upper()
    default_modulation = 1 if system == 0 else 0

    return {
        "frequency": str(frequency),
        "symbol_rate": str(symbol_rate),
        "polarization": str(POLARISATION[polarisation]),
        "fec_inner": str(FEC.get(str(row.get("fec") or "AUTO").upper(), 0)),
        "system": str(system),
        "modulation": str(MODULATION.get(modulation_name, default_modulation)),
    }


def real_position_groups(position_rows):
    """Assign each transponder to its satellite's actual orbital position."""
    groups = {}
    for position, rows in position_rows:
        satellites = position.get("satellites") or []
        locations = []
        for satellite in satellites:
            try:
                location = orbital_tenths(satellite.get("real_pos"))
            except (TypeError, ValueError, OverflowError):
                location = position["orbital_position"]
            locations.append((satellite, location))
            group = groups.setdefault(location, ({"orbital_position": location,
                "satellites": []}, []))
            if satellite not in group[0]["satellites"]:
                group[0]["satellites"].append(satellite)
        for row in rows:
            matches = [loc for satellite, loc in locations
                if row.get("satellite_id") is not None
                and satellite.get("id") is not None
                and str(row["satellite_id"]) == str(satellite["id"])]
            if not matches:
                matches = [loc for satellite, loc in locations
                    if row.get("satellite_name")
                    and row["satellite_name"] == satellite.get("name")]
            if not matches:
                # The channels endpoint also contains satellites absent from
                # the current positions catalogue. Use their explicit position,
                # never assign them to an arbitrary catalogue satellite.
                if row.get("position") is not None:
                    try:
                        reported = orbital_tenths(row["position"])
                    except (TypeError, ValueError, OverflowError):
                        raise SatBeamsError(_("Invalid transponder position"))
                    distance = abs(reported - position["orbital_position"])
                    if min(distance, 3600 - distance) > 5:
                        raise SatBeamsError(_("API returned a transponder outside the selected position: %s") % row.get("satellite_name", "?"))
                    matches = [reported]
                elif row.get("satellite_id") is not None or row.get("satellite_name"):
                    raise SatBeamsError(_("Missing satellite position in API record: %s") % row.get("satellite_name", "?"))
                else:
                    matches = list(set(loc for satellite, loc in locations))
            if len(set(matches)) > 1:
                raise SatBeamsError(_("Could not match transponder to actual satellite position: %s") % row.get("satellite_name", row.get("id", "?")))
            location = matches[0] if matches else position["orbital_position"]
            group = groups.setdefault(location, ({"orbital_position": location,
                "satellites": []}, []))
            group[1].append(row)
    return [groups[key] for key in sorted(groups)]


def build_satellites_xml(position_rows):
    """Build XML from [(position_dict, transponder_list), ...]."""
    root = ET.Element("satellites")
    stats = {"satellites": 0, "transponders": 0, "skipped": 0}

    for position, rows in real_position_groups(position_rows):
        sat = ET.SubElement(
            root,
            "sat",
            {
                "name": satellite_name(position, rows),
                "flags": "1",
                "position": str(position["orbital_position"]),
            },
        )
        seen = set()
        for row in rows:
            attributes = transponder_attributes(row)
            if attributes is None:
                stats["skipped"] += 1
                continue
            key = tuple(attributes[name] for name in sorted(attributes))
            if key in seen:
                continue
            seen.add(key)
            ET.SubElement(sat, "transponder", attributes)
            stats["transponders"] += 1
        stats["satellites"] += 1

    _indent(root)
    body = ET.tostring(root, encoding="utf-8")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + body + b"\n", stats


def _indent(element, level=0):
    indentation = "\n" + ("\t" * level)
    child_indentation = "\n" + ("\t" * (level + 1))
    if len(element):
        if not element.text or not element.text.strip():
            element.text = child_indentation
        for child in element:
            _indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = child_indentation
        element[-1].tail = indentation
    elif level and (not element.tail or not element.tail.strip()):
        element.tail = indentation


def install_xml(xml_bytes, destination="/etc/tuxbox/satellites.xml"):
    directory = os.path.dirname(destination)
    if not os.path.isdir(directory):
        os.makedirs(directory)

    backup = None
    if os.path.exists(destination):
        backup = "%s.bak_%s" % (destination, time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(destination, backup)

    temporary = destination + ".satbeams.tmp"
    try:
        with open(temporary, "wb") as output:
            output.write(xml_bytes)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o644)
        os.rename(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup
