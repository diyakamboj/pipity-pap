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

      // Update model badge if Gemini was used
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
  loadApprovals();
  loadTasks();
  loadSpeakers();
  loadVendors();
  loadSponsors();
}

async function loadOverview() {
  try {
    const res = await fetch('/api/overview');
    if (!res.ok) return;
    const data = await res.json();
    const ev = data.event || {};
    
    const budgetEl = document.getElementById('stat-budget');
    if (budgetEl) budgetEl.textContent = `$${(ev.budget || 2500).toLocaleString()}`;
    
    const tasksEl = document.getElementById('stat-tasks');
    if (tasksEl) tasksEl.textContent = data.tasks || '0/0';

    const spkEl = document.getElementById('stat-speakers');
    if (spkEl) spkEl.textContent = data.speakers ? data.speakers.split(' ')[0] : '0/0';
  } catch (e) {}
}

async function loadApprovals() {
  const container = document.getElementById('approvals-list');
  try {
    const res = await fetch('/api/actions');
    const actions = await res.json();
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
          </div>
          <div class="card-preview">${payload.message_body || payload.message || act.payload}</div>
          <div class="card-footer">
            ${isPending ? `
              <div style="display:flex; gap:8px;">
                <button class="btn-approve" onclick="approveAction('${act.id}')">Approve & Send</button>
                <button class="btn-dismiss" onclick="dismissAction('${act.id}')">Dismiss</button>
              </div>
            ` : `
              <span style="font-size:11px; color:var(--accent-emerald);">✓ Executed</span>
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
function openAddTaskModal() {
  document.getElementById('task-modal').style.display = 'flex';
}

function openAddVendorModal() {
  document.getElementById('vendor-modal').style.display = 'flex';
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

// Initial boot load
loadAllRecords();
