// Gurt Client Application Controller
// Live real-time operations interface with Human-in-the-Loop workflows

const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const approvalCountBadge = document.getElementById('approval-count');
const tasksCountBadge = document.getElementById('tasks-count');
const speakersCountBadge = document.getElementById('speakers-count');
const vendorsCountBadge = document.getElementById('vendors-count');
const sponsorsCountBadge = document.getElementById('sponsors-count');

let conversationHistory = [];
let activeEventBrief = {};
let allActionProposals = [];

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const tabName = btn.getAttribute('data-tab');
    const pane = document.getElementById(`pane-${tabName}`);
    if (pane) pane.classList.add('active');
  });
});

// Quick prompt click
function sendQuickPrompt(text) {
  userInput.value = text;
  submitMessage();
}

function clearHistory() {
  conversationHistory = [];
  chatMessages.innerHTML = `
    <div class="message assistant">
      <div class="msg-avatar">🧃</div>
      <div class="msg-body">
        <p><strong>Chat history cleared.</strong> I'm ready to organize! What would you like to review or coordinate?</p>
      </div>
    </div>
  `;
}

// Chat Form submit
chatForm.addEventListener('submit', (e) => {
  e.preventDefault();
  submitMessage();
});

async function submitMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  // Add User Message to UI
  appendMessage('user', text);
  userInput.value = '';
  sendBtn.disabled = true;

  // Temporary typing indicator
  const typingId = appendTypingIndicator();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: conversationHistory })
    });

    const data = await res.json();
    removeMessage(typingId);

    if (data.text) {
      appendMessage('assistant', data.text, data.tool_calls, data.model_used);
      conversationHistory.push({ role: 'user', content: text });
      conversationHistory.push({ role: 'assistant', content: data.text });
      if (conversationHistory.length > 8) conversationHistory = conversationHistory.slice(-8);

      if (data.model_used) {
        const badge = document.getElementById('model-badge');
        if (badge) {
          badge.textContent = data.model_used.includes('gemini') ? 'Gemini 3 Flash • Online' : 'Gurt Engine • Online';
        }
      }
    } else {
      appendMessage('assistant', 'Sorry, I ran into an issue processing that turn.');
    }

    // Refresh Ops Board & Overview Stats
    loadAllRecords();

  } catch (err) {
    removeMessage(typingId);
    appendMessage('assistant', `⚠️ **Connection Error:** Could not reach Gurt backend (${err.message}).`);
  } finally {
    sendBtn.disabled = false;
  }
}

function appendMessage(role, text, toolCalls = [], modelUsed = null) {
  const msgEl = document.createElement('div');
  msgEl.className = `message ${role}`;
  const avatar = role === 'user' ? '👤' : '🧃';

  let toolTags = '';
  if (toolCalls && toolCalls.length > 0) {
    toolTags = toolCalls.map(tc => `<div class="tool-tag">⚡ ${tc.tool}()</div>`).join(' ');
  }

  // Markdown rendering
  let formatted = text
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--accent-cyan); text-decoration:underline;">$1</a>')
    .replace(/> (.*?)(?:<br>|$)/g, '<blockquote>$1</blockquote>');

  msgEl.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-body">
      <p>${formatted}</p>
      ${toolTags ? `<div style="margin-top:6px;">${toolTags}</div>` : ''}
    </div>
  `;
  chatMessages.appendChild(msgEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendTypingIndicator() {
  const id = `typing-${Date.now()}`;
  const el = document.createElement('div');
  el.id = id;
  el.className = 'message assistant';
  el.innerHTML = `
    <div class="msg-avatar">🧃</div>
    <div class="msg-body"><p><em>Gurt is coordinating with event tools...</em></p></div>
  `;
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return id;
}

function removeMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// Global data refresh
async function loadAllRecords() {
  loadOverview();
  loadBrief();
  loadSchedule();
  loadApprovals();
  loadTasks();
  loadSpeakers();
  loadVendors();
  loadVendorRequirements();
  loadSponsors();
  loadPdfDocuments();
}

async function loadOverview() {
  try {
    const res = await fetch('/api/overview');
    if (!res.ok) return;
    const data = await res.json();
    const ev = data.event || {};
    activeEventBrief = ev;

    const titleEl = document.getElementById('header-event-title');
    if (titleEl) titleEl.textContent = ev.title || 'DubHacks 2026 Agentic AI Workshop';

    const metaEl = document.getElementById('header-event-meta');
    if (metaEl) metaEl.textContent = `${ev.date || 'Nov 15, 2026'} • ${ev.location || 'UW HUB'} • ${ev.attendee_count || 80} Attendees`;

    const budgetEl = document.getElementById('stat-budget');
    if (budgetEl) budgetEl.textContent = `$${(ev.budget || 2500).toLocaleString()}`;

    const tasksEl = document.getElementById('stat-tasks');
    if (tasksEl) tasksEl.textContent = data.tasks || '0/0';

    const spkEl = document.getElementById('stat-speakers');
    if (spkEl) spkEl.textContent = data.speakers ? data.speakers.split(' ')[0] : '0/0';
  } catch (e) {}
}

async function loadBrief() {
  const container = document.getElementById('brief-display-container');
  try {
    const res = await fetch('/api/event/brief');
    const b = await res.json();
    activeEventBrief = b;

    container.innerHTML = `
      <div class="brief-container">
        <div class="brief-hero">
          <div class="brief-hero-header">
            <div>
              <div class="brief-hero-title">${b.title}</div>
              <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Status: <strong style="color:var(--accent-cyan); text-transform:uppercase;">${b.status}</strong> • Updated: <strong>${(b.updated_at || '').slice(0, 16).replace('T', ' ')}</strong></div>
            </div>
            <button class="btn-small btn-primary" onclick="openEditBriefModal()">✎ Edit Specifications</button>
          </div>
          <p style="font-size:13px; line-height:1.5; color:var(--text-secondary); margin-top:10px;">${b.goals || 'No goals specified yet.'}</p>
        </div>

        <div class="brief-meta-grid">
          <div class="brief-meta-card">
            <div class="brief-meta-label">Date & Time</div>
            <div class="brief-meta-val">${b.date}</div>
          </div>
          <div class="brief-meta-card">
            <div class="brief-meta-label">Location / Venue</div>
            <div class="brief-meta-val">${b.location}</div>
          </div>
          <div class="brief-meta-card">
            <div class="brief-meta-label">Headcount</div>
            <div class="brief-meta-val">${b.attendee_count} Attendees</div>
          </div>
          <div class="brief-meta-card">
            <div class="brief-meta-label">Total Budget</div>
            <div class="brief-meta-val" style="color:var(--accent-emerald);">$${Number(b.budget || 0).toLocaleString()}</div>
          </div>
          <div class="brief-meta-card" style="grid-column: 1 / -1;">
            <div class="brief-meta-label">Dietary Specifications (Catering Bound)</div>
            <div class="brief-meta-val" style="font-weight:normal; font-size:12.5px;">${b.dietary_specs || 'Nut-free facility required; vegan, halal, and gluten-free meal boxes.'}</div>
          </div>
          <div class="brief-meta-card" style="grid-column: 1 / -1;">
            <div class="brief-meta-label">AV & Technical Requirements</div>
            <div class="brief-meta-val" style="font-weight:normal; font-size:12.5px;">${b.av_requirements || 'Dual projectors in Room 214, 2 wireless handheld mics, podium lapel mic.'}</div>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load event brief.</div>`;
  }
}

async function loadSchedule() {
  const container = document.getElementById('schedule-list');
  try {
    const res = await fetch('/api/schedule');
    const schedule = await res.json();

    if (!schedule || schedule.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          No schedule generated yet. Click "Re-synthesize Schedule" to build the run-of-show timeline!
        </div>
      `;
      return;
    }

    container.innerHTML = schedule.map(s => {
      let typeColor = 'rgba(99,102,241,0.2)';
      let textCol = '#a5b4fc';
      if (s.activity_type === 'keynote') { typeColor = 'rgba(16,185,129,0.2)'; textCol = '#6ee7b7'; }
      else if (s.activity_type === 'lunch') { typeColor = 'rgba(245,158,11,0.2)'; textCol = '#fcd34d'; }
      else if (s.activity_type === 'setup' || s.activity_type === 'teardown') { typeColor = 'rgba(244,63,94,0.2)'; textCol = '#fda4af'; }

      return `
        <div class="timeline-card">
          <div class="timeline-time-badge">${s.time_slot}</div>
          <div class="timeline-body">
            <div class="timeline-title">${s.activity}</div>
            <div class="timeline-meta">
              <span>📍 <strong>${s.location}</strong></span>
              <span>👤 Owner: <strong>${s.owner}</strong></span>
              <span style="background:${typeColor}; color:${textCol}; padding:2px 8px; border-radius:4px; font-weight:600; text-transform:uppercase; font-size:10px;">${s.activity_type}</span>
            </div>
            ${s.notes ? `<div style="font-size:11.5px; color:#94a3b8; margin-top:4px;">${s.notes}</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load schedule.</div>`;
  }
}

async function handleGenerateSchedule() {
  try {
    const res = await fetch('/api/schedule/generate', { method: 'POST' });
    if (res.ok) {
      loadSchedule();
      appendMessage('assistant', `📅 **Run-of-Show Schedule Synthesized!** Integrated confirmed keynote, hands-on tracks, catered lunch, and teardown.`);
    }
  } catch (e) {
    alert('Error generating schedule: ' + e.message);
  }
}

async function loadApprovals() {
  const container = document.getElementById('approvals-list');
  try {
    const res = await fetch('/api/actions');
    const actions = await res.json();
    allActionProposals = actions;
    const pending = actions.filter(a => a.status === 'pending_approval');
    if (approvalCountBadge) approvalCountBadge.textContent = pending.length;

    if (actions.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          No pending actions. Ask Gurt in chat: <em>"Draft an outreach email to Dr. Alicia Chen"</em> to test!
        </div>
      `;
      return;
    }

    container.innerHTML = actions.map(act => {
      let payload = {};
      try { payload = JSON.parse(act.payload); } catch(e) {}
      const isPending = act.status === 'pending_approval';
      const isSlack = act.action_type === 'slack_message';

      return `
        <div class="card">
          <div class="card-header">
            <div>
              <span class="card-title">${act.title}</span>
              <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">ID: <code>${act.id}</code></div>
            </div>
            <span class="card-badge ${isPending ? 'badge-pending' : 'badge-executed'}">${act.status.replace('_', ' ')}</span>
          </div>
          <div class="card-body">
            ${isSlack ? `<strong>Target Channel:</strong> <code>${payload.channel || '#event-ops'}</code>` : `<strong>Recipient:</strong> ${payload.recipient_email || 'On file'}`}
            ${payload.subject ? `<div style="font-size:12px; margin-top:4px; font-weight:600;">Subject: ${payload.subject}</div>` : ''}
          </div>
          <div class="card-preview">${payload.message_body || payload.message || act.payload}</div>
          <div class="card-footer">
            ${isPending ? `
              <div style="display:flex; gap:8px;">
                <button class="btn-approve" onclick="approveAction('${act.id}')">Approve & Send</button>
                <button class="btn-edit-draft" onclick="openEditDraftModal('${act.id}')">✎ Edit Draft</button>
                <button class="btn-dismiss" onclick="dismissAction('${act.id}')">Dismiss</button>
              </div>
            ` : `
              <span style="font-size:11px; color:var(--accent-emerald);">✓ Executed at ${(act.executed_at || '').slice(11, 19)}</span>
            `}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load action center.</div>`;
  }
}

async function approveAction(actionId) {
  try {
    const res = await fetch(`/api/actions/${actionId}/approve`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      appendMessage('assistant', `✅ **Action Approved & Dispatched!** "${data.title}" has been executed.`);
      loadAllRecords();
    } else {
      alert(`Approval error: ${data.detail || 'Could not approve action'}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

async function dismissAction(actionId) {
  try {
    const res = await fetch(`/api/actions/${actionId}/dismiss`, { method: 'POST' });
    if (res.ok) {
      loadAllRecords();
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

function openEditDraftModal(actionId) {
  const act = allActionProposals.find(a => a.id === actionId);
  if (!act) return;
  let payload = {};
  try { payload = JSON.parse(act.payload); } catch(e) {}

  document.getElementById('modal-draft-id').value = actionId;
  document.getElementById('modal-draft-subject').value = payload.subject || act.title;
  document.getElementById('modal-draft-body').value = payload.message_body || payload.message || '';
  document.getElementById('edit-draft-modal').style.display = 'flex';
}

async function handleSaveDraftEdit(e) {
  e.preventDefault();
  const id = document.getElementById('modal-draft-id').value;
  const subject = document.getElementById('modal-draft-subject').value.trim();
  const message_body = document.getElementById('modal-draft-body').value.trim();

  try {
    const res = await fetch(`/api/actions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, message_body })
    });
    if (res.ok) {
      closeModal('edit-draft-modal');
      loadApprovals();
      appendMessage('assistant', `✏️ **Draft Updated!** Changes saved to action proposal \`${id}\`. Ready for approval.`);
    }
  } catch (err) {
    alert('Error saving draft: ' + err.message);
  }
}

// PDF Form Filling Standout Workflow
async function triggerFillPdf() {
  const btn = document.querySelector('.btn-pdf-action');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/pdf/fill', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      displayPdfSuccess(data);
      appendMessage('assistant', `📄 **Facility Booking Form Filled!** Generated draft PDF: [${data.output_file}](${data.download_url}). 8 facts mapped from brief/catering records; 8 items left unresolved.`);
    }
  } catch (err) {
    alert('PDF form fill error: ' + err.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function displayPdfSuccess(data) {
  const area = document.getElementById('pdf-download-area');
  if (!area) return;

  const missingList = data.unresolved_missing_fields.map(m => `<li><strong>${m.field}:</strong> ${m.reason}</li>`).join('');

  area.innerHTML = `
    <div style="background:var(--bg-card); border:1px solid var(--accent-emerald); border-radius:var(--radius-sm); padding:12px; margin-top:10px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <span style="font-size:13px; font-weight:700; color:var(--text-main);">Draft PDF Created: <code>${data.output_file}</code></span>
          <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Mapped ${data.field_counts.mapped} fields • Original template preserved untouched</div>
        </div>
        <a href="${data.download_url}" target="_blank" class="btn-pdf-action" style="padding:6px 12px; font-size:12px;">⬇ Download PDF</a>
      </div>
      <div class="pdf-unresolved-box">
        <strong>⚠️ Unresolved Fields Requiring Manual Organizer Review (${data.field_counts.unresolved}):</strong>
        <ul class="pdf-unresolved-list">${missingList}</ul>
      </div>
    </div>
  `;
}

async function loadPdfDocuments() {
  try {
    const res = await fetch('/api/pdf/documents');
    const docs = await res.json();
    if (docs.length > 0) {
      const latest = docs[0];
      const filename = latest.file_path.split('\\').pop().split('/').pop();
      const area = document.getElementById('pdf-download-area');
      if (area && !area.innerHTML.trim()) {
        area.innerHTML = `
          <div style="display:flex; align-items:center; justify-content:space-between; background:var(--bg-card); padding:8px 12px; border-radius:var(--radius-sm); border:1px solid var(--border-color); margin-top:8px;">
            <span style="font-size:12px;">Existing Draft on File: <code>${filename}</code></span>
            <a href="/api/pdf/download/${filename}" target="_blank" class="btn-pdf-secondary">Download Latest Draft</a>
          </div>
        `;
      }
    }
  } catch (e) {}
}

async function loadTasks() {
  const container = document.getElementById('tasks-list');
  try {
    const res = await fetch('/api/records/tasks');
    const tasks = await res.json();
    if (tasksCountBadge) tasksCountBadge.textContent = tasks.length;

    container.innerHTML = tasks.map(t => {
      const nextStatus = t.status === 'todo' ? 'in_progress' : (t.status === 'in_progress' ? 'done' : 'todo');
      return `
        <div class="card">
          <div class="card-header">
            <div>
              <span class="card-title">${t.title}</span>
              <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Owner: <strong>${t.owner}</strong> • Due: <strong>${t.deadline}</strong></div>
            </div>
            <button class="task-toggle-btn" onclick="toggleTaskStatus('${t.id}', '${nextStatus}')" title="Click to cycle status">
              <span class="card-badge badge-${t.status}">${t.status.replace('_', ' ')} ↻</span>
            </button>
          </div>
          <div class="card-body">
            <span style="font-size:11px; background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:4px;">${t.category}</span>
            ${t.dependencies && t.dependencies !== 'None' ? `<span style="font-size:11px; color:var(--accent-amber); margin-left:6px;">⚠️ Depends on: ${t.dependencies}</span>` : ''}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load tasks.</div>`;
  }
}

async function toggleTaskStatus(taskId, nextStatus) {
  try {
    const res = await fetch(`/api/tasks/${taskId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: nextStatus })
    });
    if (res.ok) {
      loadAllRecords();
    }
  } catch (e) {}
}

async function loadSpeakers() {
  const container = document.getElementById('speakers-list');
  try {
    const res = await fetch('/api/records/speakers');
    const speakers = await res.json();
    if (speakersCountBadge) speakersCountBadge.textContent = speakers.length;

    container.innerHTML = speakers.map(s => `
      <div class="card">
        <div class="card-header">
          <div>
            <span class="card-title">${s.name}</span>
            <div style="font-size:11px; color:var(--text-muted);">${s.org}</div>
          </div>
          <span class="card-badge badge-${s.status}">${s.status}</span>
        </div>
        <div class="card-body">
          <p><strong>Topic:</strong> ${s.topic}</p>
          <p style="margin-top:4px; font-size:11.5px; color:var(--text-muted);">Slot: ${s.proposed_time || 'TBD'} • ${s.contact_email || ''}</p>
          ${s.bio ? `<p style="margin-top:6px; font-size:11.5px; color:#94a3b8;">${s.bio}</p>` : ''}
        </div>
        <div class="card-footer">
          <button class="btn-small" onclick="sendQuickPrompt('Draft an outreach invitation to ${s.name}')">✉️ Draft Invite</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load speakers.</div>`;
  }
}

async function loadVendorRequirements() {
  const container = document.getElementById('requirements-list');
  if (!container) return;
  try {
    const res = await fetch('/api/vendor-requirements');
    const reqs = await res.json();

    if (reqs.length === 0) {
      container.innerHTML = `<div class="empty-state">No vendor requirements logged yet.</div>`;
      return;
    }

    container.innerHTML = reqs.map(r => `
      <div class="card" style="border-left: 3px solid var(--accent-cyan);">
        <div class="card-header">
          <div>
            <span class="card-title">${r.category}</span>
            <div style="font-size:11px; color:var(--text-muted);">Headcount: <strong>${r.headcount}</strong> • Allocated Budget: <strong>$${Number(r.budget_allocated || 0).toLocaleString()}</strong></div>
          </div>
          <span class="card-badge badge-${r.status}">${r.status}</span>
        </div>
        <div class="card-body">
          <p style="font-size:12.5px;">${r.specification}</p>
          ${r.unknowns ? `<div style="margin-top:6px; font-size:11.5px; color:#fbbf24;">⚠️ <strong>Unknowns to resolve:</strong> ${r.unknowns}</div>` : ''}
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load requirements.</div>`;
  }
}

async function loadVendors() {
  const container = document.getElementById('vendors-list');
  try {
    const res = await fetch('/api/records/vendors');
    const vendors = await res.json();
    if (vendorsCountBadge) vendorsCountBadge.textContent = vendors.length;

    container.innerHTML = vendors.map(v => {
      const perHeadStr = v.price_per_head ? `$${v.price_per_head.toFixed(2)}/head` : '';
      return `
        <div class="card">
          <div class="card-header">
            <div>
              <span class="card-title">${v.company_name}</span>
              <div style="font-size:11px; color:var(--text-muted);">${v.category}</div>
            </div>
            <span class="card-badge badge-${v.status}">${v.status}</span>
          </div>
          <div class="card-body">
            <div style="font-size:15px; font-weight:700; color:var(--accent-cyan); margin-bottom:4px;">
              $${v.quote_amount.toFixed(2)} <span style="font-size:11px; color:var(--text-muted); font-weight:normal;">${perHeadStr}</span>
            </div>
            <p style="font-size:12px;">${v.details}</p>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load vendors.</div>`;
  }
}

async function loadSponsors() {
  const container = document.getElementById('sponsors-list');
  try {
    const res = await fetch('/api/records/sponsors');
    const sponsors = await res.json();
    if (sponsorsCountBadge) sponsorsCountBadge.textContent = sponsors.length;

    container.innerHTML = sponsors.map(sp => `
      <div class="card">
        <div class="card-header">
          <div>
            <span class="card-title">${sp.name}</span>
            <div style="font-size:11px; color:var(--text-muted);">${sp.tier} Sponsor</div>
          </div>
          <span class="card-badge badge-confirmed">${sp.status}</span>
        </div>
        <div class="card-body">
          <div style="font-size:15px; font-weight:700; color:var(--accent-emerald); margin-bottom:4px;">
            $${sp.amount.toFixed(2)}
          </div>
          <p style="font-size:12px;">${sp.notes}</p>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load sponsors.</div>`;
  }
}

// Modal handling
function openEditBriefModal() {
  const b = activeEventBrief;
  document.getElementById('modal-brief-title').value = b.title || '';
  document.getElementById('modal-brief-date').value = b.date || '';
  document.getElementById('modal-brief-attendees').value = b.attendee_count || 80;
  document.getElementById('modal-brief-location').value = b.location || '';
  document.getElementById('modal-brief-budget').value = b.budget || 2500;
  document.getElementById('modal-brief-goals').value = b.goals || '';
  document.getElementById('modal-brief-dietary').value = b.dietary_specs || '';
  document.getElementById('modal-brief-av').value = b.av_requirements || '';
  document.getElementById('brief-modal').style.display = 'flex';
}

async function handleSaveBrief(e) {
  e.preventDefault();
  const title = document.getElementById('modal-brief-title').value.trim();
  const date = document.getElementById('modal-brief-date').value.trim();
  const attendee_count = parseInt(document.getElementById('modal-brief-attendees').value);
  const location = document.getElementById('modal-brief-location').value.trim();
  const budget = parseFloat(document.getElementById('modal-brief-budget').value);
  const goals = document.getElementById('modal-brief-goals').value.trim();
  const dietary_specs = document.getElementById('modal-brief-dietary').value.trim();
  const av_requirements = document.getElementById('modal-brief-av').value.trim();

  try {
    const res = await fetch('/api/event/brief', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date, attendee_count, location, budget, goals, dietary_specs, av_requirements })
    });
    if (res.ok) {
      closeModal('brief-modal');
      loadAllRecords();
      appendMessage('assistant', `📝 **Event Brief Updated!** Title: "${title}", Headcount: ${attendee_count}, Budget: $${budget.toLocaleString()}.`);
    }
  } catch (err) {
    alert('Error saving brief: ' + err.message);
  }
}

function openAddTaskModal() {
  document.getElementById('task-modal').style.display = 'flex';
}

function openAddVendorModal() {
  document.getElementById('vendor-modal').style.display = 'flex';
}

function openAddReqModal() {
  document.getElementById('req-modal').style.display = 'flex';
}

function closeModal(modalId) {
  document.getElementById(modalId).style.display = 'none';
}

async function handleCreateTask(e) {
  e.preventDefault();
  const title = document.getElementById('modal-task-title').value.trim();
  const owner = document.getElementById('modal-task-owner').value.trim();
  const category = document.getElementById('modal-task-category').value;
  const deadline = document.getElementById('modal-task-deadline').value;
  const dependencies = document.getElementById('modal-task-deps').value.trim() || 'None';

  try {
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, owner, category, deadline, dependencies })
    });
    if (res.ok) {
      closeModal('task-modal');
      document.getElementById('add-task-form').reset();
      loadAllRecords();
      appendMessage('assistant', `📋 **Task Added!** Created "${title}" assigned to **${owner}**.`);
    }
  } catch (err) {
    alert(`Error creating task: ${err.message}`);
  }
}

async function handleCreateVendor(e) {
  e.preventDefault();
  const company_name = document.getElementById('modal-vendor-name').value.trim();
  const category = document.getElementById('modal-vendor-category').value;
  const quote_amount = parseFloat(document.getElementById('modal-vendor-amount').value);
  const price_per_head = parseFloat(document.getElementById('modal-vendor-perhead').value) || 0.0;
  const contact_email = document.getElementById('modal-vendor-email').value.trim();
  const details = document.getElementById('modal-vendor-details').value.trim();

  try {
    const res = await fetch('/api/vendors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_name, category, quote_amount, price_per_head, contact_email, details })
    });
    if (res.ok) {
      closeModal('vendor-modal');
      document.getElementById('add-vendor-form').reset();
      loadAllRecords();
      appendMessage('assistant', `🍱 **Vendor Quote Recorded!** Saved quote for **${company_name}** ($${quote_amount.toFixed(2)}).`);
    }
  } catch (err) {
    alert(`Error saving vendor: ${err.message}`);
  }
}

async function handleCreateReq(e) {
  e.preventDefault();
  const category = document.getElementById('modal-req-category').value;
  const headcount = parseInt(document.getElementById('modal-req-headcount').value);
  const specification = document.getElementById('modal-req-spec').value.trim();
  const unknowns = document.getElementById('modal-req-unknowns').value.trim();

  try {
    const res = await fetch('/api/vendor-requirements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, headcount, specification, unknowns })
    });
    if (res.ok) {
      closeModal('req-modal');
      document.getElementById('add-req-form').reset();
      loadAllRecords();
      appendMessage('assistant', `🔍 **Vendor Need Logged!** Recorded specification for **${category}** (${headcount} pax).`);
    }
  } catch (err) {
    alert(`Error saving requirement: ${err.message}`);
  }
}

// Initial boot load
loadAllRecords();
