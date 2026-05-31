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
- Flujos conversacionales: Pipecat Flows

## Estructura del proyecto

- `src/main.py`: monta el pipeline de Pipecat.
- `src/flows/flow_nodes.py`: nodo inicial que decide entre pedido y reserva.
- `src/flows/ordering.py`: logica de pedidos de comida.
- `src/flows/reservations.py`: logica de reservas.
- `src/services/services.py`: configura OpenAI, Deepgram y ElevenLabs.
- `src/services/menu.py`: menu del restaurante.
- `src/services/common_nodes.py`: instrucciones globales y nodos compartidos.
- `src/services/speech_format.py`: formato de telefonos y horas para que el TTS los lea bien.
- `scripts/`: scripts auxiliares, como la generacion de diapositivas.
- `tests/`: carpeta para pruebas.
- `.env.example`: plantilla de variables de entorno.

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

## 8. Parar el servidor

En la terminal donde esta corriendo:

```text
Ctrl + C
```
