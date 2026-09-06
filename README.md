# DreamOSatSatellites

Enigma2 için SatBeams / KingOfSat kaynaklarından satellites.xml oluşturucu.
By audi06_19 — info@dreamosat-forum.com

## Kurulum

`src/DreamOSatSatellites` klasörünü `/usr/lib/enigma2/python/Plugins/Extensions/` içine kopyalayın ve Enigma2 arayüzünü yeniden başlatın. Eski `SatBeamsSatellites` klasörünü Extensions dışına yedekleyin; iki kopyayı birlikte çalıştırmayın.

## Kullanım

- Açılışta logolu kaynak seçimi.
- OK: seç/kaldır; yeşil: tümünü seç; sarı: tümünü kaldır; mavi: XML oluştur.
- MENU: kaynak bazında beş profil, bölgesel seçim, HD/FHD/4K ve Hakkında.
- Mevcut `/etc/tuxbox/satellites.xml` zaman damgasıyla yedeklenir.
- SatBeams sorgusu `rounded_pos`, XML konumu `real_pos` kullanır.
- KingOfSat nominal konum kullanır; açıkça boş sonuç dönen konumlar atlanır.

OpenATV ve Dreambox Two Gemini 4.2 üzerinde geliştirilmiştir. Python 2.7 ve Python 3 uyumluluğu hedeflenir. Bölgesel seçimler yörünge aralıklarına dayanır.

## Lisans ve iletişim

GPL-2.0-or-later. Tam metin: [LICENSE](LICENSE); kapsam: [LICENSING.md](LICENSING.md).
Logolar ve üçüncü taraf verileri ilgili sahiplerinin koşullarına tabidir.

- Destek: https://www.dreamosat-forum.com
- GitHub: https://github.com/audi06/DreamOSatSatellites
- Kaynaklar: https://satbeams.com ve https://kingofsat.net
