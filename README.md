# Generador local de videos con IA

Aplicación web local para producir videos a partir de prompts, imágenes Agnes AI y una narración. Genera imágenes en paralelo con hasta 10 claves API, crea narración de voz con Edge TTS (requiere internet) o acepta un audio propio, incorpora subtítulos SRT y monta un MP4 1080p con movimiento Ken Burns usando FFmpeg.

## Inicio rápido en Windows (doble clic)

1. Descarga el ZIP de esta rama y descomprímelo.
2. Haz doble clic en **`Iniciar Frameforge.bat`**.
3. En el primer inicio, el lanzador descarga Python portátil, FFmpeg portátil e instala las dependencias dentro de la propia carpeta del proyecto. No pide permisos de administrador ni que escribas comandos. Necesita conexión a Internet y puede tardar varios minutos; después abre el navegador en http://127.0.0.1:8000.
4. Pega tus prompts y claves Agnes en la página. Cuando termines, cierra el servidor con el archivo **`Detener Frameforge.bat`** o termina `python.exe` desde el Administrador de tareas.

El primer arranque descarga componentes en `.runtime/` (aproximadamente 100–200 MB, según dependencias y versión de FFmpeg). Se guardan en la carpeta descomprimida, así que los siguientes inicios no vuelven a descargarlos. El ZIP inicial solo contiene el código y los lanzadores; **no es una aplicación compilada autocontenida**. Requiere Windows 10/11 de 64 bits e Internet para la preparación inicial, TTS de Edge y los servicios de Agnes.

Si Windows muestra una advertencia de seguridad, verifica que descargaste el ZIP de este repositorio antes de permitir que se ejecute. El script no solicita privilegios de administrador; descarga Python/FFmpeg portátiles y paquetes Python oficiales.

## Inicio manual (macOS, Linux o desarrollo)

Requiere Python 3.10+ y FFmpeg/ffprobe instalados en el sistema:

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
3. Escribe la narración para crear voz en español con Edge TTS, o carga un audio propio. Para subtítulos, proporciona el guion en el campo correspondiente o deja que use el texto de narración. Con audio propio, pega también el texto del que quieres generar subtítulos.
4. Elige la voz y los FPS y pulsa **Crear MP4**. El resultado queda disponible para descarga en la página.

La sincronización de subtítulos se distribuye aproximadamente según la longitud de cada línea; no se realiza reconocimiento automático del habla. Los recursos se guardan localmente en `data/jobs/`.

## Configuración y privacidad

- Endpoint por defecto: `https://apihub.agnes-ai.cn/v1/images/generations`.
- Modelo por defecto: `agnes-image-2.1-flash`.
- `AGNES_IMAGE_ENDPOINT` puede establecer un endpoint alternativo antes de iniciar la app.
- Las claves API no se guardan en disco ni se devuelven en la API de estado. No compartas la carpeta de la sesión ni expongas el servidor en una red pública.
- El montaje del video se realiza localmente. La generación de imágenes y Edge TTS requieren Internet.

La disponibilidad de modelos, tamaños y cuotas depende de Agnes. FFmpeg debe incluir los filtros `zoompan` y `subtitles`/libass para incrustar subtítulos.
