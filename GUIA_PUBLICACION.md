# Guía para publicar el sitio (sin usar git ni la terminal)

Repo: https://github.com/togetherviajesapp/Realstate

## Paso 1 — Subir los archivos

1. Entrá a https://github.com/togetherviajesapp/Realstate
2. Click en **"uploading an existing file"** (o el botón **Add file > Upload files** si el repo ya no está vacío)
3. Arrastrá TODOS estos archivos y carpetas a la ventana del navegador (mantené la estructura de carpetas):
   - `index.html`
   - `data.json`
   - `scraper.py`
   - `scraper_ml.py`
   - `process.py`
   - `barrios.py`
   - `requirements.txt`
   - la carpeta `.github` completa (con `.github/workflows/update.yml` adentro)
   - la carpeta `data` (si existe, puede ir vacía o con los CSV de referencia)
4. Abajo de la página escribí un mensaje como "primera versión" y click en **Commit changes**

Nota: si al arrastrar la carpeta `.github` no te deja (algunos navegadores no soportan subir carpetas ocultas por drag-and-drop), subí primero el resto de archivos, y para `.github/workflows/update.yml` usá el botón **Add file > Create new file**, escribí el nombre completo `.github/workflows/update.yml` (GitHub crea las carpetas solo) y pegá el contenido del archivo.

## Paso 2 — Activar GitHub Pages

1. En el repo, andá a **Settings** (arriba a la derecha)
2. En el menú de la izquierda, click en **Pages**
3. En "Build and deployment" > "Source", elegí **Deploy from a branch**
4. En "Branch", elegí **main** y la carpeta **/ (root)**, después **Save**
5. Esperá 1-2 minutos. GitHub te va a mostrar la URL pública, algo como:
   `https://togetherviajesapp.github.io/Realstate/`

Esa es la URL que vas a poder abrir desde cualquier dispositivo.

## Paso 3 — Instalar el runner en tu computadora (necesario para Gallito y MercadoLibre)

Gallito y MercadoLibre bloquean el tráfico que sale de las máquinas de GitHub (ver "Limitaciones conocidas" más abajo). Para evitar ese bloqueo, la tarea semanal ahora corre **desde tu propia computadora** en vez de en la nube de GitHub — usa tu conexión a internet normal, la misma con la que navegás vos. Es gratis, pero tu PC tiene que estar prendida y conectada a internet los lunes a las 10am (hora Uruguay), o vas a tener que correrla vos a mano ese día cuando puedas.

Esto requiere una instalación única (30-40 minutos la primera vez). Pasos:

**3.1 — Instalar Git para Windows (si no lo tenés)**

1. Descargá desde https://git-scm.com/download/win e instalá con las opciones por defecto (click en "Next" en todas las pantallas).
2. Esto es necesario porque la tarea automática usa comandos de Git internamente.

**3.2 — Registrar tu computadora como "runner" en GitHub**

1. En el repo, andá a **Settings > Actions > Runners**.
2. Click en **New self-hosted runner**.
3. Elegí sistema operativo **Windows** y arquitectura **x64**.
4. GitHub te va a mostrar un bloque de comandos para copiar y pegar (algo como `Invoke-WebRequest`, `Expand-Archive`, `.\config.cmd --url ... --token ...`). Abrí **PowerShell** (buscalo en el menú de inicio), creá o entrá a una carpeta donde quieras guardar el runner (por ejemplo `C:\actions-runner`) y pegá esos comandos uno por uno, en el orden que aparecen en la página de GitHub.
5. Cuando `config.cmd` te pregunte el nombre del runner y las "labels", podés dejar todo por defecto (Enter).
6. Cuando te pregunte "Run as service?" respondé que **sí** — así queda corriendo en segundo plano sin que tengas que dejar una ventana abierta.

**3.3 — Confirmar que quedó activo**

1. Volvé a **Settings > Actions > Runners** en GitHub.
2. Deberías ver tu computadora listada con un punto verde ("Idle" = esperando tareas).

Con esto ya está. Mientras tu PC esté prendida y conectada, la tarea semanal (lunes 10am) va a correr sola en segundo plano, sin que tengas que abrir nada. Si tu PC está apagada ese día, la tarea queda esperando y corre apenas la prendas y se conecte a internet (o la podés disparar vos a mano, ver abajo).

## Paso 4 — Probar la tarea manualmente

1. Andá a la pestaña **Actions** del repo.
2. Click en el workflow **"Actualizar inmuebles Montevideo"** (columna izquierda).
3. Click en **Run workflow** (botón a la derecha) > **Run workflow**.
4. Esperá unos minutos y actualizá la página — vas a ver el progreso y si terminó bien (tilde verde) o con error (cruz roja). Esta vez corre en tu computadora, así que asegurate de que esté prendida y conectada cuando la dispares.

Si sale con error, copiá el mensaje y pasámelo para que lo revise contigo.

## Qué hace cada archivo

- `index.html` — la página que ves vos, con el buscador, los filtros y la pestaña de Análisis
- `data.json` — los datos actuales (se actualiza solo cada semana)
- `scraper.py` — descarga avisos de InfoCasas (pedido normal) y Gallito (navegador simulado, porque ese portal bloquea las descargas simples)
- `scraper_ml.py` — descarga avisos de MercadoLibre (usa un navegador simulado porque ese sitio bloquea las descargas simples)
- `scraper_casasymas.py` — descarga avisos de Casasymas, filtrados a Montevideo (navegador simulado; ver "Casasymas" más abajo — es la primera versión, puede necesitar ajustes)
- `process.py` — compara lo nuevo contra lo anterior y arma `data.json` (incluye el historial de precio por aviso y el registro acumulado de bajas)
- `barrios.py` — cuando el portal informa una dirección en vez de un barrio, la reconoce y le asigna el barrio real (ver más abajo)
- `export_excel.py` — genera `Reporte_Inmuebles_Montevideo.xlsx` a partir de `data.json` en cada corrida (ver "Excel automático" más abajo)
- `.github/workflows/update.yml` — la tarea automática semanal (corre en tu computadora, ver Paso 3)

## Barrio automático a partir de direcciones

Algunos avisos traen una dirección (calle + número) en el campo de barrio en vez del nombre de la zona. Cada corrida semanal ahora:

1. Si el valor ya es un barrio conocido de Montevideo, lo deja tal cual (normalizado).
2. Si parece una dirección, la consulta contra un servicio gratuito de mapas (OpenStreetMap) y le asigna el barrio real más cercano.
3. Guarda cada dirección ya consultada en `data/geocode_cache.json`, para no volver a consultar lo mismo la semana siguiente.

Esto no se pudo probar en vivo desde donde armé el sitio (sin acceso a internet en ese entorno), así que el resultado real se va a ver recién después de la primera corrida. Si después de correr ves direcciones que no cambiaron a barrio, avisame y reviso el archivo `barrios.py`.

## Pestaña "Análisis"

Además del buscador, el sitio tiene una pestaña **Análisis** (arriba a la derecha) con:

- Posibles ventas/alquileres: avisos que dejaron de aparecer en el portal, con tipo, barrio, precio y cuánto tiempo estuvieron publicados. Se muestran siempre como "posible" venta/alquiler, nunca como confirmada — el portal también puede sacarlos por vencimiento u otro motivo.
- Gráficos de qué tipo de vivienda y qué barrios tienen más bajas (una forma indirecta de ver qué se mueve más).
- Gráfico de variación de precio: compara cuánto cambió el precio de un aviso contra cuántos días lleva publicado.

Este historial arranca a partir de la corrida donde se agregó esta función — las bajas de corridas anteriores no quedaron con ese nivel de detalle, solo como un número total.

## Por qué Gallito y MercadoLibre a veces tardan o fallan

Investigando los timeouts de la corrida del 15/7 encontré la causa: tanto Gallito como MercadoLibre son páginas cargadas de publicidad y scripts de analytics (Google ads, Google Tag Manager, cxense, etc.) además de decenas de imágenes por página. Esos scripts a veces tardan muchísimo en responder (o nunca lo hacen), y el navegador automatizado se queda esperando a que la página "termine de cargar" — no es que el sitio nos esté bloqueando activamente.

Por eso `scraper.py` y `scraper_ml.py`:

1. Bloquean imágenes, fuentes y los scripts de publicidad/analytics conocidos (no afecta los datos que leemos, que son solo texto).
2. Reintentan automáticamente si una página falla, y Gallito además le da una "segunda vuelta" al final a cualquier página que haya seguido fallando, con una pausa más larga antes de reintentar.

Con estos cambios, la corrida del 15/7 (run #12) logró **10 de 10 páginas de Gallito, 10 de 10 de InfoCasas y 6 de 6 de MercadoLibre — 100% de éxito en los tres portales**, sin necesitar la segunda vuelta.

## Reinicio del historial (15/7/2026)

Antes del 15/7, los datos de "nuevos", "bajas" y variación de precio mezclaban corridas hechas con versiones distintas del scraper (antes y después de arreglar Gallito y MercadoLibre). Comparar avisos de esas corridas por URL daba resultados sin sentido — por ejemplo, 0 de 148 avisos de MercadoLibre de la primera búsqueda coincidían con los de la corrida más reciente, no porque hayan cambiado todos, sino porque el método de descarga cambió y generó URLs distintas para el mismo aviso.

Por eso `data.json` se reinició: la corrida del 15/7 (858 avisos, 100% de éxito en los tres portales) pasó a ser el nuevo punto de partida. Todos los avisos activos quedaron marcados como "Nuevo" desde esa fecha, y el registro de bajas y variación de precio arranca de cero. A partir de acá, cada corrida semanal compara contra un dato confiable, así que los gráficos de la pestaña Análisis van a reflejar cambios reales del mercado, no ruido técnico.

## Gallito cambió de diseño (20/7/2026)

La corrida del 20/7 dio 0 avisos de Gallito en las 10 páginas (antes venía dando 100%). No fue un timeout: la página cargaba bien pero no encontraba ninguna tarjeta. Gallito rediseñó su sitio — las clases HTML que usábamos para leer los avisos (`.contenedor-info`, etc.) ya no existen, las reemplazaron por una estructura totalmente distinta.

Esto contaminó `data.json`: al no encontrar nada de Gallito, marcó como "posible baja" a los ~400 avisos de Gallito que estaban activos, aunque en realidad seguían publicados. Actualicé `scraper.py` para leer la nueva estructura del sitio y lo probé en vivo contra Gallito (venta y alquiler, varios casos: monoambientes, oficinas, barrios de una y varias palabras) — funciona correctamente. Cuando subas esta versión y corras el workflow de nuevo, Gallito debería volver a traer datos reales.

**Importante**: por esta contaminación, después de confirmar que Gallito volvió a funcionar puede convenir reiniciar `data.json` de nuevo (igual que se hizo el 15/7), para no arrastrar esas ~400 bajas falsas al historial de Análisis.

## Casasymas (nuevo portal, primera versión)

Pediste agregar también Veocasas, Mirando y Casasymas. Investigué los tres y ninguno se puede descargar de forma simple como InfoCasas:

- **Veocasas**: la paginación se maneja 100% por JavaScript interno, sin ningún rastro en la URL — hay que simular clicks reales, y es más frágil que los portales actuales porque ni siquiera hay una URL por página como referencia.
- **Mirando**: no es un catálogo navegable — es un buscador con IA orientado a cuentas de usuario (alertas, favoritos). Puede que no tenga una vista pública para scrapear.
- **Casasymas**: tiene un endpoint de datos interno, pero llamarlo directo (sin pasar por la página real) hace que el servidor deje el pedido colgado indefinidamente — una protección antibot. Sí funciona si se simulan los clicks reales de un usuario (elegir "Montevideo" en el filtro, clickear "Buscar"), así que `scraper_casasymas.py` hace eso con un navegador simulado, igual que Gallito.

Empecé por Casasymas porque era el más viable. Es la **primera versión**: el sitio no usa nombres de clase descriptivos en sus tarjetas de avisos, así que identificar precio/tipo/zona de cada aviso se basa en el orden y el contenido del texto visible, no en algo tan estable como en otros portales. Puede necesitar ajustes después de ver los resultados de la primera corrida real (igual que pasó con Gallito al principio) — así que prestale especial atención al log de esa corrida.

Veocasas y Mirando quedan pendientes para una próxima sesión.

## Excel automático

Cada corrida semanal ahora genera también `Reporte_Inmuebles_Montevideo.xlsx` (en la raíz del repo), a partir de los mismos datos que muestra el sitio web. Tiene las hojas: Listado actual, Posibles bajas, Historico semanal y Resumen y Gráfica (con las mismas fórmulas y gráficos de evolución que tenía el Excel original). Se commitea junto con `data.json` en cada corrida, así que después de cada lunes vas a tener la versión más reciente para descargar desde GitHub.

## Limitaciones conocidas

- **Gallito bloqueaba los pedidos normales (error 403), incluso desde tu propia conexión** — no era solo un tema de IP de GitHub, sino que el sitio detecta pedidos que no vienen de un navegador real. Por eso Gallito se descarga con un navegador simulado (igual que MercadoLibre).
- MercadoLibre: cobertura parcial (3 páginas por operación). El scraper busca de forma más amplia el link real de cada aviso; cuando ese portal no lo expone en la tarjeta, el sitio muestra "Sin link" en vez de un link genérico equivocado.
- Como solo se scrapean las primeras páginas de cada portal (5 para InfoCasas/Gallito, 3 para MercadoLibre), un aviso puede "desaparecer" de la corrida simplemente porque quedó más atrás en el orden del portal (por avisos nuevos empujándolo), no porque se haya vendido/alquilado o dado de baja. Por eso la pestaña Análisis siempre lo muestra como "posible" venta/alquiler, nunca como confirmado.
- **Tu computadora tiene que estar prendida y conectada** los lunes a las 10am para que la tarea corra sola. Si está apagada, la tarea queda pendiente hasta que la prendas (o la corrés vos a mano desde Actions).
