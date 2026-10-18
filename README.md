# Bot de voz para restaurante con Pipecat

Este repositorio contiene un ejemplo de agente de voz. El asistente atiende llamadas de un restaurante español y permite:

- Tomar pedidos de comida.
- Añadir uno o varios productos del menu.
- Pedir telefono y direccion cuando corresponde.
- Reservar mesa.
- Pedir dia, numero de personas, hora, nombre y telefono.
- Confirmar el pedido o la reserva y despedirse.

SQLite es el origen de la disponibilidad y las reservas (`data/reservations.sqlite3`,
configurable con `RESERVATIONS_DB_PATH`). La tabla `reservation_calendar` contiene
cinco horas por día (18:00 a 22:00) con disponibilidad específica para cada fecha.
El calendario de demo combina días completamente libres, días completos y días con
distintas horas ocupadas. Cada mes se genera de forma reproducible al consultarlo,
sin sobrescribir cambios posteriores ni reservas existentes.

Octubre de 2026 está inicializado en la base local. Por ejemplo, el 21 tiene todas
las horas habilitadas, el 22 está completo y el 23 tiene libres las 18:00, 20:00 y
22:00, salvo las reservas que se añadan después. Las fechas relativas se resuelven
antes de consultar el calendario.
Cada fecha y hora admite una reserva, independientemente del número de personas.
Al confirmarla, el hueco queda ocupado para las siguientes llamadas, incluso después
de reiniciar el servidor; la misma hora en otra fecha sigue disponible. La comprobación
y el guardado son una única transacción para evitar reservas simultáneas del mismo
hueco. Si otro cliente se adelanta, el agente ofrece las horas que aún quedan libres.

La base de datos conserva nombre y teléfono y está excluida de Git. El agente solo
confirma después de guardar; si falla, ofrece reintentar sin duplicar el registro.
No hay integración con una API del restaurante ni borrado automático de registros.

Los días «hoy», «mañana», «pasado mañana» y «pasado» (equivalente a pasado mañana)
se resuelven a una fecha concreta usando la zona `Europe/Madrid`. La reserva guarda
esa fecha en formato ISO y la confirmación la expresa en castellano. Otras fechas
habladas, como «el viernes», se conservan como texto.

El saludo identifica al agente como asistente virtual. Tras una interrupción sin
transcripción, pide repetir en español, con una recuperación consecutiva como máximo.

## Stack

- VAD: Silero
- STT: Deepgram
- LLM: OpenAI Responses API
- TTS: ElevenLabs
- Transporte local: WebRTC
- Flujos conversacionales: Pipecat Flows integrado en Pipecat
- Fin de turno: Silero VAD + Smart Turn v3

## Estructura del proyecto

- `src/main.py`: punto de entrada; muestra el recorrido general de la aplicación.
- `src/pipeline.py`: configura VAD, Smart Turn y la cadena de audio de Pipecat.
- `src/config.py`: carga y valida la configuración externa.
- `src/flows/restaurant.yaml`: nodos, prompts, herramientas y transiciones de pedidos y reservas.
- `src/flows/restaurant_flow.py`: carga el YAML y conecta sus handlers Python.
- `src/flows/ordering.py`: logica de pedidos de comida.
- `src/flows/reservations.py`: logica de reservas.
- `src/services/services.py`: configura OpenAI, Deepgram y ElevenLabs.
- `src/services/menu.py`: menu del restaurante.
- `src/services/common_nodes.py`: acciones Python compartidas referenciadas desde el YAML.
- `src/services/speech_format.py`: formato de teléfonos, horas, fechas numéricas e importes para que el TTS los lea bien.
- `src/services/reservation_store.py`: registro persistente de reservas confirmadas en SQLite.
- `src/services/validation.py`: normalización y validación de datos de pedidos y reservas.
- `tests/`: pruebas deterministas de los flujos, validaciones y formato de voz.
- `evals/`: escenarios YAML de evaluación y pruebas de su estructura.
- `.env.example`: plantilla de variables de entorno.

### Orden recomendado para estudiar el código

Sigue este recorrido:

1. `src/flows/restaurant.yaml`: observa los nodos y cómo se elige entre pedido y reserva.
2. `src/flows/restaurant_flow.py`: revisa cómo se carga el flujo y se resuelven sus handlers.
3. `src/flows/reservations.py`: sigue las herramientas de una reserva y sus resultados.
4. `src/flows/ordering.py`: revisa cómo se mantiene y confirma un pedido.
5. `src/main.py`: identifica cómo se conectan servicios, pipeline y flujo.
6. `src/pipeline.py`: estudia al final VAD, Smart Turn y los procesadores de audio.

La lógica conversacional y la infraestructura de voz están separadas a propósito:
se puede comprender primero qué hace el agente y después cómo procesa el audio.

## Requisitos

Antes de empezar instala:

- Python 3.11 o superior. El archivo `.python-version` selecciona Python 3.13 para `uv`.
- Git para clonar el repositorio.
- `uv`, para gestionar dependencias de Python (o `pip` para la instalación alternativa).
- Claves de API de OpenAI, Deepgram y ElevenLabs.
- Un navegador con acceso al micrófono y conexión a Internet para los servicios de voz.

## 1. Clonar el repositorio en VS Code

### macOS

Abre Terminal y ejecuta:

```bash
git clone <URL_DEL_REPOSITORIO>
cd voice_agents_pipecat
code .
```

Si `code .` no funciona, abre VS Code y activa el comando:

```text
Command Palette > Shell Command: Install 'code' command in PATH
```

### Windows

Abre PowerShell y ejecuta:

```powershell
git clone <URL_DEL_REPOSITORIO>
cd voice_agents_pipecat
code .
```

Tambien puedes clonar desde VS Code:

```text
Source Control > Clone Repository > pega la URL > Open
```

## 2. Crear el archivo `.env` partiendo de `.env.example`

El archivo `.env` guarda tus claves privadas y está excluido de Git. Copia la plantilla:

macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Si ya tienes un `.env`, conserva sus valores y consulta `.env.example` para añadir las opciones que falten.

## 3. Instalacion con `uv`

Esta es la opcion recomendada.

### Instalar `uv`

macOS:


```bash
pip install uv
```

Windows PowerShell:


```powershell
pip install uv
```

### Sincronizar dependencias

En la carpeta del proyecto:


```bash
uv sync
```

En Windows se utiliza también `uv sync`. Este comando crea `.venv` e instala
las dependencias, incluidas las de desarrollo; no necesitas activar el entorno
si ejecutas los comandos mediante `uv run`.

Ahora sí, abre `.env` y completa estos valores:

```env
OPENAI_API_KEY=tu_clave_de_openai
DEEPGRAM_API_KEY=tu_clave_de_deepgram
ELEVENLABS_API_KEY=tu_clave_de_elevenlabs
```

Por defecto el agente usa Smart Turn v3 para no confundir una pausa natural con
el final de una frase. En equipos con recursos limitados se puede usar el modo
por timeout:

```env
TURN_STOP_STRATEGY=timeout
USER_SPEECH_TIMEOUT=0.6
```

El resto de opciones de modelos, idioma, voz, transporte del LLM y VAD se
encuentran en `.env.example`. Por defecto, el LLM utiliza `gpt-4.1-nano` por
HTTP, Deepgram utiliza `nova-3` y ElevenLabs utiliza `eleven_flash_v2_5`.

No ajustes `DEEPGRAM_TTFS_P99_LATENCY` sin medir antes el entorno real con
`pipecat-ai/stt-benchmark`.

## 4. Instalacion sin `uv`

Usa esta opcion si no puedes instalar `uv`.

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Si PowerShell bloquea la activacion del entorno virtual, ejecuta:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Despues vuelve a activar:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 5. Seleccionar el interprete en VS Code

En VS Code:

```text
Command Palette > Python: Select Interpreter
```

Selecciona el interprete dentro de `.venv`.

Suele aparecer como:

- macOS: `.venv/bin/python`
- Windows: `.venv\Scripts\python.exe`

## 6. Ejecutar el bot

### Con `uv`

macOS o Windows:

```bash
uv run python src/main.py
```

Si instalaste con `pip`, ejecuta `python src/main.py` con el entorno virtual activado.

Cuando arranque, abre:

```text
http://localhost:7860/client
```

Permite el acceso al microfono en el navegador.

## 7. Probar la conversacion

Puedes probar frases como:

```text
Quiero hacer un pedido de comida.
```

```text
Quiero dos tortillas, una de croquetas y una paella.
```

```text
Quiero reservar una mesa.
```

```text
Para mañana, cuatro personas, a las siete de la tarde.
```

## 8. Pruebas y evaluaciones

Ejecuta las pruebas deterministas con:

```bash
uv run pytest
```

Si instalaste con `pip`, instala primero las herramientas de pruebas y ejecútalas
con el entorno activado:

```bash
python -m pip install pytest pytest-asyncio
python -m pytest
```

Los escenarios de `evals/orders.yaml` y `evals/reservations.yaml` describen
reservas disponibles, alternativas, cambio de intención, pedidos múltiples y
entradas ambiguas. `evals/test_schemas.py` valida su estructura; `pytest` no
mantiene conversaciones con los servicios externos ni evalúa el audio.

El repositorio no incluye un ejecutor de conversaciones con Pipecat Evals ni
un transporte de evaluación configurado en `src/main.py`. Para comprobar voz,
pausas e interrupciones, utiliza el cliente WebRTC y las frases de la sección anterior.

## 9. Parar el servidor

En la terminal donde esta corriendo:

```text
Ctrl + C
```
