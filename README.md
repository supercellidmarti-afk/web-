# Generador local de videos con IA

Aplicación web local para producir videos a partir de prompts, imágenes Agnes AI y una narración. Genera imágenes en paralelo con hasta 10 claves API, crea narración de voz con Edge TTS (requiere internet) o acepta un audio propio, incorpora subtítulos SRT y monta un MP4 1080p con movimiento Ken Burns usando FFmpeg.

## Requisitos

- Python 3.10 o posterior.
- FFmpeg y `ffprobe` instalados y disponibles en `PATH`.
- Conexión a Internet y una o varias claves Agnes AI para generar imágenes. Las claves se mantienen en memoria durante la sesión y no se guardan en disco.

## Inicio

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Abre http://127.0.0.1:8000. El servidor escucha solo en localhost por defecto.

## Uso

1. Pega un prompt por línea y añade tus claves Agnes (una por línea; hasta 10). El reparto concurrente respeta el máximo de concurrencia indicado.
2. Espera a que se generen las imágenes y revisa el resultado.
3. Escribe la narración para crear voz en español con Edge TTS, o carga un audio propio. Para subtítulos automáticos por texto, proporciona el guion en el campo de subtítulos o deja que use el texto de narración. Con audio propio, pega también el texto del que quieres generar subtítulos.
4. Elige la voz, los FPS y la duración mínima por imagen y pulsa **Crear MP4**. El resultado queda disponible para descarga en la página.

La sincronización de subtítulos se distribuye aproximadamente según la longitud de cada línea; no se realiza reconocimiento automático del habla. Los recursos se guardan localmente en `data/jobs/`.

## Configuración

- Endpoint por defecto: `https://apihub.agnes-ai.cn/v1/images/generations`.
- Modelo por defecto: `agnes-image-2.1-flash`.
- Se pueden sobrescribir endpoint, modelo, voz y parámetros desde la interfaz.
- `AGNES_IMAGE_ENDPOINT` puede establecer un endpoint alternativo antes de iniciar la app.

No publiques claves API ni expongas el servidor a una red pública. El endpoint de generación se restringe a HTTPS para reducir riesgos de filtración de claves.

## Límites

El endpoint de Agnes puede devolver URL o base64 en el formato OpenAI habitual. La disponibilidad de modelos, tamaños y cuotas depende del proveedor. FFmpeg debe incluir el filtro `zoompan` y, para subtítulos incrustados, el filtro `subtitles`/libass. La generación de voz de Edge TTS necesita Internet; la edición del video se realiza localmente.
