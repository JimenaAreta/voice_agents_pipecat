# Evaluación de agentes de voz

Material de la sesión de evaluación del agente de reservas. Las prácticas usan
datos sintéticos (replays) y no necesitan claves de API. Las dependencias se
instalan con el `uv sync` del repositorio; si instalaste con `pip`, añade
`python -m pip install pydantic-evals`.

## Estructura

- `metrics.py`: normalización, alineación palabra a palabra, WER, CER y WER de corpus.
- `schemas.py`: contratos Pydantic con los mismos nombres de campo que el agente.
- `p01_schema_stt.py`: práctica 1, esquema y WER.
- `p02_agent.py`: práctica 2, suite de reservas contra los handlers reales.
  La práctica 4 vuelve a usarla.
- `escucha.html` y `p03_ratings.py`: práctica 3, escucha A/B y valoraciones.
- `p02_solucion.py`: soluciones de C05 (práctica 2, JSON inválido) y C06
  (práctica 4, sin mesa); no repartir.
- `data/`: CSV de ejemplo para la práctica 3 (uno válido y uno con errores).
- `agent_scenarios/`: escenarios YAML de conversaciones del agente y los
  modelos que validan su estructura. No hay un ejecutor de conversaciones.
- `tests/`: pruebas de las prácticas y de los escenarios.

## Práctica 1: esquema y WER

```bash
cd evaluation
uv run python p01_schema_stt.py
```

El script muestra:

1. Payloads que `Slots` rechaza (tipo, campo extra, rango y formato de hora).
2. La alineación de cada caso con sus sustituciones, deleciones e inserciones.
3. El informe de Pydantic Evals: `RawWER`, `WER` normalizado, `SchemaValid` y
   `SlotsCorrect` con la razón de cada fallo.
4. La diferencia entre la media de WER por clip y el WER de corpus.

Las hipótesis siguen el formato que devuelve Deepgram con `smart_format`
(cifras, «21:00» y puntuación). Si escribes una referencia en palabras, compara
`RawWER` y `WER` para ver el efecto de la normalización.

## Práctica 2: suite de reservas

```bash
cd evaluation
uv run python p02_agent.py
uv run python p02_agent.py --fixed
```

Solo se simula el LLM: cada caso es un guion de llamadas a herramientas y
mensajes. Las herramientas son los handlers reales de `src/flows/reservations.py`
y cada caso usa una base SQLite temporal, así que la evidencia del backend es real.

Cada llamada a una herramienta se registra con Logfire como un paso de la traza.
El evaluador `Llama_collect_party_size` de C02 lee esa traza en lugar del
backend. Sin cuenta todo funciona en local; con `LOGFIRE_TOKEN` la traza se ve
también en Logfire.

| Caso | Qué comprueba |
|---|---|
| C01 | Reserva básica el 14/10 a las 21:00 |
| C02 | El usuario corrige de 4 a 5 personas; falla si no llama a `collect_party_size` |
| C03 | El viernes 16 a las 21:00 no hay mesa y acepta las 22:00 |
| C04 | El guardado escribe, pero la herramienta recibe un error; reintento sin duplicar |

La decisión se toma por puertas: todos los evaluadores en todos los casos, no
la media de assertions.

Las soluciones están en `p02_solucion.py` (`--fixed` también funciona):

| Caso | Práctica | Qué comprueba |
|---|---|---|
| C05 | 2 | La reserva se hace, pero el JSON de datos finales llega cortado |
| C06 | 4 | El 16/10 a las 21:00 no hay mesa, no acepta alternativa y no se reserva |

## Práctica 3: escucha y valoraciones

1. Abre `escucha.html` en Chrome, Edge o Safari (doble clic; no necesita servidor).
2. El operador elige las voces o velocidades de A y B y pulsa «Ocultar configuración».
3. Cada evaluador escucha los tres textos en orden aleatorio, puntúa la naturalidad
   (1-5), marca los datos que ha entendido y escribe una observación.
4. Descarga `valoraciones.csv` y ejecuta:

```bash
cd evaluation
uv run python p03_ratings.py --csv valoraciones.csv
```

Sin `--csv` se usa `data/valoraciones_ejemplo.csv`, que reproduce el debrief de
la sesión. `data/valoraciones_invalidas.csv` muestra cómo se rechaza un fichero
con valores fuera de escala.

Un voto cuenta como «datos correctos» cuando recupera todos los campos de su
texto: 3 en la reserva y 2 en los otros dos textos.

## Práctica 4: recuperación y decisión

Se vuelve a `p02_agent.py`. Añade un caso C06 en el que no hay mesa y el
cliente no acepta ninguna alternativa (`Expected(completed=False)`), y compara
la decisión con y sin `--fixed`:

```bash
cd evaluation
uv run python p02_agent.py
uv run python p02_agent.py --fixed
```

## Pruebas

Desde la raíz del repositorio, `uv run pytest` ejecuta también estas pruebas.
