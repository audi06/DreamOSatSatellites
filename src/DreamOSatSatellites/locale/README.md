# Çeviri dosyaları

Enigma2'nin seçili dili kullanılır. `tr.po` Türkçe, `en.po` İngilizce çeviridir.
Yeni dil için `DreamOSatSatellites.pot` dosyasını dil koduyla `.po` olarak kopyalayın.
İngilizce `msgid` değerlerini koruyun; yalnızca `msgstr` değerlerini çevirin.
`%s`, `%d` yer tutucularını ve sıralarını koruyun.

Depo kökünden: `python3 tools/compile_translations.py`

Alternatif: `msgfmt --check -o tr/LC_MESSAGES/DreamOSatSatellites.mo tr.po`

Cihaza hem `.po` hem dil/LC_MESSAGES altındaki `.mo` dosyalarını kopyalayın.
Dil değişiminden sonra açık eklenti ekranını kapatıp yeniden açın.
