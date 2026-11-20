import os
import re
import uuid
import json
import base64
import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("VIDEO_APP_DATA", ROOT / "data"))
JOBS_DIR = DATA / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_ENDPOINT = os.getenv("AGNES_IMAGE_ENDPOINT", "https://apihub.agnes-ai.cn/v1/images/generations")
MAX_UPLOAD = 250 * 1024 * 1024
jobs: dict[str, dict[str, Any]] = {}
app = FastAPI(title="Generador local de videos IA")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "app" / "templates")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def safe_endpoint(value: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(400, "El endpoint debe ser una URL HTTPS válida.")
    return value.rstrip("/")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"endpoint": DEFAULT_ENDPOINT})


@app.get("/api/health")
async def health():
    return {"ok": True, "ffmpeg": shutil.which("ffmpeg") is not None, "ffprobe": shutil.which("ffprobe") is not None}


@app.post("/api/jobs")
async def create_job(
    prompts: str = Form(...),
    api_keys: str = Form(...),
    model: str = Form("agnes-image-2.1-flash"),
    endpoint: str = Form(DEFAULT_ENDPOINT),
    concurrency: int = Form(4),
    size: str = Form("1024x1024"),
):
    prompt_list = [line.strip() for line in prompts.splitlines() if line.strip()]
    keys = [line.strip() for line in api_keys.splitlines() if line.strip()]
    if not prompt_list:
        raise HTTPException(400, "Añade al menos un prompt, uno por línea.")
    if not keys:
        raise HTTPException(400, "Añade al menos una clave API de Agnes.")
    if len(keys) > 10:
        raise HTTPException(400, "Se admiten como máximo 10 claves API.")
    if len(prompt_list) > 200:
        raise HTTPException(400, "Se admiten como máximo 200 prompts por proyecto.")
    if not 1 <= concurrency <= 10:
        raise HTTPException(400, "La concurrencia debe estar entre 1 y 10.")
    if not re.fullmatch(r"\d{3,4}x\d{3,4}", size):
        raise HTTPException(400, "Tamaño no válido. Usa, por ejemplo, 1024x1024.")
    endpoint = safe_endpoint(endpoint)
    job_id = uuid.uuid4().hex[:12]
    folder = JOBS_DIR / job_id
    folder.mkdir(parents=True)
    jobs[job_id] = {"id": job_id, "status": "generating", "total": len(prompt_list), "completed": 0,
                    "images": [], "errors": [], "message": "Generando imágenes…", "video": None}
    # The credentials are only captured by this task and never included in status responses or written to disk.
    asyncio.create_task(generate_images(job_id, folder, prompt_list, keys, model.strip(), endpoint, size, concurrency))
    return {"id": job_id, "status": "generating", "total": len(prompt_list)}


async def generate_images(job_id: str, folder: Path, prompts: list[str], keys: list[str], model: str,
                          endpoint: str, size: str, concurrency: int):
    job = jobs[job_id]
    semaphore = asyncio.Semaphore(concurrency)
    client_timeout = httpx.Timeout(180, connect=25)
    async with httpx.AsyncClient(timeout=client_timeout, follow_redirects=True) as client:
        async def generate(index: int, prompt: str):
            async with semaphore:
                key = keys[index % len(keys)]
                for attempt in range(3):
                    try:
                        response = await client.post(endpoint, headers={"Authorization": f"Bearer {key}",
                                                                         "Content-Type": "application/json"},
                                                     json={"model": model, "prompt": prompt, "size": size})
                        response.raise_for_status()
                        payload = response.json()
                        item = (payload.get("data") or [None])[0]
                        if not isinstance(item, dict):
                            raise ValueError("La respuesta de Agnes no contiene data[0].")
                        image_path = folder / f"image_{index + 1:03d}.png"
                        if item.get("url"):
                            image_response = await client.get(item["url"])
                            image_response.raise_for_status()
                            image_bytes = image_response.content
                        elif item.get("b64_json"):
                            image_bytes = base64.b64decode(item["b64_json"], validate=True)
                        else:
                            raise ValueError("La respuesta no contiene url ni b64_json.")
                        if not image_bytes or len(image_bytes) > 40 * 1024 * 1024:
                            raise ValueError("Imagen vacía o superior al límite de 40 MB.")
                        image_path.write_bytes(image_bytes)
                        job["images"].append({"index": index, "name": image_path.name, "prompt": prompt})
                        job["completed"] += 1
                        return
                    except Exception as exc:
                        if attempt == 2:
                            job["errors"].append({"index": index, "prompt": prompt, "error": str(exc)[:300]})
                        else:
                            await asyncio.sleep(1.5 * (attempt + 1))
        await asyncio.gather(*(generate(i, p) for i, p in enumerate(prompts)))
    job["images"].sort(key=lambda img: img["index"])
    job["status"] = "ready" if job["images"] else "failed"
    job["message"] = f"{len(job['images'])} de {job['total']} imágenes generadas."


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Proyecto no encontrado en esta sesión del servidor.")
    return {key: value for key, value in job.items() if key not in {"api_keys"}}


@app.get("/api/jobs/{job_id}/images/{filename}")
async def get_image(job_id: str, filename: str):
    if not re.fullmatch(r"image_\d{3}\.png", filename):
        raise HTTPException(400, "Nombre de imagen no válido.")
    path = JOBS_DIR / job_id / filename
    if not path.is_file():
        raise HTTPException(404, "Imagen no encontrada.")
    return FileResponse(path, media_type="image/png")


def run_command(args: list[str], timeout: int = 1800) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or "Error de FFmpeg")[-1800:])
    return result.stdout.strip()


def make_srt(text: str, duration: float, path: Path):
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    if not lines:
        path.write_text("", encoding="utf-8")
        return
    weights = [max(1, len(line)) for line in lines]
    total = sum(weights)
    cursor = 0.0
    blocks = []
    for i, (line, weight) in enumerate(zip(lines, weights), 1):
        end = duration if i == len(lines) else cursor + duration * weight / total
        start_ms, end_ms = round(cursor * 1000), round(end * 1000)
        blocks.append(f"{i}\n{stamp(start_ms)} --> {stamp(end_ms)}\n{line}\n")
        cursor = end
    path.write_text("\n".join(blocks), encoding="utf-8-sig")


def stamp(milliseconds: int) -> str:
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


@app.post("/api/jobs/{job_id}/render")
async def render_video(
    job_id: str,
    narration: str = Form(""),
    subtitles: str = Form(""),
    voice: str = Form("es-ES-AlvaroNeural"),
    fps: int = Form(30),
    min_seconds: float = Form(3.0),
    burn_subtitles: bool = Form(True),
    audio: UploadFile | None = File(None),
):
    job = jobs.get(job_id)
    if not job or job["status"] != "ready":
        raise HTTPException(400, "Primero genera al menos una imagen correctamente.")
    if not 24 <= fps <= 60 or not 1 <= min_seconds <= 30:
        raise HTTPException(400, "FPS o duración por imagen fuera de rango.")
    narration = narration.strip()
    subtitles = subtitles.strip() or narration
    if audio is None and not narration:
        raise HTTPException(400, "Escribe la narración o carga un archivo de audio.")
    if burn_subtitles and not subtitles:
        raise HTTPException(400, "Añade texto para crear los subtítulos o desactiva su incrustación.")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(500, "Instala FFmpeg y ffprobe y asegúrate de que están en PATH.")
    folder = JOBS_DIR / job_id
    audio_path = folder / "narration_audio"
    try:
        if audio is not None and audio.filename:
            data = await audio.read(MAX_UPLOAD + 1)
            if len(data) > MAX_UPLOAD:
                raise HTTPException(413, "El audio supera el límite de 250 MB.")
            suffix = Path(audio.filename).suffix.lower()
            if suffix not in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".webm"}:
                raise HTTPException(400, "Formato de audio no compatible.")
            audio_path = folder / f"narration{suffix}"
            audio_path.write_bytes(data)
        else:
            import edge_tts
            communicate = edge_tts.Communicate(narration, voice)
            await communicate.save(str(audio_path.with_suffix(".mp3")))
            audio_path = audio_path.with_suffix(".mp3")
        probe = json.loads(run_command(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                        "-of", "json", str(audio_path)]))
        audio_duration = float(probe["format"]["duration"])
        if audio_duration <= 0:
            raise ValueError("No se pudo determinar la duración del audio.")
        srt_path = folder / "subtitles.srt"
        if subtitles:
            make_srt(subtitles, audio_duration, srt_path)
        images = [folder / entry["name"] for entry in job["images"] if (folder / entry["name"]).is_file()]
        if not images:
            raise ValueError("No quedan imágenes generadas para editar.")
        per_image = max(min_seconds, audio_duration / len(images))
        durations = [audio_duration / len(images)] * len(images)
        durations = [max(0.5, d) for d in durations]
        # The narration determines the final duration; distribute it evenly across the available images.
        inputs = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for image, duration in zip(images, durations):
            inputs.extend(["-loop", "1", "-framerate", str(fps), "-t", f"{duration:.4f}", "-i", str(image)])
        audio_index = len(images)
        inputs.extend(["-i", str(audio_path)])
        filters = []
        labels = []
        frame_count = max(1, round(durations[0] * fps))
        for i in range(len(images)):
            label = f"v{i}"
            filters.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
                           f"zoompan=z='min(zoom+0.0005,1.08)':d={frame_count}:s=1920x1080:fps={fps},setsar=1[{label}]")
            labels.append(f"[{label}]")
        filters.append("".join(labels) + f"concat=n={len(images)}:v=1:a=0[vbase]")
        video_map = "[vbase]"
        if burn_subtitles and subtitles:
            escaped = str(srt_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            filters.append(f"[vbase]subtitles='{escaped}':force_style='FontName=Arial,FontSize=26,Outline=2,Shadow=1,Alignment=2,MarginV=48'[vout]")
            video_map = "[vout]"
        output_path = folder / "video_1080p.mp4"
        inputs.extend(["-filter_complex", ";".join(filters), "-map", video_map, "-map", f"{audio_index}:a:0",
                       "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                       "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                       str(output_path)])
        job["status"] = "rendering"
        await asyncio.to_thread(run_command, inputs, 3600)
        job["status"] = "complete"
        job["video"] = f"/api/jobs/{job_id}/video"
        job["message"] = "Video MP4 1080p creado."
        return {"status": "complete", "video": job["video"]}
    except HTTPException:
        raise
    except Exception as exc:
        job["status"] = "ready"
        raise HTTPException(500, f"No se pudo crear el video: {str(exc)[:500]}") from exc


@app.get("/api/jobs/{job_id}/video")
async def download_video(job_id: str):
    path = JOBS_DIR / job_id / "video_1080p.mp4"
    if not path.is_file():
        raise HTTPException(404, "El video aún no está listo.")
    return FileResponse(path, media_type="video/mp4", filename=f"agnes_video_{job_id}.mp4")
