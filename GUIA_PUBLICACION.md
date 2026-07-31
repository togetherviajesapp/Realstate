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

## URL definitiva: Vercel (20/7/2026)

El link de GitHub Pages incluía "togetherviajesapp" (el nombre de otro proyecto tuyo), así que se agregó una segunda publicación en Vercel, apuntando al mismo repositorio, con un nombre propio:

**`https://inmueblesuy.vercel.app/`** — este es el link que hay que compartir y usar de acá en más.

Es un proyecto de Vercel completamente aparte del de Together (mismo repo de GitHub, pero un proyecto distinto en Vercel) — no toca ni la cuenta de GitHub ni nada de ese otro proyecto. Se actualiza solo cada vez que la tarea semanal (o cualquier otro cambio) se sube al repositorio, igual que GitHub Pages, que se puede seguir usando o dejar de compartir, como prefieras — ambos quedan funcionando en paralelo con los mismos datos.

## Paso 3 — Instalar el runner en tu computadora (necesario para Gallito y MercadoLibre)

Gallito y MercadoLibre bloquean el tráfico que sale de las máquinas de GitHub (ver "Limitaciones conocidas" más abajo). Para evitar ese bloqueo, la tarea semanal ahora corre **desde tu propia computadora** en vez de en la nube de GitHub — usa tu conexión a internet normal, la misma con la que navegás vos. Es gratis, pero tu PC tiene que estar prendida y conectada a internet los lunes, miércoles y viernes a las 10am (hora Uruguay), o vas a tener que correrla vos a mano ese día cuando puedas.

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

Con esto ya está. Mientras tu PC esté prendida y conectada, la tarea (lunes, miércoles y viernes 10am) va a correr sola en segundo plano, sin que tengas que abrir nada. Si tu PC está apagada ese día, la tarea queda esperando y corre apenas la prendas y se conecte a internet (o la podés disparar vos a mano, ver abajo).

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
- `scraper_veocasas.py` — descarga avisos de Veocasas, filtrados a Montevideo (navegador simulado; ver "Veocasas" más abajo)
- `usuarios.json` — lista de usuarios habilitados para entrar al sitio (ver "Acceso con usuario y contraseña" más abajo)
- `generar-clave.html` — página para generar la línea que se pega en `usuarios.json` al agregar o cambiar un usuario
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

## Segundo reinicio del historial (20/7/2026)

Después de arreglar Gallito, MercadoLibre y la paginación de Casasymas (ver secciones siguientes), volví a reiniciar `data.json` por el mismo motivo que el 15/7: dos regresiones seguidas (Gallito en 0% y después MercadoLibre en 0%) habían marcado como "posible baja" a cientos de avisos que en realidad seguían publicados, contaminando el historial de Análisis.

Usé la corrida #17 (20/7, con los cuatro portales funcionando: InfoCasas, Gallito, MercadoLibre y Casasymas) como nuevo punto de partida: **1.251 avisos activos**, todos marcados "Nuevo" desde hoy, sin bajas ni variación de precio en el historial. A partir de esta corrida, los gráficos de Análisis vuelven a reflejar cambios reales del mercado.

## Gallito cambió de diseño (20/7/2026)

La corrida del 20/7 dio 0 avisos de Gallito en las 10 páginas (antes venía dando 100%). No fue un timeout: la página cargaba bien pero no encontraba ninguna tarjeta. Gallito rediseñó su sitio — las clases HTML que usábamos para leer los avisos (`.contenedor-info`, etc.) ya no existen, las reemplazaron por una estructura totalmente distinta.

Esto contaminó `data.json`: al no encontrar nada de Gallito, marcó como "posible baja" a los ~400 avisos de Gallito que estaban activos, aunque en realidad seguían publicados. Actualicé `scraper.py` para leer la nueva estructura del sitio y lo probé en vivo contra Gallito (venta y alquiler, varios casos: monoambientes, oficinas, barrios de una y varias palabras) — funciona correctamente. Cuando subas esta versión y corras el workflow de nuevo, Gallito debería volver a traer datos reales.

**Importante**: por esta contaminación, después de confirmar que Gallito volvió a funcionar puede convenir reiniciar `data.json` de nuevo (igual que se hizo el 15/7), para no arrastrar esas ~400 bajas falsas al historial de Análisis.

## MercadoLibre pidió verificar cuenta (20/7/2026)

Después de arreglar Gallito, la misma corrida mostró MercadoLibre en 0%: en vez de tardar o no encontrar avisos, redirigía a una página de "verificación de cuenta" pidiendo iniciar sesión. Comprobé navegando manualmente (con tu Chrome, sin automatizar nada) que el sitio carga perfecto y no pide login — el bloqueo es específicamente contra la sesión automatizada, no un requisito general del sitio ni un bloqueo de tu IP.

Le agregué varias capas de disimulo a `scraper_ml.py` para intentar evitarlo:

- Un "disfraz" más completo del navegador automatizado (antes solo tapaba 2-3 señales obvias, ahora también WebGL, memoria, plugins, permisos, etc.).
- Intenta usar Chrome real en vez del Chromium que trae Playwright (más parecido a un navegador de verdad). Si Chrome no está instalado en tu PC, cae de nuevo a Chromium sin romperse.
- "Entrada en calor": ahora visita la portada de MercadoLibre antes de ir directo al listado, como haría una persona.
- Movimientos de mouse y scroll simulados, y pausas variables en vez de siempre la misma cantidad de segundos.

Agregué `python -m playwright install chrome` al workflow para que el runner tenga Chrome real disponible.

**Resultado (corrida #15, 20/7/2026): funcionó.** MercadoLibre volvió a traer datos — 288 avisos (48/48 en las 6 páginas), sin ningún muro de verificación. Junto con InfoCasas y Gallito, también al 100%, los tres portales originales quedaron sanos otra vez.

Por la contaminación de las dos regresiones seguidas (Gallito y luego MercadoLibre marcando cientos de avisos activos como "posible baja" por error), corresponde reiniciar `data.json` ahora que los tres portales están confirmados funcionando, para no arrastrar esas bajas falsas al historial de Análisis.

## Casasymas (nuevo portal, primera versión)

Pediste agregar también Veocasas, Mirando y Casasymas. Investigué los tres y ninguno se puede descargar de forma simple como InfoCasas:

- **Veocasas**: la paginación se maneja 100% por JavaScript interno, sin ningún rastro en la URL — hay que simular clicks reales, y es más frágil que los portales actuales porque ni siquiera hay una URL por página como referencia.
- **Mirando**: no es un catálogo navegable — es un buscador con IA orientado a cuentas de usuario (alertas, favoritos). Puede que no tenga una vista pública para scrapear.
- **Casasymas**: tiene un endpoint de datos interno, pero llamarlo directo (sin pasar por la página real) hace que el servidor deje el pedido colgado indefinidamente — una protección antibot. Sí funciona si se simulan los clicks reales de un usuario (elegir "Montevideo" en el filtro, clickear "Buscar"), así que `scraper_casasymas.py` hace eso con un navegador simulado, igual que Gallito.

Empecé por Casasymas porque era el más viable. Es la **primera versión**: el sitio no usa nombres de clase descriptivos en sus tarjetas de avisos, así que identificar precio/tipo/zona de cada aviso se basa en el orden y el contenido del texto visible, no en algo tan estable como en otros portales.

**Arreglo de paginación (20/7/2026):** la primera versión simulaba clicks en "página siguiente", y eso fallaba de forma intermitente (algunas páginas devolvían 0 avisos sin motivo aparente). Investigando en vivo encontré que el sitio en realidad tiene una URL real por página (por ejemplo `casasymas.com.uy/propiedades/venta/montevideo/pagina-3`), aunque no era evidente navegando con clicks. Reescribí el scraper para ir directo a esa URL en cada página — igual que InfoCasas y Gallito — en vez de simular clicks de paginación. Es más simple y no debería tener más huecos.

Mirando queda pendiente (no es un catálogo navegable). **Veocasas se agregó el 20/7** — ver sección siguiente.

## Veocasas (nuevo portal, 20/7/2026)

En la sesión anterior había quedado descartado por parecer una SPA sin ninguna URL de referencia para paginar. Investigando de nuevo encontré dos cosas:

1. El dominio real es `veocasas.com` (sin ".uy") — `veocasas.com.uy` solo redirige, y mi navegador lo bloqueaba por una protección de seguridad que detectaba un token de sesión en esa página (no era un problema del sitio, era mi propia herramienta).
2. Al revisar el sitio real con tu ayuda, confirmamos que **sí tiene paginación por URL**: `veocasas.com/properties?location=1&recenter=1&page=N` (venta) y lo mismo con `&operation=RENT` para alquiler. El parámetro `location=1` ya filtra a Montevideo.

Con eso, `scraper_veocasas.py` navega directo a cada página igual que los demás portales. El sitio no muestra el barrio como campo separado, así que se intenta reconocer el nombre de un barrio oficial de Montevideo dentro del título del aviso (si no aparece ninguno, se deja vacío en vez de adivinar).

## Excel automático

Cada corrida semanal ahora genera también `Reporte_Inmuebles_Montevideo.xlsx` (en la raíz del repo), a partir de los mismos datos que muestra el sitio web. Tiene las hojas: Listado actual, Posibles bajas, Historico semanal y Resumen y Gráfica (con las mismas fórmulas y gráficos de evolución que tenía el Excel original). Se commitea junto con `data.json` en cada corrida, así que después de cada lunes vas a tener la versión más reciente para descargar desde GitHub.

## Acceso con usuario y contraseña (20/7/2026)

El sitio ahora pide usuario y contraseña antes de mostrar nada. Usuarios iniciales: `gramirez` y `vferreira`.

**Importante sobre qué tipo de protección es esta.** GitHub Pages (donde vive el sitio) es 100% gratis pero no tiene forma de pedir login de verdad — es solo HTML/JS que corre en tu navegador, sin ningún servidor propio atrás. Evaluamos las alternativas con protección real (Cloudflare Access, un dominio propio) pero requerían comprar un dominio (~10-15 USD/año), así que optamos por esta versión casera:

- Las contraseñas se guardan como un código (hash SHA-256), no en texto plano — alguien que abra el código de la página no ve la contraseña directamente escrita.
- Pero **no es seguridad real**: alguien con conocimientos técnicos podría revertir ese código. Sirve para que no entre cualquiera que llegue al link por casualidad (por ejemplo, si se indexa en un buscador o se comparte sin querer), no para proteger información sensible de un atacante decidido.
- Una vez que alguien pone bien el usuario y contraseña en un dispositivo, queda recordado ahí (no hay que volver a escribirlo cada vez que entra desde ese mismo celular o PC). Hay un link "Cerrar sesión" arriba a la derecha por si querés que vuelva a pedir el login en ese dispositivo.

**Para agregar una persona nueva o cambiar una contraseña:**
1. Abrí `generar-clave.html` (`https://togetherviajesapp.github.io/Realstate/generar-clave.html`).
2. Escribí el usuario y la contraseña (dos veces, para confirmar) y tocá "Generar línea".
3. Copiá la línea que aparece.
4. Andá al archivo `usuarios.json` en GitHub, tocá el lápiz para editarlo.
   - Si es alguien **nuevo**: pegá la línea antes del `]` final, con una coma después de la línea anterior.
   - Si es un **cambio de contraseña** de alguien que ya existe: reemplazá su línea entera por la nueva.
5. Guardá los cambios ("Commit changes"). Ya puede entrar con la nueva clave.

No hay una forma de que cada persona cambie su propia contraseña desde el sitio (necesitaría un servidor, que es justo lo que estamos evitando por el costo) — los cambios de contraseña se hacen siempre así, editando `usuarios.json`.

## Registro de uso: ingresos y búsquedas (21/7/2026)

El sitio puede registrar, en una Google Sheet propia tuya, cada vez que alguien entra y qué filtros/búsquedas usa (operación, portal, barrio, precio, texto buscado, etc.), con usuario y fecha/hora. Por defecto está **apagado** (no manda nada) hasta que lo actives con los pasos de abajo. Es gratis, sin tarjeta.

Cómo funciona: en `index.html` hay una constante `TRACK_URL` vacía. Mientras esté vacía, el sitio funciona igual que antes y no registra nada. Al completarla con la URL de tu Google Apps Script, cada login y cada cambio de filtro (con una pequeña demora de 2 segundos para no mandar un evento por cada letra tipeada) se manda a esa URL.

**Pasos para activarlo:**
1. Andá a [sheets.google.com](https://sheets.google.com) y creá una planilla nueva, por ejemplo "Registro de uso — Inmuebles Montevideo".
2. En el menú de la planilla: **Extensiones > Apps Script**.
3. Borrá el código de ejemplo que aparece y pegá el contenido del archivo `Code.gs` (está en la raíz del repo, junto a `index.html`).
4. Guardá (ícono de disco o Ctrl+S). Si pide un nombre para el proyecto, poné cualquiera.
5. Arriba a la derecha: **Implementar > Nueva implementación**.
   - Tipo: **Aplicación web**.
   - Ejecutar como: **Yo** (tu cuenta de Google).
   - Quién tiene acceso: **Cualquier usuario** (necesario para que el sitio pueda mandar los datos sin loguearse con Google).
6. Tocá **Implementar**. La primera vez te va a pedir autorizar permisos — es tu propio script accediendo a tu propia planilla, aceptá.
7. Copiá la URL que termina en `/exec`.
8. Abrí `index.html`, buscá la línea `const TRACK_URL = '';` y pegá la URL entre las comillas.
9. Subí el `index.html` actualizado a GitHub (como siempre, reemplazando el archivo).

Una vez activo, cada fila en la hoja "Registros" de tu planilla tiene: fecha/hora, usuario, tipo de evento (`ingreso` o `busqueda`) y el detalle (qué filtros tenía puestos, o si el ingreso fue con usuario/contraseña o porque ya tenía la sesión guardada en ese dispositivo).

**Limitaciones de este enfoque:**
- Si más adelante cambiás la URL del Apps Script (por ejemplo, creás una implementación nueva), hay que actualizar `TRACK_URL` en `index.html` con la URL nueva.
- Como el sitio manda estos datos con `fetch(..., {mode:'no-cors'})`, no hay forma de confirmar desde el navegador si Google efectivamente guardó la fila (por diseño no se puede leer la respuesta) — si algo falla, revisá directamente la planilla.
- Esto registra uso del sitio, no información personal más allá del usuario que ya usan para entrar.

## MercadoLibre: el muro anti-bot volvió (22-23/7/2026)

Después de arreglarlo el 20/7, el muro de "verificación de cuenta" volvió a aparecer en dos corridas seguidas (22/7 y 23/7), trayendo 0 avisos ambas veces. Como esto pasó *antes* de que existiera la salvaguarda de `process.py` (ver más abajo), esos 0 avisos alcanzaron a borrar los 288 avisos de MercadoLibre que estaban activos — tuve que reconstruir `data.json` a mano restaurando esos avisos desde la última corrida buena y limpiando las "bajas falsas" que había dejado el bloqueo.

Dos arreglos separados, en capas distintas:

**1. Salvaguarda en `process.py` (ya activa desde el 22/7):** si un portal que tenía avisos activos trae 0 en una corrida, `process.py` ahora asume que el scraper fue bloqueado y mantiene los avisos anteriores de ese portal sin cambios, en vez de marcarlos como baja. Esto evita que un bloqueo futuro vuelva a borrar datos, pero **no evita el bloqueo en sí** — es una red de seguridad, no una solución.

**2. Mejoras al scraper de MercadoLibre (`scraper_ml.py`) para reducir el bloqueo:**
- **Sesión persistente entre corridas:** antes, cada corrida arrancaba con cookies nuevas (una sesión "recién nacida" cada vez, algo que un sistema anti-bot serio nota). Ahora el scraper guarda las cookies al terminar en `~/.ml_scraper_state.json` (en la carpeta del usuario de Windows, fuera de la carpeta del repo, para que sobreviva al "clean" que hace GitHub Actions en cada corrida) y las reusa en la próxima corrida. Con el tiempo, la sesión va a "envejecer" y parecer más creíble.
- **User-Agent coherente:** antes se forzaba siempre un User-Agent fijo ("Chrome/124"), incluso cuando el scraper usaba el Chrome real instalado en tu PC (que puede ser una versión más nueva). Esa inconsistencia entre "qué dice ser" y "qué es realmente" es día una señal clásica de bot. Ahora, si se usa el Chrome real, se deja su User-Agent auténtico sin tocar.
- **Navegación más humana:** en vez de ir de la home directo a la URL del listado, ahora simula escribir "inmuebles montevideo" en el buscador de la home y confirmar con Enter, con tipeo y pausas variables. Las esperas entre páginas también se alargaron (antes 2.5-5.5s, ahora 3-7s).

**Importante — esto no garantiza que el muro no vuelva a aparecer.** MercadoLibre puede seguir ajustando su detección en cualquier momento; estas medidas apuntan a hacer la sesión automatizada más parecida a una real, pero no hay forma de asegurar que nunca más bloquee. Si vuelve a pasar, ahora al menos la salvaguarda de `process.py` evita que se pierdan datos, y conviene revisar el log de la corrida (paso "Descargar MercadoLibre" en Actions) para confirmar si es el mismo muro u otra cosa.

## MercadoLibre: nuevo bloqueo distinto y cambio de estrategia (23/7/2026)

La corrida #25 (con las mejoras de sesión/User-Agent/navegación humana de más arriba, ya subidas y activas) volvió a traer 0 avisos de MercadoLibre. Pero esta vez el log mostró algo distinto al "muro de verificación de cuenta" de antes: una página de error genérica de MercadoLibre ("Hubo un error accediendo a esta página...") que apareció ya desde la primera visita a la home, antes de siquiera poder buscar nada. Eso apunta a un bloqueo por IP o por un sistema anti-bot (WAF) que corta el acceso antes de que la sesión o el User-Agent importen — por eso las mejoras de la sección anterior no alcanzaron esta vez.

Se evaluaron opciones pagas (proxy residencial) y gratis para evitar este bloqueo:
- **Proxy residencial (pago):** funcionaría (~$1-3/GB, costo estimado de centavos por mes dado el bajo volumen de datos), pero se descartó por ahora a pedido del usuario, que prefiere opciones sin costo.
- **API pública oficial de MercadoLibre (gratis, descartada):** se probó `api.mercadolibre.com/sites/MLU/search` y `/categories` directamente — ambos devuelven `403 Forbidden` ("forbidden" / "PA_UNAUTHORIZED_RESULT_FROM_POLICIES"). MercadoLibre cerró el acceso público a esos endpoints; ya no alcanza con no tener token, hace falta ser cuenta partner autorizada. No es una vía viable.
- **Espaciar las corridas (evaluada y descartada por ahora):** se había armado una versión del workflow que solo intentaba MercadoLibre los lunes, pero se descartó porque el runner actual usa una IP fija de una red de trabajo, así que la IP no cambia entre corridas de todos modos — espaciar no aportaría gran cosa mientras la IP siga siendo la misma. El workflow se mantiene corriendo MercadoLibre en las 3 corridas semanales (lunes, miércoles y viernes) como antes.
- **Migrar el runner a la PC personal del usuario, con IP de hogar (en curso):** la idea es que, al ser una IP residencial que puede rotar con el tiempo (a confirmar en la práctica cada cuánto lo hace), cada bloqueo no se acumule para siempre sobre la misma IP. Esto no ataca la detección por patrón de acceso automatizado en sí, pero podría reducir la frecuencia de bloqueos combinado con las mejoras de sesión/User-Agent/navegación humana ya activas en `scraper_ml.py`. Pendiente: documentar y ejecutar el procedimiento de migración del runner.

**Nada de esto garantiza que el bloqueo no vuelva a aparecer** — son medidas para reducir su frecuencia, no una solución definitiva. Mientras tanto, la salvaguarda de `process.py` sigue protegiendo los datos: si MercadoLibre trae 0 avisos en una corrida, se mantienen los últimos avisos buenos en vez de marcarlos como baja.

## Migrar el runner a tu PC personal (procedimiento)

Idea: dejar de correr la tarea desde la PC de trabajo (IP fija) y pasarla a tu PC personal en casa (IP residencial). El plan es **registrar primero el runner nuevo sin dar de baja el viejo**, probarlo, y recién ahí desactivar el de trabajo — así en ningún momento te quedás sin la tarea funcionando si algo sale mal en el medio.

**Paso A — Preparar la PC personal**

1. Instalá **Python** (versión 3.10 o superior): https://www.python.org/downloads/ — durante la instalación, marcá la casilla **"Add python.exe to PATH"** antes de darle a Install (es fácil pasarla por alto y sin eso falla todo lo demás).
2. Instalá **Git para Windows**: https://git-scm.com/download/win, con las opciones por defecto.
3. Abrí PowerShell y confirmá que ambos quedaron instalados corriendo:
   ```
   python --version
   git --version
   ```
   Si alguno da error de "no se reconoce como comando", cerrá y volvé a abrir PowerShell (a veces el PATH no se actualiza hasta reiniciar la consola); si sigue sin andar, revisá el paso de instalación.

**Paso B — Registrar la PC personal como runner nuevo**

Repetí exactamente los pasos **3.2 y 3.3** de más arriba ("Paso 3 — Instalar el runner en tu computadora"), pero ahora parado en tu PC de casa:
1. **Settings > Actions > Runners > New self-hosted runner** en el repo.
2. Elegí Windows x64 y copiá/pegá los comandos que te da GitHub en PowerShell, en una carpeta como `C:\actions-runner`.
3. Cuando pregunte "Run as service?", respondé **sí**.
4. Confirmá en **Settings > Actions > Runners** que ahora aparecen **2 runners** activos (el de trabajo y el de casa), ambos "Idle".

Nota: en este punto tenés 2 runners registrados al mismo tiempo — no pasa nada, GitHub simplemente le manda cada corrida a "un" runner disponible (no se duplica el trabajo), así que hasta que no borres el viejo, cualquiera de las dos PCs podría terminar ejecutando la tarea.

**Paso C — Probar que la PC de casa efectivamente corre la tarea**

1. Apagá momentáneamente el runner de la PC de trabajo (para forzar que la tarea caiga sí o sí en la de casa): en esa PC, abrí PowerShell como Administrador, andá a la carpeta del runner (ej. `C:\actions-runner`) y corré:
   ```
   .\svc.ps1 stop
   ```
2. Desde **Actions > Actualizar inmuebles Montevideo > Run workflow**, disparala a mano.
3. Andá a **Settings > Actions > Runners** y fijate cuál de los dos runners pasó a estado "Active" (ese es el que está ejecutando la corrida ahora) — debería ser el de casa.
4. Esperá a que termine y confirmá tilde verde, igual que en el "Paso 4" de más arriba.

**Paso D — Dar de baja el runner de trabajo**

Una vez confirmado que la PC de casa corrió la tarea con éxito:
1. En la PC de trabajo, en la carpeta del runner (`C:\actions-runner` o donde lo hayas instalado), corré en PowerShell como Administrador:
   ```
   .\config.cmd remove --token TOKEN
   ```
   (El `TOKEN` te lo da GitHub en **Settings > Actions > Runners**, click en el runner de trabajo > el botón de opciones te muestra el comando de remove con el token ya completado — copialo de ahí en vez de escribirlo a mano.)
2. Confirmá en **Settings > Actions > Runners** que ya solo aparece el runner de casa.
3. De ahí en más, la PC de trabajo puede quedar apagada sin afectar la tarea — la que tiene que estar prendida y conectada los lunes, miércoles y viernes a las 10am es la de casa.

**Qué NO hace falta migrar a mano**

- El código del repo: `actions/checkout` lo clona solo en cada corrida, en la PC que sea.
- Las credenciales de Git para el commit automático: las inyecta el propio workflow en cada corrida (via el token de GitHub Actions), no dependen de la PC.
- La sesión guardada de MercadoLibre (`~/.ml_scraper_state.json`): no se puede copiar de una PC a otra directamente porque vive en la carpeta de usuario de Windows de cada máquina. En la PC de casa va a arrancar "desde cero" la primera vez (el scraper lo maneja sin problema, ver log "no hay sesion guardada todavia") y de ahí en adelante se va a ir armando su propia sesión persistente en esa máquina.

## Limitaciones conocidas

- **Gallito bloqueaba los pedidos normales (error 403), incluso desde tu propia conexión** — no era solo un tema de IP de GitHub, sino que el sitio detecta pedidos que no vienen de un navegador real. Por eso Gallito se descarga con un navegador simulado (igual que MercadoLibre).
- MercadoLibre: cobertura parcial (3 páginas por operación). El scraper busca de forma más amplia el link real de cada aviso; cuando ese portal no lo expone en la tarjeta, el sitio muestra "Sin link" en vez de un link genérico equivocado.
- Como solo se scrapean las primeras páginas de cada portal (5 para InfoCasas/Gallito/Casasymas/Veocasas, 3 para MercadoLibre), un aviso puede "desaparecer" de la corrida simplemente porque quedó más atrás en el orden del portal (por avisos nuevos empujándolo), no porque se haya vendido/alquilado o dado de baja. Por eso la pestaña Análisis siempre lo muestra como "posible" venta/alquiler, nunca como confirmado.
- **Tu computadora tiene que estar prendida y conectada** los lunes, miércoles y viernes a las 10am para que la tarea de actualización corra sola (esto es solo para traer datos nuevos — para ver el sitio no hace falta, ver más abajo). Si está apagada, la tarea queda pendiente hasta que la prendas (o la corrés vos a mano desde Actions).
