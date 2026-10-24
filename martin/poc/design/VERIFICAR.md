# Verificar la interfaz con capturas y pruebas reales

`scripts/captura.py` abre la interfaz en un Chrome headless propio, ejecuta los pasos que le pidas y devuelve un informe JSON, así que cada agente comprueba su sección con capturas e interacciones reales, sin chocar con los demás y sin tocar el navegador del usuario.

## Qué hace

El script arranca el servidor de la demo (`python -m uvicorn app.main:app`) en un puerto libre con su propio JSON de datos (`HOTEL_DB`), siembra los datos con `--semilla` (por defecto `completa`, con el reloj de la demo en 2026-10-24T09:00) y lanza Chrome con un perfil vacío. Después abre la ruta, espera a la carga y a que la red se calme, ejecuta los pasos y hace las capturas, y una ejecución sencilla tarda 3 o 4 s.

Al terminar mata a Chrome y a uvicorn, borra sus carpetas temporales e imprime un único JSON por stdout, también cuando algo falla o se agota `--timeout` (90 s por defecto). Cada ejecución elige sus propios puertos y carpetas, así que puedes lanzar varias a la vez.

## Ocho ejemplos

Lánzalos desde `martin/poc`, en PowerShell o en Git Bash. El script expande `%TEMP%` y `~` dentro de las rutas, así que las capturas caen fuera del repositorio, y las ves abriendo con Read las rutas que devuelve `capturas`. Los ejemplos con `legacy` funcionan hoy porque esa interfaz ya existe, y para tu sección cambias la ruta y los selectores.

### 1. Captura simple

```
python scripts/captura.py --ruta "#/galeria" --salida "%TEMP%/hotel/galeria.png"
```

### 2. Tema oscuro

```
python scripts/captura.py --ruta "#/hoy" --tema oscuro --salida "%TEMP%/hotel/hoy-oscuro.png"
```

### 3. Móvil 390x844

```
python scripts/captura.py --ruta "#/bandeja" --ancho 390 --alto 844 --pagina-completa --salida "%TEMP%/hotel/bandeja-movil.png"
```

### 4. Flujo con clic y escritura

```
python scripts/captura.py --ruta legacy --paso "click:#btnSync" --paso "esperar-selector:#listado .fila" --paso "escribir:#chatTexto=¿Qué llegadas hay hoy?" --paso "click:#btnChat" --paso "esperar-selector:#chatLog > *" --paso "captura:%TEMP%/hotel/chat.png"
```

### 5. Comprobar un texto

```
python scripts/captura.py --ruta legacy --paso "click:button:texto('Leer reservas de RoomCloud')" --paso "esperar-selector:#listado .fila" --paso "texto:#resumenPartes" --paso "existe:#listado .fila"
```

El resultado queda en `textos` y en `existe`.

### 6. Comprobar el foco con tab

```
python scripts/captura.py --ruta legacy --paso "tab:3" --salida "%TEMP%/hotel/foco.png"
```

En `pasos[0].detalle.foco` están el elemento enfocado, `focus_visible` y `anillo_visible`, que vale false cuando el foco no tiene contorno ni sombra.

### 7. Dos tamaños

```
python scripts/captura.py --ruta "#/hoy" --paso "captura:%TEMP%/hotel/hoy-1440.png" --paso "viewport:390x844" --paso "captura:%TEMP%/hotel/hoy-390.png"
```

### 8. Informe de consola

```
python scripts/captura.py --ruta "#/ocupacion" --paso "esperar:1500"
```

Sin capturas, sirve para mirar solo `consola`, `excepciones` y `peticiones_fallidas`, y el código de salida dice si alguna trae algo.

## Pasos y opciones

- `click:SEL` y `hover:SEL` mueven el ratón real al centro del elemento, con scroll si hace falta, y fallan si otro elemento lo tapa.
- `escribir:SEL=TEXTO` enfoca, borra y teclea con `Input.insertText`, que no genera keydown, así que para enviar usa `tecla:Enter`. En un `select` elige la opción por valor o por texto, y en los campos de fecha asigna el valor.
- `tecla:Enter` admite también `Escape`, `Space`, `ArrowDown`, `Shift+Tab` o `Control+a`, y `tab:N` pulsa Tab N veces.
- `esperar:MS`, `esperar-selector:SEL`, `scroll:SEL`, `viewport:ANCHOxALTO`, `tema:claro|oscuro` y `navegar:#/ruta` cambian el estado de la página.
- `captura:RUTA.png` y `captura-elemento:SEL=RUTA.png` guardan una imagen, y con `--pagina-completa` la captura incluye también el contenido de los contenedores con scroll propio. `--salida` hace una última captura cuando acaban los pasos.
- `texto:SEL`, `existe:SEL` y `js:EXPRESION` guardan su resultado en `textos`, `existe` y `resultados_js`.

Los selectores son CSS y admiten el filtro final `:texto('...')` para elegir por el texto visible, por ejemplo `button:texto('Aprobar')`. Tras cada interacción el script espera a que terminen la red, las fuentes y las animaciones finitas, así que casi nunca hace falta `esperar`. Cuando las comillas del shell se complican, `--pasos-json FICHERO` lee los pasos de una lista JSON de cadenas, una por paso y con la misma sintaxis.

Las demás opciones salen con `--ayuda`: `--movimiento-reducido`, `--esperar-ms`, `--servidor URL` para reutilizar un servidor ya arrancado, `--sin-servidor` con `--url` para páginas externas, `--continuar-tras-fallo` y `--permitir-404 /api/ruta` para perdonar un 404 esperado.

## Cómo leer el informe

- `ok` y el código de salida: 0 si no hay errores de consola, excepciones ni peticiones fallidas, 1 si los hay o si falla un paso, y 2 si falla el entorno (servidor, Chrome, argumentos o tiempo, con la causa en `error`). Los `warning` no cuentan, y `--permitir-errores` deja el código en 0 con `ok` en false, pero un paso fallido siempre cuenta.
- `pasos` trae cada paso con `ok`, `ms` y `detalle`. El primero que falla muestra en `error` si el elemento no existe, no es visible o está tapado, deja una captura en `capturas_diagnostico` y omite los siguientes.
- `capturas` son rutas absolutas con barras normales, y `textos`, `existe` y `resultados_js` repiten el selector o la expresión con el sufijo `(2)` si los usas dos veces.
- `consola` recoge todos los niveles con texto, url y línea. Los `error` cuentan salvo los de `origen: "red"`, que ya salen en `peticiones_fallidas`.
- `excepciones` trae el texto y la pila de los errores no capturados y de las promesas rechazadas, y un `alert`, `confirm` o `prompt` cuenta como error de consola porque el contrato los prohíbe.
- `peticiones_fallidas` lista las respuestas 4xx y 5xx y los errores de red, salvo los 404 permitidos y el de `/favicon.ico`.
- `avisos` no cambian el código y cubren el scroll horizontal del documento y, con la ventana en 800 px o menos, el de un contenedor interno, además de la red que no se calma y de que `app/store.py` aún no lea `HOTEL_DB`.
- `log_servidor` aparece cuando uvicorn escribió algo, por ejemplo el traceback de un 500.

## Límites

- No ve el navegador real del usuario: es un Chrome nuevo con perfil vacío, sin extensiones, sesión ni zoom, y no prueba Firefox ni Safari.
- El reloj de la demo es fijo en 2026-10-24T09:00 (`DEMO_START`), pero el navegador usa la fecha real, así que todo lo que el front lea de `Date.now()` no coincide con la demo.
- El servidor arranca sin `ANTHROPIC_API_KEY`, así que el chat y el OCR responden en modo simulado, sin coste y siempre igual.
- El móvil es una ventana estrecha con ratón, sin emulación táctil, y los desplegables nativos (`select` y selector de fecha) no salen en las capturas.
- Mientras `app/store.py` no lea `HOTEL_DB`, el servidor usa `data/db.json` y dos ejecuciones simultáneas en el mismo árbol comparten ese fichero.
- Con `--servidor` la semilla por defecto reinicia los datos de ese servidor, así que usa `--semilla ninguna` para no tocarlos.
- Git Bash convierte los argumentos que empiezan por barra, incluso `"#/hoy"`, en rutas de Windows, y el script lo deshace en `--ruta`, `--permitir-404` y `--paso`.
- La salida es UTF-8, así que para leerla desde otro script de Python en Windows usa `python -X utf8`.
- No entra en iframes ni en shadow DOM.
