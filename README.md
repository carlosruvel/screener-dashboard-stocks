# Screener Dashboard — configuración

Dashboard que se actualiza solo todos los días (lunes a viernes, 7:00am
hora Jalisco/CDMX) y vive en una URL fija que puedes abrir desde tu
compu o tu iPad sin correr nada.

## Pasos de instalación (una sola vez)

1. **Crea un repositorio nuevo** en GitHub (puede ser público o privado):
   `github.com/nuevo → New repository` → nómbralo, por ejemplo,
   `screener-dashboard` → Create repository.

2. **Sube estos 5 archivos** a la raíz del repo, manteniendo la carpeta
   `.github/workflows/` tal cual (arrástralos en la página web de GitHub,
   sección "Add file → Upload files", o usa `git push` si prefieres
   terminal):
   - `screener.py`
   - `requirements.txt`
   - `index.html`
   - `data.json`
   - `.github/workflows/update.yml`

3. **Activa GitHub Pages con "GitHub Actions" como origen:**
   Settings del repo → Pages (menú izquierdo) → en "Build and
   deployment / Source" selecciona **GitHub Actions** (no "Deploy from
   branch").

4. **Corre el workflow por primera vez a mano** (no esperes al cron):
   pestaña **Actions** del repo → click en "Actualizar screener diario"
   en la lista de la izquierda → botón **Run workflow** → Run workflow.
   Tarda 1-3 minutos.

5. Cuando termine (ícono verde ✓), ve otra vez a **Settings → Pages**:
   ahí aparece la URL pública, algo como
   `https://tu-usuario.github.io/screener-dashboard/`

6. **Guárdala en tu iPad como app:** abre esa URL en Safari →
   botón compartir (el cuadro con la flecha) → **Agregar a pantalla de
   inicio**. Queda como ícono normal, y cada vez que la abras va a
   mostrar los datos más recientes generados esa mañana.

## Después de esto

No necesitas volver a tocar nada. Cada día laboral a las 7am (hora de
Jalisco), GitHub corre `screener.py` solo, actualiza `data.json`, y el
dashboard en la URL pública se refresca automáticamente.

Si algún día quieres correrlo fuera de horario (por ejemplo, antes de
grabar contenido), repite el paso 4 ("Run workflow") y espera 1-3
minutos.

## Personalización

Para cambiar tickers, umbrales, o el horario del cron, edita
`screener.py` (mismas variables `TICKERS_UNIVERSE` y `THRESHOLDS` de
siempre) o la línea `cron:` dentro de
`.github/workflows/update.yml` — recuerda que el horario del cron
siempre se escribe en **UTC**, no en hora de México.

## Nota sobre privacidad

Si tu repositorio es **público**, la URL del dashboard y el contenido
de `data.json` son visibles para cualquiera que tenga el link. Si
prefieres que sea privado, crea el repo como **Private**: GitHub Pages
funciona igual, pero necesitas estar loggeado en GitHub (o usar GitHub
Pages con acceso restringido, disponible en cuentas de pago) para
verlo. Para uso personal/educativo esto normalmente no es un problema,
pero vale la pena decidirlo antes de subir el repo.
