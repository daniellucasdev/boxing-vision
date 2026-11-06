// Revisão rápida de golpes: cada golpe detectado em laço de ~1 s; o revisor dá o rótulo.
// Rótulos salvos no servidor a cada tecla (data/golpes_revisados/<luta>.json).

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const NOME = { jab: 'Jab', direto: 'Direto', cruzado_frente: 'Cruzado da frente', cruzado_tras: 'Cruzado de trás',
               gancho_frente: 'Gancho da frente', gancho_tras: 'Gancho de trás', finta: 'Finta',
               nao_golpe: 'Não é golpe', incerto: 'Não dá para ver' };
const BRACO = { L: 'esquerdo', R: 'direito' };
const ANTES = 0.6, DEPOIS = 0.5, VEL = 0.5;

const video = $('#video');
const S = { luta: null, golpes: [], fila: [], i: 0, pausado: false };

const atual = () => S.fila[S.i];

function flash(txt, cor) {
  const el = $('#hudFlash');
  el.textContent = txt; el.style.setProperty('--c', cor || 'var(--ok)');
  el.classList.add('ver');
  clearTimeout(flash.t); flash.t = setTimeout(() => el.classList.remove('ver'), 700);
}

function montarFila() {
  const cor = $('#selCor').value, rnd = $('#selRound').value, pend = $('#soPendentes').checked;
  const g0 = atual();
  S.fila = S.golpes.filter(g => (!cor || g.cor === cor) && (!rnd || String(g.round) === rnd)
                                && (!pend || !g.revisao || g === g0));
  S.i = Math.max(0, g0 ? S.fila.indexOf(g0) : 0);
  mostrar();
}

function mostrar() {
  const g = atual();
  $('#posicao').textContent = S.fila.length ? `${S.i + 1} / ${S.fila.length}` : '—';
  $$('#teclas .tecla').forEach(b => {
    b.classList.toggle('sugestao', !!g && b.dataset.r === g.auto);
    b.classList.toggle('escolhida', !!g && b.dataset.r === g.revisao);
  });
  if (!g) {
    $('#ficha').innerHTML = '<dd>Nada para revisar com esses filtros.</dd>';
    $('#hud').textContent = ''; video.pause(); desenhar(); progresso(); return;
  }
  $('#hud').innerHTML = `<span class="cor-${g.cor}">●</span> ${esc(g.atleta || g.cor)} · R${g.round}`;
  $('#ficha').innerHTML = `
    <dt>Atleta</dt><dd class="cor-${g.cor}">${esc(g.atleta || '—')} (${g.cor})</dd>
    <dt>Round</dt><dd>${g.round}</dd>
    <dt>Vídeo</dt><dd class="mono">${g.t.toFixed(2)} s</dd>
    <dt>Braço (detector)</dt><dd>${BRACO[g.braco]}</dd>
    <dt>Guarda</dt><dd>${g.guarda ? (g.guarda === 'L' ? 'ortodoxo (esq. à frente)' : 'canhoto (dir. à frente)') : 'indefinida'}</dd>
    <dt>Sugestão</dt><dd>${g.auto ? NOME[g.auto] : '<span class="muted">sem tipo</span>'}</dd>
    <dt>Revisão</dt><dd>${g.revisao ? NOME[g.revisao] : '<span class="muted">—</span>'}</dd>`;
  S.pausado = false;
  video.playbackRate = VEL;
  video.currentTime = Math.max(0, g.t - ANTES);
  video.play().catch(() => {});
  desenhar(); progresso();
}

function desenhar() {
  const cv = $('#cvSobre'), g = atual();
  const r = cv.getBoundingClientRect();
  cv.width = r.width * devicePixelRatio; cv.height = r.height * devicePixelRatio;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (!g || !g.caixa || !video.videoWidth) return;
  // vídeo em object-fit: contain → escala e margens
  const esc_ = Math.min(cv.width / video.videoWidth, cv.height / video.videoHeight);
  const ox = (cv.width - video.videoWidth * esc_) / 2, oy = (cv.height - video.videoHeight * esc_) / 2;
  const [x1, y1, x2, y2] = g.caixa.map((v, i) => v * esc_ + (i % 2 ? oy : ox));
  ctx.lineWidth = 2 * devicePixelRatio;
  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue(g.cor === 'Vermelho' ? '--vermelho' : '--azul');
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  ctx.font = `800 ${12 * devicePixelRatio}px ui-monospace, Menlo, monospace`;
  ctx.fillStyle = ctx.strokeStyle;
  ctx.fillText(`braço ${BRACO[g.braco]}`, x1 + 4, Math.max(14 * devicePixelRatio, y1 - 6));
}

function progresso() {
  const n = S.golpes.length, rev = S.golpes.filter(g => g.revisao);
  $('#nRevisados').textContent = `${rev.length} / ${n}`;
  $('#barra').style.width = `${n ? 100 * rev.length / n : 0}%`;
  const cont = {};
  rev.forEach(g => { cont[g.revisao] = (cont[g.revisao] || 0) + 1; });
  const conc = rev.filter(g => g.auto && g.auto === g.revisao).length;
  const comAuto = rev.filter(g => g.auto && NOME[g.revisao] && !['finta', 'nao_golpe', 'incerto'].includes(g.revisao)).length;
  $('#contagem').innerHTML = Object.keys(NOME).filter(k => cont[k]).map(k =>
    `<span>${NOME[k]}</span><b class="mono">${cont[k]}</b>`).join('') +
    (comAuto ? `<span class="muted">sugestão certa (golpes tipados)</span><b class="mono">${conc}/${comAuto}</b>` : '');
}

async function rotular(rotulo) {
  const g = atual();
  if (!g) return;
  const resp = await fetch(`/api/golpes/${encodeURIComponent(S.luta)}/${g.id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rotulo }) });
  if (!resp.ok) { flash('Erro ao salvar', 'var(--err)'); return; }
  g.revisao = rotulo;
  flash(rotulo ? NOME[rotulo] : 'Rótulo apagado', rotulo ? 'var(--ok)' : 'var(--err)');
  if (rotulo) avancar(1); else mostrar();
}

function avancar(d) {
  if (!S.fila.length) return;
  if ($('#soPendentes').checked && d > 0 && atual()?.revisao) {
    S.fila.splice(S.i, 1);            // revisado sai da fila; o próximo ocupa o lugar
    if (S.i >= S.fila.length) S.i = Math.max(0, S.fila.length - 1);
  } else {
    S.i = Math.min(S.fila.length - 1, Math.max(0, S.i + d));
  }
  mostrar();
}

video.addEventListener('timeupdate', () => {
  const g = atual();
  if (g && !S.pausado && video.currentTime > g.t + DEPOIS) video.currentTime = Math.max(0, g.t - ANTES);
});
video.addEventListener('loadedmetadata', desenhar);
window.addEventListener('resize', desenhar);

const TECLAS = {
  'ArrowLeft': () => avancar(-1), 'ArrowRight': () => avancar(1),
  ' ': () => { S.pausado = !S.pausado; S.pausado ? video.pause() : video.play(); },
  'Enter': () => { if (atual()?.auto) rotular(atual().auto); },
  'Backspace': () => rotular(null),
};
$$('#teclas .tecla[data-r]').forEach(b => { TECLAS[b.dataset.k] = () => rotular(b.dataset.r); });

document.addEventListener('keydown', (ev) => {
  if (ev.target.closest?.('input, select, textarea') || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const k = ev.key.length !== 1 ? ev.key
    : (ev.shiftKey && TECLAS[ev.key.toUpperCase()] && ev.key !== '?') ? ev.key.toUpperCase()
    : TECLAS[ev.key] ? ev.key : ev.key.toLowerCase();
  const f = TECLAS[k];
  if (!f) return;
  ev.preventDefault();
  if (ev.repeat && k !== 'ArrowLeft' && k !== 'ArrowRight') return;
  f();
});
$$('[data-k]').forEach(b => b.addEventListener('click', () => { TECLAS[b.dataset.k]?.(); b.blur(); }));
['#selCor', '#selRound', '#soPendentes'].forEach(s => $(s).addEventListener('change', montarFila));
$('#selLuta').addEventListener('change', () => carregar($('#selLuta').value));

async function carregar(nome) {
  const d = await (await fetch(`/api/golpes/${encodeURIComponent(nome)}`)).json();
  S.luta = nome; S.golpes = d.golpes; S.i = 0; S.fila = [];
  video.src = `/media/data/${d.video}`;
  montarFila();
}

(async () => {
  const lutas = await (await fetch('/api/golpes')).json();
  if (!lutas.length) { $('#semLutas').classList.remove('hidden'); $('#grade').classList.add('hidden'); return; }
  $('#selLuta').innerHTML = lutas.map(l =>
    `<option value="${esc(l.nome)}">${esc(l.nome)} (${l.revisados} revisados)</option>`).join('');
  carregar(lutas[0].nome);
})();
