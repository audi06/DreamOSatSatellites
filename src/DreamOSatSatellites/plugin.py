# -*- coding: utf-8 -*-
from __future__ import absolute_import
from . import _

import json
import re
import sys
import os

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.MenuList import MenuList
from Components.config import config, configfile, ConfigSubsection, ConfigSelection, ConfigText
from Screens.ChoiceBox import ChoiceBox
from enigma import getDesktop, eListboxPythonMultiContent, gFont
from Components.MultiContent import MultiContentEntryText
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from twisted.internet import threads

from .SatBeamsClient import (
    SatBeamsClient,
    SatBeamsError,
    build_satellites_xml,
    install_xml,
)
from .KingOfSatClient import KingOfSatClient


PLUGIN_NAME = "DreamOSatSatellites"
PLUGIN_VERSION = "1.4.0"
PLUGIN_LICENSE = "GPL-3.0"
DESTINATION = "/etc/tuxbox/satellites.xml"

if not hasattr(config.plugins, "satbeamssatellites"):
    config.plugins.satbeamssatellites = ConfigSubsection()
    config.plugins.satbeamssatellites.skin = ConfigSelection(
        default="hd", choices=[("hd", "HD"), ("fhd", "FHD"), ("4k", "4K")])
    config.plugins.satbeamssatellites.profiles = ConfigText(default="{}", fixed_size=False)
settings = config.plugins.satbeamssatellites


def scaled_skin(skin):
    desktop = getDesktop(0).size()
    scale = min({"hd": 1.0, "fhd": 1.5, "4k": 3.0}[settings.skin.value],
                desktop.width() / 1280.0, desktop.height() / 720.0)
    def pair(match):
        return '%s="%d,%d"' % (match.group(1), int(int(match.group(2)) * scale),
                                   int(int(match.group(3)) * scale))
    skin = re.sub(r'(position|size)="(\d+),(\d+)"', pair, skin)
    skin = re.sub(r'Regular;(\d+)', lambda m: 'Regular;%d' % int(int(m.group(1)) * scale), skin)
    return re.sub(r'itemHeight="(\d+)"', lambda m: 'itemHeight="%d"' % int(int(m.group(1)) * scale), skin)


class SatBeamsSelection(Screen):
    skin = """
    <screen name="SatBeamsSelection" position="center,center" size="1120,650" title="DreamOSatSatellites">
        <widget name="title" position="25,18" size="1070,42" font="Regular;30" />
        <widget name="list" position="25,70" size="1070,470" scrollbarMode="showOnDemand" />
        <widget name="status" position="25,548" size="1070,38" font="Regular;22" />
        <widget name="key_red" position="25,602" size="245,34" font="Regular;22" halign="center" backgroundColor="#9f1313" foregroundColor="#ffffff" />
        <widget name="key_green" position="295,602" size="245,34" font="Regular;22" halign="center" backgroundColor="#1f771f" foregroundColor="#ffffff" />
        <widget name="key_yellow" position="565,602" size="245,34" font="Regular;22" halign="center" backgroundColor="#9f8b13" foregroundColor="#ffffff" />
        <widget name="key_blue" position="835,602" size="260,34" font="Regular;22" halign="center" backgroundColor="#164f9f" foregroundColor="#ffffff" />
    </screen>
    """

    def __init__(self, session, source="satbeams"):
        self.skin = scaled_skin(type(self).skin)
        Screen.__init__(self, session)
        self.source = source
        self.source_name = "KingOfSat" if source == "kingofsat" else "SatBeams"
        self.client = KingOfSatClient() if source == "kingofsat" else SatBeamsClient()
        self.positions = []
        self.selected = set()
        self.busy = False
        self.closed = False

        self["title"] = Label(_("%s satellite positions") % self.source_name)
        self["list"] = MenuList([], content=eListboxPythonMultiContent)
        desktop = getDesktop(0).size()
        self.list_scale = min({"hd": 1.0, "fhd": 1.5, "4k": 3.0}[settings.skin.value],
            desktop.width() / 1280.0, desktop.height() / 720.0)
        self["list"].l.setFont(0, gFont("Regular", int(25 * self.list_scale)))
        self["list"].l.setItemHeight(int(34 * self.list_scale))
        self["status"] = Label(_("Preparing satellite list..."))
        self["key_red"] = Label(_("Close"))
        self["key_green"] = Label(_("Select all"))
        self["key_yellow"] = Label(_("Clear all"))
        self["key_blue"] = Label(_("Download and create"))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions"],
            {
                "menu": self.openSettings,
                "cancel": self.close,
                "red": self.close,
                "ok": self.toggleCurrent,
                "green": self.selectAll,
                "yellow": self.clearAll,
                "blue": self.requestBuild,
                "up": self["list"].up,
                "down": self["list"].down,
                "left": self["list"].pageUp,
                "right": self["list"].pageDown,
            },
            -1,
        )
        self.onLayoutFinish.append(self.loadPositions)
        self.onClose.append(self._onClose)

    def openSettings(self):
        if self.busy:
            return
        self.session.openWithCallback(self._menuChosen, ChoiceBox,
            title=_("DreamOSatSatellites - Menu"), list=[
                (_("Profiles (1-5)"), "profiles"),
                (_("Regional selection"), "regions"),
                (_("Skin (4K / FHD / HD)"), "skin"),
                (_("About / Author / License"), "about")])

    def _menuChosen(self, choice):
        if not choice:
            return
        if choice[1] == "about":
            self.session.open(MessageBox,
                _("DreamOSatSatellites v%s\nBy audi06_19\n\nEmail: info@dreamosat-forum.com\nGitHub: https://github.com/audi06\nSupport forum: https://www.dreamosat-forum.com\nLicense: %s\n\nData sources: https://satbeams.com\nKingOfSat: https://kingofsat.net") % (PLUGIN_VERSION, PLUGIN_LICENSE),
                MessageBox.TYPE_INFO)
        elif choice[1] == "profiles":
            self.session.openWithCallback(self._profileChosen, ChoiceBox,
                title=_("Select profile"), list=[(_("Profile %d") % n, str(n)) for n in range(1, 6)])
        elif choice[1] == "regions":
            self.session.openWithCallback(self._regionChosen, ChoiceBox,
                title=_("Add region (orbital ranges)"), list=[
                    (_("All"), "all"), (_("Add Europe (0-60E)"), "europe"),
                    (_("Add Atlantic (60W-0)"), "atlantic"),
                    (_("Add America (180W-60W)"), "america"),
                    (_("Add Asia (60E-180E)"), "asia")])
        else:
            self.session.openWithCallback(self._skinChosen, ChoiceBox,
                title=_("Screen size"), list=[("4K", "4k"), ("FHD", "fhd"), ("HD", "hd")])

    def _profileChosen(self, choice):
        if choice:
            slot = choice[1]
            self.session.openWithCallback(self._profileAction, ChoiceBox,
                title=_("Profile %s") % slot, list=[
                    (_("Save selected satellites"), (slot, "save")),
                    (_("Load profile"), (slot, "load"))])

    def _profileAction(self, choice):
        if not choice:
            return
        slot, action = choice[1]
        if self.source != "satbeams":
            slot = self.source + ":" + slot
        try:
            profiles = json.loads(settings.profiles.value)
            if not isinstance(profiles, dict):
                profiles = {}
        except (ValueError, TypeError):
            profiles = {}
        if action == "save":
            profiles[slot] = sorted(self.selected)
            settings.profiles.value = json.dumps(profiles)
            settings.profiles.save()
            configfile.save()
            self["status"].setText(_("Profile %s saved (%d positions)") % (slot, len(self.selected)))
        elif slot in profiles:
            available = set(item["key"] for item in self.positions)
            self.selected = set(profiles[slot]) & available
            self._refreshList()
            self._selectionStatus()
        else:
            self["status"].setText(_("Profile %s has not been saved yet") % slot)

    def _regionChosen(self, choice):
        if not choice:
            return
        region = choice[1]
        for item in self.positions:
            p = item["orbital_position"]
            if (region == "all" or (region == "europe" and 0 <= p < 600)
                    or (region == "atlantic" and -600 <= p < 0)
                    or (region == "america" and p < -600)
                    or (region == "asia" and p >= 600)):
                self.selected.add(item["key"])
        self._refreshList()
        self._selectionStatus()

    def _skinChosen(self, choice):
        if choice:
            settings.skin.value = choice[1]
            settings.skin.save()
            configfile.save()
            self.session.open(MessageBox,
                _("Skin saved. Close and reopen the plugin to apply. Size is limited to your screen resolution."),
                MessageBox.TYPE_INFO, timeout=10)

    def _onClose(self):
        self.closed = True

    def loadPositions(self):
        if self.busy:
            return
        self.busy = True
        self["status"].setText(_("Downloading %s satellite list...") % self.source_name)
        deferred = threads.deferToThread(self.client.get_positions)
        deferred.addCallbacks(self._positionsLoaded, self._failed)

    def _positionsLoaded(self, positions):
        if self.closed:
            return
        self.busy = False
        self.positions = positions
        self._refreshList(0)
        self["status"].setText(
            _("%d positions found. OK: select/clear | MENU: settings") % len(positions)
        )

    def _failed(self, failure):
        if self.closed:
            return
        self.busy = False
        message = failure.getErrorMessage() if hasattr(failure, "getErrorMessage") else str(failure)
        self["status"].setText(_("Error: %s") % message)
        self.session.open(MessageBox, message, MessageBox.TYPE_ERROR, timeout=12)

    def _rowText(self, position):
        mark = "[X]" if position["key"] in self.selected else "[ ]"
        names = []
        for satellite in position.get("satellites") or []:
            name = (satellite.get("name") or "").strip()
            if name:
                names.append(name)
        suffix = " / ".join(names)
        label = position.get("rounded_pos_display") or self.client._display_position(
            position["orbital_position"])
        text = "%s  %-9s  %s" % (mark, label, suffix)
        # DreamOS Python 2's native list renderer requires UTF-8 bytes.
        if sys.version_info[0] == 2 and not isinstance(text, str):
            text = text.encode("utf-8")
        return text

    def _refreshList(self, index=None):
        if index is None:
            index = self["list"].getSelectedIndex()
        self["list"].setList([[item["key"], MultiContentEntryText(
            pos=(0, 0), size=(int(1045 * self.list_scale), int(34 * self.list_scale)),
            font=0, text=self._rowText(item))] for item in self.positions])
        if self.positions:
            self["list"].moveToIndex(min(index, len(self.positions) - 1))

    def toggleCurrent(self):
        if self.busy or not self.positions:
            return
        index = self["list"].getSelectedIndex()
        key = self.positions[index]["key"]
        if key in self.selected:
            self.selected.remove(key)
        else:
            self.selected.add(key)
        self._refreshList(index)
        self._selectionStatus()

    def selectAll(self):
        if self.busy:
            return
        self.selected = set(item["key"] for item in self.positions)
        self._refreshList()
        self._selectionStatus()

    def clearAll(self):
        if self.busy:
            return
        self.selected.clear()
        self._refreshList()
        self._selectionStatus()

    def _selectionStatus(self):
        self["status"].setText(
            _("%d / %d positions selected") % (len(self.selected), len(self.positions))
        )

    def requestBuild(self):
        if self.busy:
            return
        if not self.selected:
            self.session.open(
                MessageBox,
                _("Select at least one satellite position first."),
                MessageBox.TYPE_INFO,
                timeout=7,
            )
            return
        text = (
            _("Download %d positions and replace %s. Continue?")
            % (len(self.selected), DESTINATION)
        )
        self.session.openWithCallback(
            self._confirmedBuild, MessageBox, text, MessageBox.TYPE_YESNO
        )

    def _confirmedBuild(self, answer):
        if not answer or self.busy:
            return
        chosen = [item for item in self.positions if item["key"] in self.selected]
        self.busy = True
        self["status"].setText(
            _("Downloading transponders for %d positions...") % len(chosen)
        )
        deferred = threads.deferToThread(self._downloadAndInstall, chosen)
        deferred.addCallbacks(self._buildFinished, self._failed)

    def _downloadAndInstall(self, chosen):
        rows = []
        empty = []
        for position in chosen:
            transponders = self.client.get_transponders(position["rounded_pos"])
            if not transponders:
                empty.append(position.get("rounded_pos_display", position["display"]))
                continue
            rows.append((position, transponders))
        xml_bytes, stats = build_satellites_xml(rows)
        if not stats["transponders"]:
            raise SatBeamsError(_("No transponders found for selected satellites. Existing XML is preserved."))
        stats["empty"] = len(empty)
        backup = install_xml(xml_bytes, DESTINATION)
        return stats, backup

    def _buildFinished(self, result):
        if self.closed:
            return
        self.busy = False
        stats, backup = result
        try:
            from Components.NimManager import nimmanager

            nimmanager.readTransponders()
            reload_text = _("Tuner list reloaded.")
        except Exception:
            reload_text = _("Restart Enigma2 to apply the changes.")

        message = (
            _("Wrote %d satellite positions and %d transponders.\n%s\n%s")
            % (
                stats["satellites"],
                stats["transponders"],
                reload_text,
                (_("Backup: %s") % backup) if backup else _("No previous file existed."),
            )
        )
        self["status"].setText(message.replace("\n", " "))
        if stats.get("empty"):
            message += _("\nSkipped %d positions with no transponders.") % stats["empty"]
        self.session.open(MessageBox, message, MessageBox.TYPE_INFO, timeout=15)


class SourceSelection(Screen):
    def __init__(self, session):
        directory = os.path.dirname(__file__)
        self.skin = '''<screen position="center,center" size="1000,430" title="DreamOSatSatellites">
            <widget name="prompt" position="30,20" size="940,45" font="Regular;28" halign="center" />
            <widget name="satbeams" position="60,100" size="400,140" pixmap="%s" alphatest="blend" scale="1" />
            <widget name="kingofsat" position="540,100" size="400,140" pixmap="%s" alphatest="blend" scale="1" />
            <widget name="selection" position="30,270" size="940,55" font="Regular;28" halign="center" />
            <widget name="help" position="30,355" size="940,40" font="Regular;22" halign="center" />
        </screen>''' % (os.path.join(directory, 'satbeams-logo.svg'), os.path.join(directory, 'kingofsat-logo.png'))
        Screen.__init__(self, session)
        self.choice = 0
        self["prompt"] = Label(_("Which site would you like to use?"))
        self["satbeams"] = Pixmap()
        self["kingofsat"] = Pixmap()
        self["selection"] = Label()
        self["help"] = Label(_("Left / Right: select source | OK: continue | EXIT: close"))
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "left": self.toggle, "right": self.toggle,
            "ok": self.accept, "cancel": self.close}, -1)
        self.refresh()

    def refresh(self):
        self["selection"].setText("[ SatBeams ]                 KingOfSat" if self.choice == 0
            else "SatBeams                 [ KingOfSat ]")

    def toggle(self):
        self.choice = 1 - self.choice
        self.refresh()

    def accept(self):
        self.close("satbeams" if self.choice == 0 else "kingofsat")


def main(session, **kwargs):
    def selected(source=None):
        if source:
            session.open(SatBeamsSelection, source)
    session.openWithCallback(selected, SourceSelection)


def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description=_("Create satellites.xml from SatBeams or KingOfSat"),
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="plugin.svg",
            fnc=main,
        ),
        PluginDescriptor(
            name=PLUGIN_NAME,
            description=_("Create satellites.xml from SatBeams or KingOfSat"),
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            fnc=main,
        ),
    ]
