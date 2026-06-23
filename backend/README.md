# Backend local para consultas sobre videos

Este backend permite cargar videos de capacitacion, extraer audio localmente, transcribirlo con timestamps y consultar coincidencias usando TF-IDF + similitud coseno. No usa LLM ni servicios remotos para responder preguntas; las respuestas son extractivas y citan fragmentos relevantes del video.

## Requisitos

- Python 3.10+
- ffmpeg disponible en PATH recomendado, pero no obligatorio
- Espacio en disco para videos, audio extraido y modelo local de Whisper

## Instalacion

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

El primer procesamiento puede descargar el modelo configurado en `WHISPER_MODEL` si no existe localmente. Para un prototipo rapido en CPU, `base` + `int8` es un buen punto de partida. Para mayor calidad, usa `small` o `medium`, asumiendo mas tiempo de procesamiento.

Para evitar picos de memoria con videos largos, el backend parte el audio extraido en chunks temporales antes de enviarlo a Whisper. El valor por defecto procesa bloques de 5 minutos:

```env
WHISPER_AUDIO_CHUNK_SECONDS=300
WHISPER_BEAM_SIZE=5
```

Si el servidor esta muy ajustado de memoria, baja `WHISPER_AUDIO_CHUNK_SECONDS` a `180` o `120`. Si necesitas reducir aun mas el consumo durante decodificacion, puedes bajar `WHISPER_BEAM_SIZE` a `1` a cambio de algo menos de precision.

Si `ffmpeg` no esta en PATH, el backend intenta transcribir directamente el archivo original con `faster-whisper`/PyAV. Tener `ffmpeg` instalado sigue siendo recomendable porque genera un `audio.wav` normalizado y hace el flujo mas predecible con videos largos.

Si tu terminal ve `ffmpeg` pero el backend no, configura la ruta exacta en `.env`:

```powershell
where.exe ffmpeg
```

Luego copia esa ruta en:

```env
FFMPEG_BIN=C:\ruta\a\ffmpeg.exe
```

## Ejecutar

Para procesar videos, usa el servidor **sin** `--reload`. El modo reload puede reiniciar Uvicorn cuando cambian archivos dentro de `storage/`, cortando la transcripcion en background.

```powershell
.\run_backend.ps1
```

La consola mostrara trazas del procesamiento, por ejemplo:

```text
[video:...] Upload stored ...
[video:...] Starting ffmpeg audio extraction
[video:...] ffmpeg audio extraction finished ...
[video:...] Loading faster-whisper model ...
[video:...] Whisper still running elapsed=10.0s segments=0 ...
[video:...] Segment emitted id=0 start=... end=...
[video:...] Partial transcript saved segments=10 progress=...
[video:...] Processing finished successfully; status=ready
```

Luego abre:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/system/dependencies`
- `GET http://localhost:8000/docs`

Si necesitas `--reload` durante desarrollo, excluye `storage/` o usa una carpeta fuera del backend:

```powershell
uvicorn app.main:app --reload --reload-exclude "storage/*" --reload-exclude "storage/**/*" --port 8000
```

Otra opcion es configurar en `.env`:

```env
VIDEO_STORAGE_DIR=C:\tmp\bmsc-ai-video-storage
```

## Flujo principal

Formatos aceptados para video: `.mp4`, `.mkv` y `.mvk` ademas de otros formatos comunes de audio/video. La extension estándar de Matroska es `.mkv`; `.mvk` se acepta como alias por si llega un archivo nombrado asi.

1. Cargar video:

```powershell
curl.exe -X POST "http://localhost:8000/videos" -F "file=@C:\ruta\capacitacion.mp4"
```

La respuesta incluye el `id`. El procesamiento queda en background y cambia de `uploaded` a `processing`, luego a `ready` o `failed`.

2. Revisar estado:

```powershell
curl.exe "http://localhost:8000/videos/{video_id}"
```

3. Ver transcripcion con timestamps:

```powershell
curl.exe "http://localhost:8000/videos/{video_id}/transcript"
```

4. Consultar coincidencias:

```powershell
curl.exe -X POST "http://localhost:8000/videos/{video_id}/query" `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"autenticacion multifactor\", \"top_k\":5, \"min_score\":0.05}"
```

La respuesta incluye `answer`, `confidence` y `matches`. Cada elemento de `matches` devuelve:

- `score`: puntaje hibrido de similitud
- `start_timecode` / `end_timecode`: ubicacion exacta en el video
- `text`: fragmento encontrado

5. Preguntar al video con respuesta extractiva:

```powershell
curl.exe -X POST "http://localhost:8000/videos/{video_id}/ask" `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"desde donde descargo la app de banca movil?\", \"top_k\":3, \"min_score\":0.0}"
```

Este endpoint no usa LLM. Recupera los fragmentos mas relevantes y arma una respuesta tipo bot, citando el rango del video:

```json
{
  "answer": "Se habla de esto entre 00:00:29.870 y 00:00:38.350. Según el video: Primero, descarga...",
  "sources": [...]
}
```

Para resultados mas precisos, los chunks de busqueda son cortos por defecto:

```env
SEARCH_CHUNK_SECONDS=14
SEARCH_CHUNK_MAX_CHARS=320
```

Si quieres mas contexto por resultado, sube esos valores y reprocesa el video con `POST /videos/{video_id}/process`.

Si la transcripcion ya existe y solo cambiaste la logica de busqueda, puedes reconstruir el indice sin volver a transcribir:

```powershell
curl.exe -X POST "http://localhost:8000/videos/{video_id}/index"
```

## Verificar uso de ffmpeg

El backend intenta extraer audio con `ffmpeg` primero. Si `ffmpeg` no esta disponible para el proceso o falla con el archivo, usa el archivo original directamente con `faster-whisper`/PyAV.

Para confirmar que el proceso ve `ffmpeg`:

```powershell
curl.exe "http://localhost:8000/system/dependencies"
```

La respuesta debe incluir:

```json
{
  "ffmpeg": {
    "available": true,
    "path": "C:\\...",
    "version": "ffmpeg version ..."
  }
}
```

Para confirmar que un video procesado uso `ffmpeg`, consulta:

```powershell
curl.exe "http://localhost:8000/videos/{video_id}"
```

Busca `audio_extraction_backend`. Si vale `"ffmpeg"`, ese video uso ffmpeg. Si vale `"direct"`, cayo al modo alternativo y `audio_extraction_error` explica por que.

Durante el procesamiento, `processing_stage` indica la fase actual:

- `queued`: el video espera su turno; otro video esta usando Whisper.
- `extracting_audio`: FFmpeg esta generando `audio.wav`.
- `transcribing`: Whisper esta transcribiendo; esta es la fase lenta.
- `indexing`: se esta creando el indice TF-IDF.
- `ready`: ya se puede consultar.
- `interrupted`: el backend fue reiniciado o cerrado mientras procesaba; usa `POST /videos/{video_id}/process`.

`GET /videos/{video_id}` tambien devuelve campos para barra de progreso:

- `processing_progress`: porcentaje estimado de 0 a 100.
- `transcribed_seconds`: segundo del audio hasta donde Whisper avanzo.
- `transcribed_timecode`: el mismo avance en formato `HH:MM:SS.mmm`.
- `progress_updated_at`: ultima vez que se actualizo el avance. Si este valor no cambia durante mucho tiempo, el proceso puede estar cargando modelo o bloqueado.

## Estructura

```text
app/
  main.py           API FastAPI
  service.py        Orquestacion del flujo
  transcription.py  ffmpeg opcional + faster-whisper local
  chunking.py       Agrupacion de segmentos con timestamps
  search.py         TF-IDF + similitud coseno
  storage.py        Persistencia local en JSON
storage/
  videos/{id}/      Video original, audio.wav, metadata, transcript y chunks
```

## Notas del prototipo

- El procesamiento corre como background task dentro de FastAPI. Para produccion conviene moverlo a una cola de trabajo.
- Videos de 2 horas pueden tardar bastante en CPU; para acelerar, configura `WHISPER_DEVICE=cuda` si el equipo tiene GPU compatible.
- TF-IDF no entiende semantica profunda: encuentra coincidencias por vocabulario y frases cercanas. Mas adelante se puede reemplazar o complementar con embeddings/vector DB sin cambiar demasiado el contrato de la API.
- Puedes importar `BMSC-AI-Video.postman_collection.json` en Postman para probar todos los endpoints.
