from __future__ import print_function

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from DreamOSatSatellites.SatBeamsClient import (  # noqa: E402
    build_satellites_xml,
    orbital_tenths,
)


def test_xml_conversion():
    east = {
        "orbital_position": 420,
        "display": "42.0 E",
        "satellites": [{"name": "Turksat 5B"}],
    }
    west = {
        "orbital_position": -10,
        "display": "1.0 W",
        "satellites": [{"name": "West Test"}],
    }
    transponder = {
        "frequency": 11012,
        "symbol_rate": 30000,
        "polarisation": "H",
        "fec": "3/4",
        "encoding": "DVB-S2",
        "modulation": "8PSK",
    }
    xml, stats = build_satellites_xml(
        [(east, [transponder]), (west, [dict(transponder, polarisation="V")])]
    )
    text = xml.decode("utf-8")
    assert 'position="420"' in text
    assert 'position="-10"' in text
    assert 'frequency="11012000"' in text
    assert 'symbol_rate="30000000"' in text
    assert 'polarization="0"' in text
    assert 'fec_inner="3"' in text
    assert 'system="1"' in text
    assert 'modulation="2"' in text
    assert stats == {"satellites": 2, "transponders": 2, "skipped": 0}


def test_position_conversion():
    assert orbital_tenths(42) == 420
    assert orbital_tenths(359) == -10


def test_real_xml_positions():
    from xml.etree import ElementTree as ET
    from DreamOSatSatellites.SatBeamsClient import SatBeamsError
    position = {"orbital_position": -350, "satellites": [
        {"id": 1, "name": "Satellite A", "real_pos": 325.5},
        {"id": 2, "name": "Satellite B", "real_pos": 325.2}]}
    tp = {"frequency": 11012, "symbol_rate": 30000, "polarisation": "H"}
    xml, stats = build_satellites_xml([(position, [dict(tp, satellite_id=1),
        dict(tp, satellite_id=2, frequency=12000)])])
    root = ET.fromstring(xml)
    sats = {sat.get("position"): sat for sat in root}
    assert set(sats) == {"-345", "-348"}
    assert "34.5W" in sats["-345"].get("name")
    assert "Satellite B" not in sats["-345"].get("name")
    assert sats["-345"][0].get("frequency") == "11012000"
    assert sats["-348"][0].get("frequency") == "12000000"
    xml, stats = build_satellites_xml([(position, [dict(tp,
        satellite_id=999, satellite_name="Old satellite", position=325)])])
    root = ET.fromstring(xml)
    old = [sat for sat in root if sat.get("position") == "-350"][0]
    assert "Old satellite" in old.get("name")
    assert len(old) == 1
    try:
        build_satellites_xml([(position, [tp])])
    except SatBeamsError:
        pass
    else:
        raise AssertionError("Ambiguous satellite must not be assigned arbitrarily")


if __name__ == "__main__":
    test_xml_conversion()
    test_position_conversion()
    test_real_xml_positions()
    print("OK")
