const $ = (id) => document.getElementById(id);
let currentJob = null;
let pollTimer = null;

function showError(message) {
  const node = $('status-message');
  node.textContent = message;
  node.classList.add('error-text');
}
function setStep(step) {
  document.querySelectorAll('.step').forEach((el) => el.classList.toggle('active', Number(el.dataset.step) === step));
}
function renderImages(job) {
  const grid = $('image-grid');
  grid.replaceChildren();
  for (const image of job.images || []) {
    const card = document.createElement('figure');
    card.className = 'image-card';
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.src = `/api/jobs/${currentJob}/images/${encodeURIComponent(image.name)}`;
    img.alt = image.prompt;
    const caption = document.createElement('figcaption');
    caption.textContent = `${String(image.index + 1).padStart(2, '0')} · ${image.prompt}`;
    card.append(img, caption);
    grid.append(card);
  }
  $('render').disabled = !(job.status === 'ready' && job.images?.length);
}
async function poll() {
  if (!currentJob) return;
  try {
    const response = await fetch(`/api/jobs/${currentJob}`);
    const job = await response.json();
    $('progress-count').textContent = `${job.completed} / ${job.total}`;
    $('progress-bar').style.width = `${job.total ? (job.completed / job.total) * 100 : 0}%`;
    $('status-message').textContent = job.message || '';
    renderImages(job);
    if (job.status === 'generating') pollTimer = setTimeout(poll, 1200);
    else {
      $('progress-label').textContent = job.status === 'ready' ? 'Generación completada' : 'No se pudieron generar imágenes';
      if (job.errors?.length) $('status-message').textContent += ` ${job.errors.length} prompt(s) fallaron; revisa claves, cuotas y endpoint.`;
      if (job.status === 'ready') setStep(2);
    }
  } catch (error) {
    $('status-message').textContent = `Error consultando el proyecto: ${error.message}`;
  }
}
$('generate').addEventListener('click', async () => {
  clearTimeout(pollTimer);
  $('generate').disabled = true;
  $('status-message').classList.remove('error-text');
  $('status-message').textContent = '';
  $('progress').classList.remove('hidden');
  $('progress-label').textContent = 'Generando imágenes…';
  $('progress-count').textContent = '0 / 0';
  $('progress-bar').style.width = '0%';
  $('image-grid').replaceChildren();
  const body = new FormData();
  body.set('prompts', $('prompts').value);
  body.set('api_keys', $('keys').value);
  body.set('model', $('model').value);
  body.set('endpoint', $('endpoint').value);
  body.set('size', $('size').value);
  body.set('concurrency', $('concurrency').value);
  try {
    const response = await fetch('/api/jobs', { method: 'POST', body });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'No se pudo iniciar la generación.');
    currentJob = result.id;
    poll();
  } catch (error) {
    showError(error.message);
    $('generate').disabled = false;
  } finally {
    $('generate').disabled = false;
  }
});
$('render').addEventListener('click', async () => {
  if (!currentJob) return;
  const button = $('render');
  button.disabled = true;
  $('download').classList.add('hidden');
  $('render-status').textContent = 'Preparando narración y editando escenas… puede tardar varios minutos.';
  $('render-status').className = 'render-status';
  const body = new FormData();
  body.set('narration', $('narration').value);
  body.set('subtitles', $('subtitles').value);
  body.set('voice', $('voice').value);
  body.set('fps', $('fps').value);
  body.set('min_seconds', $('seconds').value);
  body.set('burn_subtitles', $('burn').checked ? 'true' : 'false');
  if ($('audio').files[0]) body.set('audio', $('audio').files[0]);
  try {
    const response = await fetch(`/api/jobs/${currentJob}/render`, { method: 'POST', body });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'No se pudo crear el video.');
    $('render-status').textContent = 'Video 1080p listo para descargar.';
    $('download').href = result.video;
    $('download').classList.remove('hidden');
    setStep(3);
  } catch (error) {
    $('render-status').textContent = error.message;
    $('render-status').classList.add('error-text');
  } finally {
    button.disabled = false;
  }
});
fetch('/api/health').then((r) => r.json()).then((h) => {
  if (!h.ffmpeg || !h.ffprobe) {
    $('render-status').textContent = 'Instala FFmpeg y ffprobe; deben estar disponibles en PATH.';
    $('render-status').classList.add('error-text');
  }
}).catch(() => {});
