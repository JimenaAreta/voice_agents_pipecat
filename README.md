# Bot de voz para restaurante con Pipecat

Este repositorio contiene un ejemplo de agente de voz. El asistente atiende llamadas de un restaurante español y permite:

- Tomar pedidos de comida.
- Añadir uno o varios productos del menu.
- Pedir telefono y direccion cuando corresponde.
- Reservar mesa.
- Pedir dia, numero de personas, hora, nombre y telefono.
- Confirmar el pedido o la reserva y despedirse.

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
- `src/flows/flow_nodes.py`: nodo inicial que decide entre pedido y reserva.
- `src/flows/ordering.py`: logica de pedidos de comida.
- `src/flows/reservations.py`: logica de reservas.
- `src/services/services.py`: configura OpenAI, Deepgram y ElevenLabs.
- `src/services/menu.py`: menu del restaurante.
- `src/services/common_nodes.py`: instrucciones globales y nodos compartidos.
- `src/services/speech_format.py`: formato de telefonos y horas para que el TTS los lea bien.
- `tests/`: carpeta para pruebas.
- `.env.example`: plantilla de variables de entorno.

### Orden recomendado para estudiar el código

Sigue este recorrido:

1. `flows/flow_nodes.py`: observa cómo se elige entre pedido y reserva.
2. `flows/reservations.py`: sigue las herramientas y transiciones de una reserva.
3. `flows/ordering.py`: revisa cómo se mantiene y confirma un pedido.
4. `main.py`: identifica cómo se conectan servicios, pipeline y flujo.
5. `pipeline.py`: estudia al final VAD, Smart Turn y los procesadores de audio.

La lógica conversacional y la infraestructura de voz están separadas a propósito:
se puede comprender primero qué hace el agente y después cómo procesa el audio.

## Requisitos

Antes de empezar instala:

- `uv`, para gestionar dependencias de Python de forma rapida.

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

El archivo `.env` guarda tus claves privadas. No se sube a Git. Usa el fichero `.env.example`.

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
uv venv
source .venv/bin/activate
uv sync
```

En Windows el comando es el mismo:


```powershell
uv venv
.\.venv\Scripts\activate
uv sync
```

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

Los escenarios de `evals/` cubren reservas disponibles, alternativas, cambio de
intención, pedidos múltiples y entradas ambiguas. Con el bot iniciado mediante
el transporte de evaluación pueden ejecutarse con Pipecat Evals en modo texto;
para comprobar VAD, pausas e interrupciones se deben ejecutar después en modo
audio con grabaciones representativas del entorno final.

## 9. Generar la diapositiva de reservas

El generador usa objetos editables de PowerPoint mediante `@oai/artifact-tool`:

```bash
uv run python scripts/generate_pipecat_slides.py
```

La salida se guarda en `artifacts/pipecat_reservation_flow.pptx` y representa
solo la reserva, aunque el agente conserva también el flujo de pedidos.

## 10. Parar el servidor

En la terminal donde esta corriendo:

```text
Ctrl + C
```
