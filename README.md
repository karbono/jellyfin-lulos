# jellyfin-lulos

Compilación automática en GitHub Actions de [Jellyfin Android](https://github.com/jellyfin/jellyfin-android) (variante `proprietary` con Chromecast) preconfigurada con `https://tv.karbono.es:8920`.

Al abrir la app por primera vez, conecta directamente al servidor y solo pide usuario y contraseña.

## Descarga

- Página web: `https://dl.karbono.es/jellyfin`
- Enlace directo APK: `https://dl.karbono.es/jellyfin/apk`

## Parche AV1 (app de TV)

`scripts/patch_tv_av1_hw.py` hace que la app de TV solo cuente los decodificadores AV1 por hardware. Sin él, la app da AV1 por soportado aunque la tele solo tenga un decodificador por software, pide la peli sin transcodificar y la reproducción se corta a los pocos segundos en vez de que el servidor la transcodifique. El resto de códecs no cambia.
