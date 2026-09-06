# -*- coding: utf-8 -*-
from __future__ import absolute_import
import gettext
import os
import sys

PluginLanguageDomain = 'DreamOSatSatellites'
PluginLanguagePath = os.path.join(os.path.dirname(__file__), 'locale')
_translation = gettext.NullTranslations()


def locale_init():
    global _translation
    try:
        from Components.Language import language
        selected = language.getLanguage()
    except ImportError:
        selected = os.environ.get('LANGUAGE', 'en')
    gettext.bindtextdomain(PluginLanguageDomain, PluginLanguagePath)
    _translation = gettext.translation(PluginLanguageDomain, PluginLanguagePath,
        languages=[selected], fallback=True)


def _(text):
    if sys.version_info[0] == 2:
        if isinstance(text, str):
            text = text.decode('utf-8')
        return _translation.ugettext(text).encode('utf-8')
    return _translation.gettext(text)


locale_init()
try:
    from Components.Language import language
    language.addCallback(locale_init)
except ImportError:
    pass

