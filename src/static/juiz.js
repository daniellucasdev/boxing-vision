// Modo juiz (E1) — anotação temporal de 1 atleta × 1 round.
//
// Marcas: {t, tipo: 'estado', estado, dir} | {t, tipo: 'acao', acao}, com t em segundos do vídeo.
// O resumo (linha da planilha v2.0, comparação com a base MHdS, avisos) é calculado no servidor
// (src/anotacao.py) a cada salvamento; aqui só desenhamos e registramos as marcas.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const NOME_ESTADO = { deslocamento: 'Deslocamento', ataque: 'Ataque', defesa: 'Defesa',
                      pausa: 'Pausa · clinch', fora: 'Fora · replay', fim: 'Fim do round' };
const ACOES = { golpe: 'ataque', finta: 'ataque', bloqueio: 'defesa', esquiva: 'defesa', guarda: 'defesa', defesa: 'defesa' };
const NOME_ACAO = { golpe: 'Golpe', finta: 'Finta', bloqueio: 'Bloqueio', esquiva: 'Esquiva', guarda: 'Guarda', defesa: 'Defesa (auto)' };
const LETRA_ACAO = { golpe: 'G', finta: 'F', bloqueio: 'B', esquiva: 'E', guarda: 'R', defesa: 'D' };
const SETA = { esq: '←', dir: '→', frente: '↑', tras: '↓' };
const NOME_DIR = { esq: 'esquerda', dir: 'direita', frente: 'frente', tras: 'trás' };
const VELOCIDADES = [0.125, 0.25, 0.5, 1];
const rotuloVel = (v) => `${String(v).replace('.', ',')}×`;
const PASSO_QUADRO = 1 / 30;  // vídeos de luta da base são 30 fps
const JANELA_DETALHE = 8;     // ± segundos na linha do tempo de detalhe
const DURACAO_ROUND = 180;

const CAMPOS = [
  ['atleta', 'Atleta'], ['pais', 'País'],
  ['cor', 'Cor', ['', 'Azul', 'Vermelho']], ['round', 'Round', ['', '1', '2', '3']],
  ['sexo', 'Sexo', ['', 'Masculino', 'Feminino']], ['categoria', 'Categoria'],
  ['competicao', 'Competição'], ['fase', 'Fase'],
  ['oponente', 'Oponente'], ['pais_oponente', 'País do oponente'],
  ['resultado', 'Resultado', ['', 'Vencedor', 'Perdedor']], ['anotador', 'Anotador'],
];

const css = getComputedStyle(document.documentElement);
const cor = (nome) => css.getPropertyValue(nome).trim();
const COR = {
  deslocamento: cor('--st-deslocamento'), ataque: cor('--st-ataque'), defesa: cor('--st-defesa'),
  pausa: cor('--st-pausa'), fora: cor('--st-fora'), fim: cor('--brand'),
};

const fmt = (s, casas = 3) => {
  if (s == null || !isFinite(s)) return '—';
  const m = Math.floor(s / 60), r = s - m * 60;
  return `${m}:${r.toFixed(casas).padStart(casas ? casas + 3 : 2, '0')}`;
};
const num = (x, casas = 1) => (x ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });

async function api(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
  const d = r.status === 204 ? null : await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((d && d.error) || `erro ${r.status}`);
  return d;
}

// =====================================================================================
// formulário de dados do atleta (cadastro e painel lateral) + busca na base MHdS
// =====================================================================================

function montarFormulario(el, meta, aoMudar) {
  el.innerHTML = `<div class="campos">${CAMPOS.map(([k, rotulo, opcoes]) => `
    <div class="campo"><label for="f_${el.id}_${k}">${rotulo}</label>
      ${opcoes
        ? `<select id="f_${el.id}_${k}" data-campo="${k}">${opcoes.map(o =>
            `<option value="${esc(o)}" ${String(meta[k] ?? '') === o ? 'selected' : ''}>${esc(o || '—')}</option>`).join('')}</select>`
        : `<input id="f_${el.id}_${k}" data-campo="${k}" value="${esc(meta[k])}" autocomplete="off">`}
    </div>`).join('')}</div>
    ${meta.base_chave ? `<div class="vinculo">Ligado à base: ${esc(meta.base_chave.split('|').join(' · '))}
      <button type="button" title="Desligar da base">✕</button></div>` : ''}`;
  $$('[data-campo]', el).forEach(inp => inp.addEventListener('input', () => {
    meta[inp.dataset.campo] = inp.value.trim();
    aoMudar();
  }));
  const desligar = $('.vinculo button', el);
  if (desligar) desligar.onclick = () => { meta.base_chave = ''; montarFormulario(el, meta, aoMudar); aoMudar(); };
}

function ligarBusca(inp, lista, aoEscolher) {
  if (!inp) return;
  let timer = null;
  inp.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = inp.value.trim();
      if (q.length < 2) { lista.innerHTML = ''; return; }
      const linhas = await api(`/api/base?q=${encodeURIComponent(q)}`).catch(() => []);
      // agrupa os rounds de cada atleta × luta
      const grupos = new Map();
      linhas.forEach(r => {
        const k = `${r.competicao}|${r.fase}|${r.atleta}|${r.oponente}`;
        if (!grupos.has(k)) grupos.set(k, []);
        grupos.get(k).push(r);
      });
      lista.innerHTML = grupos.size ? [...grupos.values()].map((rs, gi) => `
        <div class="resultado">
          <span class="pill ${esc(rs[0].cor)}">${esc(rs[0].cor)}</span>
          <span class="quem">${esc(rs[0].atleta)} <span class="muted">vs ${esc(rs[0].oponente)}</span></span>
          <span class="onde">${esc(rs[0].competicao)} · ${esc(rs[0].fase)} · ${esc(rs[0].categoria)} ${esc(rs[0].sexo)}</span>
          <span class="rounds">${rs.sort((a, b) => a.round - b.round).map((r, ri) =>
            `<button type="button" class="chip" data-g="${gi}" data-r="${ri}">R${r.round}</button>`).join('')}</span>
        </div>`).join('') : '<div class="nota">Nada encontrado na base.</div>';
      const vals = [...grupos.values()];
      $$('.chip', lista).forEach(b => b.onclick = () => {
        aoEscolher(vals[b.dataset.g][b.dataset.r]);
        lista.innerHTML = ''; inp.value = '';
      });
    }, 220);
  });
}

function metaDaBase(meta, r) {
  Object.assign(meta, {
    atleta: r.atleta, pais: r.pais, cor: r.cor, sexo: r.sexo, categoria: r.categoria,
    competicao: r.competicao, fase: r.fase, resultado: r.resultado, oponente: r.oponente,
    pais_oponente: r.pais_oponente, round: String(r.round), base_chave: r.chave,
  });
}

// =====================================================================================
// cadastro
// =====================================================================================

const C = { video: null, meta: {} };

function cardVideo(v) {
  return `<div class="card ${C.video === v.nome ? 'selecionado' : ''}" tabindex="0" data-video="${esc(v.nome)}">
    <div class="card-thumb">
      ${v.toca_no_navegador
        ? `<video data-thumb src="${esc(v.url)}" preload="metadata" muted playsinline></video>`
        : '<span class="card-selo alerta">formato não toca no navegador</span><div class="sem-video">⚠</div>'}
      <div class="card-titulo">${esc(v.nome)}<small>${v.mb} MB · ${esc(v.codec)}</small></div>
    </div></div>`;
}

function miniaturas(raiz) {
  $$('video[data-thumb]', raiz).forEach(v => v.addEventListener('loadedmetadata',
    () => { v.currentTime = Math.min(20, v.duration * 0.3); }, { once: true }));
}

async function renderVideos() {
  const videos = await api('/api/videos');
  const trilho = $('#trilhoVideos');
  trilho.innerHTML = videos.map(cardVideo).join('') +
    `<div class="card card-novo" tabindex="0" id="cardEnviar"><div><div class="mais">+</div>Enviar luta</div></div>`;
  miniaturas(trilho);
  $$('[data-video]', trilho).forEach(c => {
    const escolher = () => {
      C.video = c.dataset.video;
      $$('[data-video]', trilho).forEach(x => x.classList.toggle('selecionado', x === c));
      validarCadastro();
    };
    c.onclick = escolher;
    c.onkeydown = (e) => { if (e.key === 'Enter') escolher(); };
  });
  $('#cardEnviar').onclick = () => $('#arquivoLuta').click();
}

function enviarVideo(arquivo) {
  const fd = new FormData(); fd.append('video', arquivo);
  const xhr = new XMLHttpRequest();
  $('#envio').classList.remove('hidden');
  xhr.upload.onprogress = (e) => {
    if (!e.lengthComputable) return;
    const pct = Math.round(100 * e.loaded / e.total);
    $('#envioBarra').style.width = pct + '%'; $('#envioPct').textContent = pct + '%';
  };
  xhr.onload = () => {
    const d = JSON.parse(xhr.responseText || '{}');
    if (xhr.status >= 300) { $('#envioRotulo').textContent = 'Erro: ' + (d.error || xhr.status); return; }
    $('#envio').classList.add('hidden');
    C.video = d.nome; renderVideos(); validarCadastro();
  };
  xhr.onerror = () => { $('#envioRotulo').textContent = 'Erro de rede no envio'; };
  xhr.open('POST', '/api/videos'); xhr.send(fd);
}

async function renderAnotacoesSalvas() {
  const lista = await api('/api/anotacoes');
  if (!lista.length) return;
  $('#filaAnotacoes').classList.remove('hidden');
  const trilho = $('#trilhoAnotacoes');
  trilho.innerHTML = lista.map(a => `
    <a class="card" href="/juiz?id=${a.id}">
      <div class="card-thumb">
        <video data-thumb src="/media/data/${encodeURI(a.video)}" preload="metadata" muted playsinline></video>
        ${a.aberto ? '' : '<span class="card-selo">Concluído</span>'}
        <button class="card-acao" data-apagar="${a.id}" title="Apagar anotação">✕</button>
        <div class="card-titulo">${esc(a.meta.atleta || 'Sem nome')} · R${esc(a.meta.round || '?')}
          <small>${a.meta.oponente ? 'vs ' + esc(a.meta.oponente) + ' · ' : ''}${esc(a.meta.competicao || a.video)} · ${a.n_marcas} marcas</small></div>
        <div class="card-progresso"><div style="width:${Math.min(100, a.t_total / DURACAO_ROUND * 100)}%"></div></div>
      </div></a>`).join('');
  miniaturas(trilho);
  $$('[data-apagar]', trilho).forEach(b => b.onclick = async (e) => {
    e.preventDefault(); e.stopPropagation();
    if (!confirm('Apagar esta anotação? Não dá para desfazer.')) return;
    await api(`/api/anotacoes/${b.dataset.apagar}`, { method: 'DELETE' });
    b.closest('.card').remove();
  });
}

function validarCadastro() {
  const ok = C.video && C.meta.atleta && C.meta.round;
  $('#btnComecar').disabled = !ok;
  $('#cadastroDica').textContent = ok ? `${C.meta.atleta} · R${C.meta.round} em ${C.video}`
    : 'Escolha o vídeo e informe atleta e round.';
}

function iniciarCadastro() {
  $('#vCadastro').classList.remove('hidden');
  C.video = new URLSearchParams(location.search).get('video');
  renderVideos(); renderAnotacoesSalvas();
  const form = $('#formCadastro');
  montarFormulario(form, C.meta, validarCadastro);
  validarCadastro();
  ligarBusca($('#buscaBase'), $('#resultadosBase'), (r) => {
    metaDaBase(C.meta, r); montarFormulario(form, C.meta, validarCadastro); validarCadastro();
  });
  $('#arquivoLuta').onchange = (e) => { if (e.target.files[0]) enviarVideo(e.target.files[0]); };
  $('#btnComecar').onclick = async () => {
    $('#btnComecar').disabled = true;
    try {
      const d = await api('/api/anotacoes', { method: 'POST', body: JSON.stringify({ video: C.video, meta: C.meta, marcas: [] }) });
      location.href = `/juiz?id=${d.id}`;
    } catch (e) { $('#cadastroDica').textContent = 'Erro: ' + e.message; $('#btnComecar').disabled = false; }
  };
}

// =====================================================================================
// anotação
// =====================================================================================

const S = {
  doc: null,        // {id, meta, video, marcas}
  res: null,        // resposta do servidor: resumo, base, comparacao
  desfazer: [],     // nº de marcas inseridas por comando (ação + troca automática de estado = 2)
  versao: 0, cache: null,
  salvando: false, pendente: false, sujo: false, timer: null,
  vel: 0.125, ultimoEstadoHud: null,
};
const video = $('#video');

const agora = () => Math.round(video.currentTime * 1000) / 1000;

function ordenado() {
  // estados ordenados por tempo (estável: no mesmo instante vale o último inserido)
  if (S.cache && S.cache.versao === S.versao) return S.cache;
  const marcas = S.doc.marcas;
  const est = marcas.map((m, i) => ({ ...m, i })).filter(m => m.tipo === 'estado')
    .sort((a, b) => a.t - b.t || a.i - b.i);
  const ultimo = marcas.reduce((mx, m) => Math.max(mx, m.t), 0);
  const fim = est.find(m => m.estado === 'fim');
  S.cache = { versao: S.versao, est, ultimo, fim };
  return S.cache;
}

function segmentos(tAgora) {
  const { est, ultimo } = ordenado();
  const segs = [];
  for (let k = 0; k < est.length; k++) {
    const m = est[k];
    if (m.estado === 'fim') break;
    const fim = k + 1 < est.length ? est[k + 1].t : Math.max(ultimo, tAgora ?? 0);
    if (fim > m.t) segs.push({ ini: m.t, fim, estado: m.estado, dir: m.dir });
  }
  return segs;
}

function estadoEm(t) {
  const { est } = ordenado();
  let atual = null;
  for (const m of est) {
    if (m.t > t) break;
    atual = m;
    if (m.estado === 'fim') break;
  }
  return atual;
}

function relogioRound(t) {
  return segmentos(t).reduce((s, g) => g.estado !== 'fora' && g.ini < t ? s + Math.min(g.fim, t) - g.ini : s, 0);
}

// ---------- comandos ----------

function flash(texto, c) {
  const el = $('#hudFlash');
  el.textContent = texto; el.style.setProperty('--c', c || 'var(--line-strong)');
  el.classList.add('ver');
  clearTimeout(flash.t); flash.t = setTimeout(() => el.classList.remove('ver'), 900);
}

function adicionar(novas) {
  S.doc.marcas.push(...novas);
  S.desfazer.push(novas.length);
  mudou();
}

function bloqueadoPeloFim(t) {
  const { fim } = ordenado();
  if (fim && t >= fim.t) { flash(`Round encerrado em ${fmt(fim.t, 1)} — apague o fim para continuar`, COR.fim); return true; }
  return false;
}

function marcarEstado(estado, dir = null) {
  const t = agora();
  if (bloqueadoPeloFim(t)) return;
  if (estado === 'fim' && ordenado().fim) { flash('O fim já está marcado — apague-o na lista para mudar', COR.fim); return; }
  const atual = estadoEm(t);
  if (atual && atual.estado === estado && (atual.dir ?? null) === dir) {
    flash(`Já em ${NOME_ESTADO[estado]}${dir ? ' ' + SETA[dir] : ''}`, COR[estado]); return;
  }
  adicionar([{ t, tipo: 'estado', estado, dir }]);
  flash(`${NOME_ESTADO[estado]}${dir ? ' ' + SETA[dir] + ' ' + NOME_DIR[dir] : ''}`, COR[estado]);
}

function marcarAcao(acao) {
  const t = agora();
  if (bloqueadoPeloFim(t)) return;
  const grupo = ACOES[acao], atual = estadoEm(t), novas = [];
  // atacar se deslocando conta como ataque: a ação abre o estado certo se preciso
  if (!atual || atual.estado !== grupo) novas.push({ t, tipo: 'estado', estado: grupo, dir: null });
  novas.push({ t, tipo: 'acao', acao });
  adicionar(novas);
  flash(`+ ${NOME_ACAO[acao]}`, COR[grupo]);
}

function desfazer() {
  if (!S.doc.marcas.length) return;
  const n = Math.min(S.desfazer.pop() ?? 1, S.doc.marcas.length);
  const removidas = S.doc.marcas.splice(-n, n);
  mudou();
  flash(`Desfeito: ${removidas.map(descrever).join(' + ')}`, cor('--err'));
}

function remover(i) {
  S.doc.marcas.splice(i, 1);
  S.desfazer = [];  // índices mudaram; desfazer volta a remover 1 marca por vez
  mudou();
}

function descrever(m) {
  return m.tipo === 'acao' ? NOME_ACAO[m.acao] : NOME_ESTADO[m.estado] + (m.dir ? ' ' + SETA[m.dir] : '');
}

function tocarPausar() { video.paused ? video.play() : video.pause(); }
function pular(dt) { video.currentTime = Math.max(0, Math.min(video.duration || 0, video.currentTime + dt)); }
function quadro(sinal) { video.pause(); pular(sinal * PASSO_QUADRO); }
function velocidade(v) {
  S.vel = v; video.playbackRate = v; video.defaultPlaybackRate = v;
  $('#hudVel').textContent = rotuloVel(v);
  $$('#velocidades .chip').forEach(c => c.classList.toggle('ativo', Number(c.dataset.v) === v));
}
function mudarVelocidade(passo) {
  const i = VELOCIDADES.indexOf(S.vel) + passo;
  if (i >= 0 && i < VELOCIDADES.length) velocidade(VELOCIDADES[i]);
}

const TECLAS = {
  '1': () => marcarEstado('deslocamento'),
  'ArrowLeft': () => marcarEstado('deslocamento', 'esq'),
  'ArrowRight': () => marcarEstado('deslocamento', 'dir'),
  'ArrowUp': () => marcarEstado('deslocamento', 'frente'),
  'ArrowDown': () => marcarEstado('deslocamento', 'tras'),
  '2': () => marcarEstado('ataque'),
  '3': () => marcarEstado('defesa'),
  '4': () => marcarEstado('pausa'),
  '0': () => marcarEstado('fora'),
  'Enter': () => marcarEstado('fim'),
  'g': () => marcarAcao('golpe'), 'f': () => marcarAcao('finta'),
  'b': () => marcarAcao('bloqueio'), 'e': () => marcarAcao('esquiva'), 'r': () => marcarAcao('guarda'),
  'Backspace': desfazer,
  ' ': tocarPausar,
  'z': () => pular(-2), 'x': () => pular(2),
  ',': () => quadro(-1), '.': () => quadro(1),
  '[': () => mudarVelocidade(-1), ']': () => mudarVelocidade(1),
};
const REPETIVEIS = new Set(['z', 'x', ',', '.']);

function pressionar(k) {
  const b = $(`.tecla[data-k="${CSS.escape(k)}"]`);
  if (!b) return;
  b.classList.add('pressionada'); setTimeout(() => b.classList.remove('pressionada'), 140);
}

document.addEventListener('keydown', (ev) => {
  if (!S.doc || ev.target.closest?.('input, select, textarea')) return;
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'z') { ev.preventDefault(); desfazer(); return; }
  if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const k = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
  const acao = TECLAS[k];
  if (!acao) return;
  ev.preventDefault();
  if (ev.repeat && !REPETIVEIS.has(k)) return;
  acao(); pressionar(k);
});

// ---------- salvamento ----------

function status(texto, classe = '') {
  const el = $('#statusSalvo');
  el.textContent = texto; el.className = 'status-salvo ' + classe;
}

function mudou() {
  S.versao++; S.sujo = true;
  renderMarcas(); atualizarTitulo();
  status('Salvando…');
  clearTimeout(S.timer); S.timer = setTimeout(salvar, 400);
}

const corpoSalvar = () => JSON.stringify({ meta: S.doc.meta, marcas: S.doc.marcas });

async function salvar() {
  if (S.salvando) { S.pendente = true; return; }
  S.salvando = true;
  const versao = S.versao;
  try {
    S.res = await api(`/api/anotacoes/${S.doc.id}`, { method: 'PUT', body: corpoSalvar() });
    if (versao === S.versao) { S.sujo = false; status('Salvo ✓', 'ok'); }
    renderLateral();
  } catch (e) {
    status('Erro ao salvar: ' + e.message, 'erro');
  } finally {
    S.salvando = false;
    if (S.pendente) { S.pendente = false; salvar(); }
  }
}

// salva o que faltar ao fechar a aba (keepalive sobrevive à navegação)
window.addEventListener('pagehide', () => {
  if (S.doc && S.sujo) fetch(`/api/anotacoes/${S.doc.id}`,
    { method: 'PUT', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: corpoSalvar() });
});

// ---------- render: lista de marcas e painel lateral ----------

function renderMarcas() {
  const marcas = S.doc.marcas.map((m, i) => ({ ...m, i })).sort((a, b) => a.t - b.t || a.i - b.i);
  $('#nMarcas').textContent = `· ${marcas.length}`;
  const segs = segmentos();
  const relogio = (t) => segs.reduce((s, g) => g.estado !== 'fora' && g.ini < t ? s + Math.min(g.fim, t) - g.ini : s, 0);
  $('#corpoMarcas').innerHTML = marcas.length ? marcas.map(m => {
    const c = m.tipo === 'acao' ? COR[ACOES[m.acao]] : COR[m.estado];
    return `<tr class="clicavel" data-t="${m.t}">
      <td class="mono">${fmt(m.t)}</td><td class="mono muted">${fmt(relogio(m.t), 1)}</td>
      <td><span class="marca-tipo ${m.tipo}" style="--c:${c}">${esc(descrever(m))}</span></td>
      <td class="num"><button class="apagar" data-i="${m.i}" title="Apagar marca">✕</button></td></tr>`;
  }).join('') : '<tr><td colspan="4" class="muted">Nenhuma marca ainda. Dê play e marque o início do round com 1–4 ou as setas.</td></tr>';
  $$('#corpoMarcas tr[data-t]').forEach(tr => tr.onclick = (e) => {
    if (e.target.closest('.apagar')) return;
    video.currentTime = Number(tr.dataset.t);
  });
  $$('#corpoMarcas .apagar').forEach(b => b.onclick = () => remover(Number(b.dataset.i)));
}

function renderLateral() {
  const r = S.res.resumo;
  const totalOk = r.t_total >= 175 && r.t_total <= 185;
  const linha = (estado, nome, t, n, rotuloN) => `
    <div class="linha-estado" style="--c:${COR[estado]}">
      <span class="ponto"></span><span>${nome}</span>
      <span class="t">${num(t)} s</span><span class="n" title="${rotuloN}">${n}</span>
      <div class="barra"><div style="width:${Math.min(100, t / DURACAO_ROUND * 100)}%"></div></div>
    </div>`;
  $('#pResumo').innerHTML = `
    <h3>Resumo do round <span class="resumo-total ${r.aberto ? '' : totalOk ? 'ok' : 'fora'}">${num(r.t_total)} / ${DURACAO_ROUND} s</span></h3>
    ${linha('deslocamento', 'Deslocamento', r.t_deslocamento, r.n_deslocamento, 'trechos')}
    ${linha('ataque', 'Ataque', r.t_ataque, r.n_ataque, 'golpes + fintas')}
    ${linha('defesa', 'Defesa', r.t_defesa, r.n_defesa, 'bloqueios + esquivas + guarda')}
    ${linha('pausa', 'Pausa · clinch', r.t_pausa, r.n_pausa, 'trechos')}
    <div class="sub-resumo">
      <span>Golpes <b>${r.n_golpes}</b></span><span>Fintas <b>${r.n_fintas}</b></span>
      <span>Sequências <b>${r.n_sequencias_ataque}</b></span>
      <span>Bloqueios <b>${r.n_bloqueios}</b></span><span>Esquivas <b>${r.n_esquivas}</b></span>
      <span>Guarda <b>${r.n_guarda}</b></span>
      ${r.n_defesa_sem_tipo ? `<span>Defesa sem tipo <b>${r.n_defesa_sem_tipo}</b></span>` : ''}
      ${r.t_fora ? `<span>Fora <b>${num(r.t_fora)} s</b></span>` : ''}
    </div>
    <div class="direcoes">${['esq', 'dir', 'frente', 'tras'].map(d => `
      <div title="Deslocamento para ${NOME_DIR[d]} (ponto de vista do atleta)">
        <div class="seta">${SETA[d]}</div><div class="v">${num(r['t_desl_' + d])} s</div>
        <div class="q">${r['n_desl_' + d]}× ${NOME_DIR[d]}</div></div>`).join('')}
    </div>
    ${r.t_desl_sem_dir ? `<p class="nota">${num(r.t_desl_sem_dir)} s de deslocamento sem direção marcada.</p>` : ''}`;

  const cmp = S.res.comparacao;
  const nomes = { t_deslocamento: 'Deslocamento', t_ataque: 'Ataque', t_defesa: 'Defesa', t_pausa: 'Pausa + clinch',
                  t_total: 'Total', n_deslocamento: 'nº deslocamentos', n_ataque: 'nº ataque',
                  n_defesa: 'nº defesa', n_pausa: 'nº pausas + clinches' };
  const classeDelta = (c) => {
    const rel = Math.abs(c.diferenca) / Math.max(Math.abs(c.base), 1);
    return rel <= 0.1 ? 'bom' : rel <= 0.25 ? 'medio' : 'ruim';
  };
  $('#pComparacao').innerHTML = cmp ? `
    <h3>Comparação com a v1.0</h3>
    <table class="tabela">
      <thead><tr><th></th><th class="num">Anotado</th><th class="num">Base</th><th class="num">Δ</th></tr></thead>
      <tbody>${cmp.map(c => `<tr>
        <td>${nomes[c.campo]}</td><td class="num">${c.campo.startsWith('t_') ? num(c.anotado) : c.anotado}</td>
        <td class="num">${c.campo.startsWith('t_') ? num(c.base) : c.base}</td>
        <td class="num delta ${classeDelta(c)}">${c.diferenca > 0 ? '+' : ''}${c.campo.startsWith('t_') ? num(c.diferenca) : c.diferenca}</td>
      </tr>`).join('')}</tbody>
    </table>
    <p class="nota">Base MHdS com o clinch somado à pausa (regra da v2.0). Verde ≤ 10%, amarelo ≤ 25%.</p>` : `
    <h3>Comparação com a v1.0</h3>
    <p class="nota" style="margin:0">Ligue esta anotação a uma linha da base em <b>Dados do atleta</b>
      para comparar com a planilha original.</p>`;

  $('#pAvisos').innerHTML = `<h3>Avisos</h3><div class="avisos">${
    r.avisos.length ? r.avisos.map(a => `<div>${esc(a)}</div>`).join('') : '<div class="tudo-ok">Nenhum aviso ✓</div>'}</div>`;
}

function atualizarTitulo() {
  const m = S.doc.meta;
  $('#tituloAnotacao').innerHTML = `${esc(m.atleta || 'Sem nome')} <span class="muted">· Round ${esc(m.round || '?')}</span>`;
  $('#subtituloAnotacao').innerHTML = [
    m.cor && `<span class="pill ${esc(m.cor)}">${esc(m.cor)}</span>`,
    m.oponente && `vs ${esc(m.oponente)}`, m.competicao && esc(m.competicao), m.fase && esc(m.fase),
    m.categoria && esc(m.categoria), esc(S.doc.video),
  ].filter(Boolean).join(' · ');
  document.title = `${m.atleta || 'Anotação'} R${m.round || '?'} — Modo juiz`;
}

// ---------- linhas do tempo (canvas) ----------

let hachura = null;
function padraoFora(ctx) {
  if (hachura) return hachura;
  const p = document.createElement('canvas'); p.width = p.height = 8;
  const c = p.getContext('2d');
  c.fillStyle = COR.fora; c.fillRect(0, 0, 8, 8);
  c.strokeStyle = '#3a4566'; c.lineWidth = 2;
  c.beginPath(); c.moveTo(-2, 10); c.lineTo(10, -2); c.stroke();
  hachura = ctx.createPattern(p, 'repeat');
  return hachura;
}

function preparar(cv) {
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, w, h];
}

function desenhar(cv, ini, fim, detalhe) {
  const [ctx, W, H] = preparar(cv);
  const t = video.currentTime;
  const x = (s) => (s - ini) / (fim - ini) * W;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = cor('--surface'); ctx.fillRect(0, 0, W, H);

  if (detalhe) {  // grade de 1 s
    ctx.fillStyle = 'rgba(150,175,230,.10)';
    for (let s = Math.ceil(ini); s <= fim; s++) ctx.fillRect(Math.round(x(s)), 0, 1, H);
  }
  const y0 = detalhe ? 22 : 5, hh = H - y0 - (detalhe ? 8 : 5);
  for (const g of segmentos(t)) {
    if (g.fim < ini || g.ini > fim) continue;
    const a = Math.max(0, x(g.ini)), b = Math.min(W, x(g.fim));
    ctx.fillStyle = g.estado === 'fora' ? padraoFora(ctx) : COR[g.estado];
    ctx.globalAlpha = g.estado === 'fora' ? 1 : 0.85;
    ctx.fillRect(a, y0, Math.max(1, b - a), hh);
    ctx.globalAlpha = 1;
    if (detalhe && g.dir && b - a > 22) {
      ctx.fillStyle = '#05080f'; ctx.font = '800 15px system-ui';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(SETA[g.dir], (a + b) / 2, y0 + hh / 2);
    }
  }
  // fim do round
  const { fim: marcaFim } = ordenado();
  if (marcaFim && marcaFim.t >= ini && marcaFim.t <= fim) {
    ctx.fillStyle = COR.fim; ctx.fillRect(x(marcaFim.t) - 1, 0, 3, H);
  }
  // ações
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.font = '800 11px ui-monospace, Menlo, monospace';
  for (const m of S.doc.marcas) {
    if (m.tipo !== 'acao' || m.t < ini || m.t > fim) continue;
    const px = x(m.t);
    ctx.fillStyle = '#fff';
    ctx.fillRect(Math.round(px), y0 - (detalhe ? 4 : 0), detalhe ? 2 : 1, hh + (detalhe ? 4 : 0));
    if (detalhe) { ctx.fillStyle = COR[ACOES[m.acao]]; ctx.fillText(LETRA_ACAO[m.acao], px, 4); }
  }
  // cabeça de leitura
  const px = x(t);
  ctx.fillStyle = cor('--brand-hi');
  ctx.fillRect(Math.round(px) - 1, 0, 2, H);
  if (detalhe) {
    ctx.beginPath(); ctx.moveTo(px - 6, 0); ctx.lineTo(px + 6, 0); ctx.lineTo(px, 7); ctx.closePath(); ctx.fill();
  }
}

function navegarPorCanvas(cv, janela) {
  const irPara = (ev) => {
    const r = cv.getBoundingClientRect();
    const [ini, fim] = janela();
    video.currentTime = Math.max(0, Math.min(video.duration || 0, ini + (ev.clientX - r.left) / r.width * (fim - ini)));
  };
  cv.addEventListener('pointerdown', (ev) => {
    cv.setPointerCapture(ev.pointerId); irPara(ev);
    const mover = (e) => irPara(e);
    cv.addEventListener('pointermove', mover);
    cv.addEventListener('pointerup', () => cv.removeEventListener('pointermove', mover), { once: true });
  });
}

const janelaDetalhe = () => [video.currentTime - JANELA_DETALHE, video.currentTime + JANELA_DETALHE];
const janelaGeral = () => [0, video.duration || Math.max(60, ordenado().ultimo + 10)];

function quadroAnimacao() {
  if (S.doc) {
    const t = video.currentTime;
    $('#tempoVideo').textContent = fmt(t);
    const inicio = ordenado().est[0];
    $('#tempoRound').textContent = inicio && t >= inicio.t ? fmt(relogioRound(t), 1) : '—';
    $('#btnTocar').textContent = video.paused ? '▶' : '❚❚';

    const atual = estadoEm(t);
    const chave = atual ? `${atual.estado}|${atual.dir}` : '';
    if (chave !== S.ultimoEstadoHud) {
      S.ultimoEstadoHud = chave;
      const hud = $('#hudEstado');
      if (!atual) {
        hud.style.setProperty('--c', cor('--dim'));
        hud.innerHTML = 'Antes do round <small>marque o início com 1–4 ou as setas</small>';
      } else {
        hud.style.setProperty('--c', COR[atual.estado]);
        hud.innerHTML = `${atual.dir ? `<span class="seta">${SETA[atual.dir]}</span>` : ''}${NOME_ESTADO[atual.estado]}`;
      }
      $$('.tecla[data-estado]').forEach(b => b.classList.toggle('ativa', !!atual &&
        b.dataset.estado === atual.estado && (b.dataset.dir || null) === (atual.dir ?? null)));
    }
    desenhar($('#cvDetalhe'), ...janelaDetalhe(), true);
    desenhar($('#cvGeral'), ...janelaGeral(), false);
  }
  requestAnimationFrame(quadroAnimacao);
}

async function iniciarAnotacao(id) {
  $('#vAnotacao').classList.remove('hidden');
  try {
    S.res = await api(`/api/anotacoes/${id}`);
  } catch (e) {
    $('#vAnotacao').innerHTML = `<p class="erro">Não foi possível abrir a anotação: ${esc(e.message)}. <a href="/juiz">Voltar</a></p>`;
    return;
  }
  S.doc = { id: S.res.id, meta: S.res.meta, video: S.res.video, marcas: S.res.marcas };
  atualizarTitulo(); renderMarcas(); renderLateral();
  status('Salvo ✓', 'ok');

  video.src = `/media/data/${encodeURI(S.doc.video)}`;
  video.addEventListener('loadedmetadata', () => velocidade(S.vel), { once: true });
  video.addEventListener('error', () => $('#avisoCodec').classList.remove('hidden'));
  $('#velocidades').innerHTML = VELOCIDADES.map(v =>
    `<button class="chip" data-v="${v}">${rotuloVel(v)}</button>`).join('');
  $$('#velocidades .chip').forEach(c => c.onclick = () => velocidade(Number(c.dataset.v)));
  velocidade(S.vel);

  $$('[data-k]').forEach(b => b.addEventListener('click', () => { TECLAS[b.dataset.k](); b.blur(); }));
  navegarPorCanvas($('#cvDetalhe'), janelaDetalhe);
  navegarPorCanvas($('#cvGeral'), janelaGeral);

  const salvarMeta = () => { atualizarTitulo(); S.sujo = true; status('Salvando…'); clearTimeout(S.timer); S.timer = setTimeout(salvar, 400); };
  const form = $('#formAnotacao');
  montarFormulario(form, S.doc.meta, salvarMeta);
  ligarBusca($('#buscaBase2'), $('#resultadosBase2'), (r) => {
    metaDaBase(S.doc.meta, r); montarFormulario(form, S.doc.meta, salvarMeta); salvarMeta();
  });
  if (!S.doc.meta.atleta) $('#pDados').open = true;

  $('#exportar').innerHTML = [
    ['linha', 'Linha da planilha'], ['intervalos', 'Intervalos'], ['acoes', 'Ações'],
  ].map(([tipo, rotulo]) => `<a class="btn btn-fantasma btn-sm" href="/api/anotacoes/${S.doc.id}/${tipo}.csv">${rotulo} · CSV</a>`).join('')
    + `<a class="btn btn-fantasma btn-sm" href="/api/planilha.csv">Planilha completa</a>`;

  requestAnimationFrame(quadroAnimacao);
}

// =====================================================================================

const idAnotacao = new URLSearchParams(location.search).get('id');
if (idAnotacao) iniciarAnotacao(idAnotacao); else iniciarCadastro();
