const pages = { chat: renderChat, documents: renderDocuments, admin: renderAdmin };
let currentPage = 'chat';

function navigate(page) {
  currentPage = page;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  const titles = { chat: 'AI Chat / Beszélgetés', documents: 'Dokumentumok / Documents', admin: 'Admin Dashboard' };
  document.getElementById('page-title').textContent = titles[page] || page;
  pages[page]();
}

function renderChat() {
  const el = document.getElementById('content');
  el.innerHTML = `
    <div class="chat-container">
      <div class="chat-messages" id="chat-messages">
        <div class="message assistant">
          <div class="msg-avatar">💎</div>
          <div class="msg-body">
            <div class="msg-text">Üdvözlöm! I'm DAIMOND AI. Upload documents and ask me questions about them. I'll find the relevant information and cite my sources.\n\nTöltsön fel dokumentumokat és kérdezzen róluk!</div>
          </div>
        </div>
      </div>
      <div class="chat-input-area">
        <div class="chat-input-wrap">
          <textarea class="chat-input" id="chat-input" placeholder="Kérdezzen... / Ask a question..." rows="1"></textarea>
          <button class="btn-send" id="btn-send" onclick="sendChat()">➤</button>
        </div>
      </div>
    </div>`;
  const input = document.getElementById('chat-input');
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); } });
  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = input.scrollHeight + 'px'; });
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  input.style.height = 'auto';
  const msgs = document.getElementById('chat-messages');
  msgs.innerHTML += `<div class="message user"><div class="msg-avatar">👤</div><div class="msg-body"><div class="msg-text">${esc(q)}</div></div></div>`;
  msgs.innerHTML += `<div class="message assistant" id="typing"><div class="msg-avatar">💎</div><div class="msg-body"><div class="typing"><span></span><span></span><span></span></div></div></div>`;
  msgs.scrollTop = msgs.scrollHeight;
  document.getElementById('btn-send').disabled = true;
  try {
    const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q }) });
    const data = await res.json();
    document.getElementById('typing').remove();
    let srcHtml = '';
    if (data.sources && data.sources.length) {
      srcHtml = `<div class="msg-sources">📎 Források / Sources: ${data.sources.map(s => `<span>${esc(s)}</span>`).join(', ')}</div>`;
    }
    msgs.innerHTML += `<div class="message assistant"><div class="msg-avatar">💎</div><div class="msg-body"><div class="msg-text">${esc(data.answer)}</div>${srcHtml}</div></div>`;
  } catch (e) {
    document.getElementById('typing')?.remove();
    msgs.innerHTML += `<div class="message assistant"><div class="msg-avatar">💎</div><div class="msg-body"><div class="msg-text" style="color:var(--error)">Error: ${esc(e.message)}</div></div></div>`;
  }
  document.getElementById('btn-send').disabled = false;
  msgs.scrollTop = msgs.scrollHeight;
}

function renderDocuments() {
  const el = document.getElementById('content');
  el.innerHTML = `
    <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-input').click()">
      <div class="icon">📄</div>
      <p>Kattintson vagy húzza ide a fájlokat / Click or drag files here</p>
      <small>PDF, TXT, DOCX — max 50MB</small>
      <input type="file" id="file-input" accept=".pdf,.txt,.docx" multiple hidden>
    </div>
    <div id="doc-list"><div class="empty-state"><div class="icon">📂</div><p>Loading...</p></div></div>`;
  const zone = document.getElementById('upload-zone');
  const fi = document.getElementById('file-input');
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('dragover'); uploadFiles(e.dataTransfer.files); });
  fi.addEventListener('change', () => { uploadFiles(fi.files); fi.value = ''; });
  loadDocuments();
}

async function uploadFiles(files) {
  for (const file of files) {
    const fd = new FormData();
    fd.append('file', file);
    try {
      await fetch('/api/upload', { method: 'POST', body: fd });
    } catch (e) { alert('Upload failed: ' + e.message); }
  }
  setTimeout(loadDocuments, 500);
}

async function loadDocuments() {
  try {
    const res = await fetch('/api/documents');
    const docs = await res.json();
    const el = document.getElementById('doc-list');
    if (!docs.length) {
      el.innerHTML = '<div class="empty-state"><div class="icon">📂</div><p>Nincsenek dokumentumok / No documents yet</p></div>';
      return;
    }
    el.innerHTML = `<table class="doc-table"><thead><tr><th>Név / Name</th><th>Típus</th><th>Méret</th><th>Chunk</th><th>Státusz</th><th></th></tr></thead><tbody>
      ${docs.map(d => `<tr><td>${esc(d.filename)}</td><td>${d.file_type.toUpperCase()}</td><td>${formatSize(d.file_size)}</td><td>${d.chunk_count}</td><td><span class="badge badge-${d.status}">${d.status}</span></td><td><button class="btn-delete" onclick="deleteDoc(${d.id})">✕</button></td></tr>`).join('')}
    </tbody></table>`;
  } catch (e) {
    document.getElementById('doc-list').innerHTML = `<p style="color:var(--error)">Error loading documents</p>`;
  }
}

async function deleteDoc(id) {
  if (!confirm('Törlés / Delete this document?')) return;
  await fetch('/api/documents/' + id, { method: 'DELETE' });
  loadDocuments();
}

async function renderAdmin() {
  const el = document.getElementById('content');
  el.innerHTML = '<div class="empty-state"><p>Loading...</p></div>';
  try {
    const res = await fetch('/api/stats');
    const stats = await res.json();
    el.innerHTML = `
      <div class="stats-grid">
        <div class="stat-card"><div class="label">Dokumentumok / Documents</div><div class="value">${stats.document_count}</div></div>
        <div class="stat-card"><div class="label">Szövegblokkok / Chunks</div><div class="value">${stats.chunk_count}</div></div>
        <div class="stat-card"><div class="label">Lekérdezések / Queries</div><div class="value">${stats.recent_queries.length}</div></div>
      </div>
      <h3 style="margin-bottom:16px">Legutóbbi kérdések / Recent Queries</h3>
      <div class="queries-list">
        ${stats.recent_queries.length ? stats.recent_queries.map(q => `<div class="query-item"><div class="q">❓ ${esc(q.question)}</div><div class="a">${esc(q.answer)}</div><div class="time">${q.created_at}</div></div>`).join('') : '<div class="empty-state"><p>Még nincsenek kérdések / No queries yet</p></div>'}
      </div>`;
  } catch (e) {
    el.innerHTML = `<p style="color:var(--error)">Error: ${esc(e.message)}</p>`;
  }
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function formatSize(b) { if (!b) return '-'; if (b < 1024) return b + ' B'; if (b < 1048576) return (b/1024).toFixed(1) + ' KB'; return (b/1048576).toFixed(1) + ' MB'; }

document.addEventListener('DOMContentLoaded', () => navigate('chat'));
