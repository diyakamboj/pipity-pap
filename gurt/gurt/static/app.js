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
let currentConversationId = null;
let currentModel = 'gemini-3.8-flash';
let currentEventId = localStorage.getItem('gurt_active_event_id') || 'evt-dubhacks-2026';
let allEventsList = [];

// Toggle Sidebar
function toggleSidebar() {
  const sidebar = document.getElementById('app-sidebar');
  if (sidebar) {
    sidebar.classList.toggle('collapsed');
  }
}

// Model Change Handler
function handleModelChange() {
  const select = document.getElementById('model-select');
  if (select) {
    currentModel = select.value;
    const badge = document.getElementById('model-badge');
    if (badge) {
      if (currentModel.includes('gemini-3.8')) badge.textContent = 'Gemini 3.8 • Online';
      else if (currentModel.includes('gemini-3')) badge.textContent = 'Gemini 3.0 • Online';
      else if (currentModel.includes('grok')) badge.textContent = 'Grok 2 • Online';
      else badge.textContent = 'Semantic Engine • Local';
    }
  }
}

// Events Management
async function loadEventsList() {
  try {
    const res = await fetch('/api/events');
    if (!res.ok) return;
    const events = await res.json();
    allEventsList = events;

    const select = document.getElementById('event-select');
    if (!select) return;

    select.innerHTML = events.map(e => `
      <option value="${e.id}" ${e.id === currentEventId ? 'selected' : ''}>${e.title}</option>
    `).join('') + `<option value="__new__">+ Create New Event...</option>`;

    if (events.length > 0 && !events.some(e => e.id === currentEventId)) {
      currentEventId = events[0].id;
      localStorage.setItem('gurt_active_event_id', currentEventId);
      select.value = currentEventId;
    }
  } catch (e) {}
}

function handleEventSelectChange(val) {
  if (val === '__new__') {
    openNewEventModal();
    const select = document.getElementById('event-select');
    if (select) select.value = currentEventId;
    return;
  }
  currentEventId = val;
  localStorage.setItem('gurt_active_event_id', currentEventId);
  loadAllRecords();
  loadConversations();
  const evt = allEventsList.find(e => e.id === val);
  appendMessage('assistant', `Switched active event context to **${evt ? evt.title : val}**.`);
}

function openNewEventModal() {
  document.getElementById('new-event-modal').style.display = 'flex';
}

async function handleCreateNewEvent(e) {
  e.preventDefault();
  const title = document.getElementById('modal-new-event-title').value.trim();
  const attendee_count = parseInt(document.getElementById('modal-new-event-attendees').value) || 50;
  const budget = parseFloat(document.getElementById('modal-new-event-budget').value) || 1000.0;
  const location = document.getElementById('modal-new-event-location').value.trim();
  const date = document.getElementById('modal-new-event-date').value.trim();
  const goals = document.getElementById('modal-new-event-goals').value.trim();

  try {
    const res = await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        attendee_count,
        budget,
        location,
        date,
        goals
      })
    });
    if (res.ok) {
      const created = await res.json();
      closeModal('new-event-modal');
      currentEventId = created.id;
      localStorage.setItem('gurt_active_event_id', currentEventId);
      await loadEventsList();
      loadAllRecords();
      loadConversations();
      appendMessage('assistant', `🎉 **Event Created!** Switched active workspace to **${created.title}** (\`${created.id}\`). Isolated tasks, vendors, and requirements initialized.`);
    } else {
      alert('Error creating event');
    }
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

// Conversations Management
async function loadConversations() {
  try {
    const res = await fetch('/api/conversations?event_id=' + encodeURIComponent(currentEventId));
    if (!res.ok) return;
    const convs = await res.json();

    const list = document.getElementById('conversations-list');
    const badge = document.getElementById('conv-count-badge');
    if (badge) badge.textContent = convs.length;

    if (!list) return;
    list.innerHTML = '';

    if (convs.length === 0) {
      list.innerHTML = `<div style="font-size:11px; color:var(--text-muted); text-align:center; padding:16px;">No chats yet. Click "+ New Chat" to start.</div>`;
      return;
    }

    convs.forEach(c => {
      const item = document.createElement('div');
      item.className = `conv-item ${c.id === currentConversationId ? 'active' : ''}`;
      item.onclick = () => selectConversation(c.id, c.title);

      const timeStr = c.updated_at ? c.updated_at.slice(11, 16) : '';
      item.innerHTML = `
        <span style="font-size:14px;">💬</span>
        <div class="conv-item-content">
          <span class="conv-title" title="${c.title || 'Untitled Chat'}">${c.title || 'Untitled Chat'}</span>
          <span class="conv-time">${timeStr || 'Recent'}</span>
        </div>
        <button class="conv-del-btn" title="Delete conversation" onclick="handleDeleteConversation('${c.id}', event)">✕</button>
      `;
      list.appendChild(item);
    });

    // If no active conversation, select first
    if (!currentConversationId && convs.length > 0) {
      selectConversation(convs[0].id, convs[0].title);
    }
  } catch (e) {
    console.error('Error loading conversations:', e);
  }
}

async function selectConversation(convId, title = '') {
  currentConversationId = convId;

  // Update UI active state
  document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.conv-item').forEach(el => {
    if (el.getAttribute('onclick') && el.getAttribute('onclick').includes(convId)) {
      el.classList.add('active');
    }
  });

  const headerTitle = document.getElementById('chat-header-title');
  if (headerTitle && title) {
    headerTitle.textContent = title;
  }

  // Load messages from SQLite
  try {
    const res = await fetch(`/api/conversations/${convId}/messages`);
    if (!res.ok) return;
    const msgs = await res.json();

    chatMessages.innerHTML = '';
    conversationHistory = [];

    if (msgs.length === 0) {
      chatMessages.innerHTML = `
        <div class="message assistant">
          <div class="msg-avatar">🧃</div>
          <div class="msg-body">
            <p><strong>Thread opened!</strong> What would you like Gurt to coordinate in this session?</p>
          </div>
        </div>
      `;
    } else {
      msgs.forEach(m => {
        appendMessage(m.role, m.content, m.tool_calls, m.model_used);
        conversationHistory.push({ role: m.role, content: m.content });
      });
      if (conversationHistory.length > 8) conversationHistory = conversationHistory.slice(-8);
    }
  } catch (e) {
    console.error('Error loading messages for conversation:', e);
  }
}

async function handleNewConversation() {
  try {
    const res = await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New Operations Thread', event_id: currentEventId })
    });
    if (!res.ok) return;
    const newConv = await res.json();
    await loadConversations();
    selectConversation(newConv.id, newConv.title);
  } catch (e) {
    console.error('Error creating new conversation:', e);
  }
}

async function handleDeleteConversation(convId, event) {
  if (event) event.stopPropagation();
  try {
    await fetch(`/api/conversations/${convId}`, { method: 'DELETE' });
    if (currentConversationId === convId) {
      currentConversationId = null;
    }
    await loadConversations();
  } catch (e) {
    console.error('Error deleting conversation:', e);
  }
}

// Persistent Memory Management
function openMemoryModal() {
  document.getElementById('memory-modal').style.display = 'flex';
  loadMemories();
}

async function loadMemories() {
  try {
    const res = await fetch('/api/memories?event_id=' + encodeURIComponent(currentEventId));
    if (!res.ok) return;
    const memories = await res.json();

    const container = document.getElementById('memory-items-container');
    const modalCount = document.getElementById('modal-memory-count');
    const sideCount = document.getElementById('sidebar-mem-count');

    if (modalCount) modalCount.textContent = `${memories.length} facts`;
    if (sideCount) sideCount.textContent = `${memories.length} preferences`;

    if (!container) return;
    container.innerHTML = '';

    if (memories.length === 0) {
      container.innerHTML = `<div style="font-size:12px; color:var(--text-muted); text-align:center; padding:18px;">No persistent memories stored yet. Add facts above!</div>`;
      return;
    }

    memories.forEach(m => {
      const card = document.createElement('div');
      card.className = 'memory-item-card';
      card.innerHTML = `
        <div>
          <div>
            <span class="memory-key-tag">${m.key}</span>
            <span class="memory-cat-tag">[${m.category || 'preference'}]</span>
          </div>
          <div class="memory-val-text">${m.value}</div>
        </div>
        <button class="memory-del-btn" title="Delete memory item" onclick="handleDeleteMemory('${m.id}')">✕</button>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error('Error loading memories:', e);
  }
}

async function handleSaveMemory(event) {
  event.preventDefault();
  const key = document.getElementById('mem-input-key').value.trim();
  const category = document.getElementById('mem-input-category').value;
  const value = document.getElementById('mem-input-val').value.trim();

  if (!key || !value) return;

  try {
    const res = await fetch('/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, category, value, event_id: currentEventId })
    });
    if (res.ok) {
      document.getElementById('add-memory-form').reset();
      loadMemories();
      appendMessage('assistant', `🧠 **Persistent Memory Saved:** Recorded \`${key}\` (${category}): "${value}".`);
    }
  } catch (e) {
    alert(`Error saving memory: ${e.message}`);
  }
}

async function handleDeleteMemory(memId) {
  try {
    await fetch(`/api/memories/${memId}`, { method: 'DELETE' });
    loadMemories();
  } catch (e) {
    console.error('Error deleting memory:', e);
  }
}

// Side Canvas & Navigation State Controller
let currentCanvasPane = null;

function openSideCanvas(paneId, icon, title) {
  const canvas = document.getElementById('side-canvas');
  const canvasTitle = document.getElementById('side-canvas-title');
  const canvasIcon = document.getElementById('side-canvas-icon');
  const toggleBtn = document.getElementById('canvas-toggle-btn');

  // Hide all panes
  document.querySelectorAll('.canvas-pane').forEach(p => {
    p.style.display = 'none';
  });

  // Show target pane
  const pane = document.getElementById(`pane-${paneId}`);
  if (pane) pane.style.display = 'flex';

  // Update header
  if (canvasTitle) canvasTitle.textContent = title;
  if (canvasIcon) canvasIcon.textContent = icon;

  // Highlight active sidebar navigation item
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  const activeNav = document.getElementById(`nav-${paneId}`);
  if (activeNav) activeNav.classList.add('active');

  // Highlight toggle button
  if (toggleBtn) toggleBtn.classList.add('active');

  // Open canvas if collapsed
  if (canvas) canvas.classList.remove('collapsed');
  currentCanvasPane = paneId;

  // Trigger pane data loader
  const loaders = {
    'approvals': loadApprovals,
    'pdf': () => { loadPdfDocuments(); },
    'brief': loadBrief,
    'schedule': loadSchedule,
    'tasks': loadTasks,
    'speakers': loadSpeakers,
    'vendors': () => { loadVendors(); loadVendorRequirements(); },
    'sponsors': loadSponsors,
    'guardrails': () => {},
  };
  if (loaders[paneId]) loaders[paneId]();
}

function closeSideCanvas() {
  const canvas = document.getElementById('side-canvas');
  if (canvas) canvas.classList.add('collapsed');
  
  const toggleBtn = document.getElementById('canvas-toggle-btn');
  if (toggleBtn) toggleBtn.classList.remove('active');

  // Reset sidebar active item to Chat Console
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  const chatNav = document.getElementById('nav-chat');
  if (chatNav) chatNav.classList.add('active');

  currentCanvasPane = null;
}

function toggleSideCanvas() {
  const canvas = document.getElementById('side-canvas');
  if (!canvas) return;
  if (canvas.classList.contains('collapsed')) {
    openSideCanvas(currentCanvasPane || 'approvals', '⚡', 'Action Center');
  } else {
    closeSideCanvas();
  }
}

function navigateToChat() {
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  const chatNav = document.getElementById('nav-chat');
  if (chatNav) chatNav.classList.add('active');
  closeSideCanvas();
}

function handleSidebarSearch(query) {
  const q = (query || '').toLowerCase().trim();

  // Filter conversations
  document.querySelectorAll('.conv-item').forEach(item => {
    const title = item.querySelector('.conv-title')?.textContent.toLowerCase() || '';
    if (!q || title.includes(q)) {
      item.style.display = 'flex';
    } else {
      item.style.display = 'none';
    }
  });

  // Filter operations views
  document.querySelectorAll('.nav-item').forEach(item => {
    const label = item.querySelector('.nav-label')?.textContent.toLowerCase() || '';
    if (!q || label.includes(q)) {
      item.style.display = 'flex';
    } else {
      item.style.display = 'none';
    }
  });
}

// Global hotkey: Escape key closes side canvas
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeSideCanvas();
  }
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
      body: JSON.stringify({
        message: text,
        history: conversationHistory,
        conversation_id: currentConversationId,
        model: currentModel,
        event_id: currentEventId
      })
    });

    const data = await res.json();
    removeMessage(typingId);

    if (data.text) {
      appendMessage('assistant', data.text, data.tool_calls, data.model_used);
      conversationHistory.push({ role: 'user', content: text });
      conversationHistory.push({ role: 'assistant', content: data.text });
      if (conversationHistory.length > 8) conversationHistory = conversationHistory.slice(-8);

      if (data.conversation_id && !currentConversationId) {
        currentConversationId = data.conversation_id;
      }

      if (data.switched_event_id && data.switched_event_id !== currentEventId) {
        currentEventId = data.switched_event_id;
        localStorage.setItem('gurt_active_event_id', currentEventId);
        loadEventsList();
      }

      if (data.model_used) {
        const badge = document.getElementById('model-badge');
        if (badge) {
          badge.textContent = data.model_used.includes('gemini') ? 'Gemini • Online' : (data.model_used.includes('grok') ? 'Grok • Online' : 'Dynamic Engine • Online');
        }
      }

      // Refresh conversations list to update title/timestamps
      loadConversations();
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
  let actionCardHtml = '';

  if (toolCalls && toolCalls.length > 0) {
    toolTags = toolCalls.map(tc => `<div class="tool-tag">⚡ ${tc.tool}()</div>`).join(' ');

    // Generate Contextual Action Cards for standout tool executions
    toolCalls.forEach(tc => {
      const toolName = tc.tool || '';
      if (toolName.includes('pdf')) {
        actionCardHtml += `
          <div class="chat-action-card">
            <div class="action-card-header">
              <span class="action-card-title">📑 Venue Booking AcroForm PDF Ready</span>
              <span class="badge badge-accent">PDF Form</span>
            </div>
            <div class="action-card-desc">Auto-mapped 8 facts from brief and catering records. 8 organizer items flagged for review.</div>
            <button class="action-card-btn" onclick="openSideCanvas('pdf', '📑', 'Venue PDF Contract')">Inspect PDF in Canvas ↗</button>
          </div>
        `;
      } else if (toolName.includes('draft') || toolName.includes('outreach') || toolName.includes('slack')) {
        actionCardHtml += `
          <div class="chat-action-card">
            <div class="action-card-header">
              <span class="action-card-title">⚡ Outreach Proposal Queued</span>
              <span class="badge badge-pending">Pending Approval</span>
            </div>
            <div class="action-card-desc">High-risk external action intercepted. Review subject and message body before dispatching.</div>
            <button class="action-card-btn" onclick="openSideCanvas('approvals', '⚡', 'Action Center')">Review &amp; Edit Draft in Canvas ↗</button>
          </div>
        `;
      } else if (toolName.includes('schedule')) {
        actionCardHtml += `
          <div class="chat-action-card">
            <div class="action-card-header">
              <span class="action-card-title">📅 Run-of-Show Schedule Synthesized</span>
              <span class="badge badge-confirmed">Timeline Synced</span>
            </div>
            <div class="action-card-desc">Detailed timeline slots generated with keynote, workshops, lunch, and teardown.</div>
            <button class="action-card-btn" onclick="openSideCanvas('schedule', '📅', 'Run-of-Show Schedule')">View Timeline in Canvas ↗</button>
          </div>
        `;
      } else if (toolName.includes('vendor') || toolName.includes('catering')) {
        actionCardHtml += `
          <div class="chat-action-card">
            <div class="action-card-header">
              <span class="action-card-title">🏪 Vendor Sourcing &amp; Quotes</span>
              <span class="badge badge-accent">Budget Tracked</span>
            </div>
            <div class="action-card-desc">Catering quotes and unknown specifications logged against the $2,500 hard budget limit.</div>
            <button class="action-card-btn" onclick="openSideCanvas('vendors', '🏪', 'Vendors &amp; Sourcing')">Compare Quotes in Canvas ↗</button>
          </div>
        `;
      } else if (toolName.includes('task')) {
        actionCardHtml += `
          <div class="chat-action-card">
            <div class="action-card-header">
              <span class="action-card-title">✓ Logistics Tasks DAG Updated</span>
              <span class="badge badge-confirmed">Tasks Synced</span>
            </div>
            <div class="action-card-desc">Logistics milestones and dependency graph updated.</div>
            <button class="action-card-btn" onclick="openSideCanvas('tasks', '✓', 'Logistics Tasks DAG')">View Tasks DAG in Canvas ↗</button>
          </div>
        `;
      }
    });
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
      ${actionCardHtml}
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
  loadEventsList();
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
    const res = await fetch('/api/overview?event_id=' + encodeURIComponent(currentEventId));
    if (!res.ok) return;
    const data = await res.json();
    const ev = data.event || {};
    activeEventBrief = ev;

    const titleEl = document.getElementById('header-event-title');
    if (titleEl) titleEl.textContent = ev.title || 'Event';

    const metaEl = document.getElementById('header-event-meta');
    if (metaEl) metaEl.textContent = `${ev.date || 'TBD'} • ${ev.location || 'TBD'} • ${ev.attendee_count || 50} Attendees`;

    const budgetEl = document.getElementById('stat-budget');
    if (budgetEl) budgetEl.textContent = `$${(ev.budget || 0).toLocaleString()}`;

    const tasksEl = document.getElementById('stat-tasks');
    if (tasksEl) tasksEl.textContent = data.tasks || '0/0';

    const spkEl = document.getElementById('stat-speakers');
    if (spkEl) spkEl.textContent = data.speakers ? data.speakers.split(' ')[0] : '0/0';
  } catch (e) {}
}

async function loadBrief() {
  const container = document.getElementById('brief-display-container');
  try {
    const res = await fetch('/api/event/brief?event_id=' + encodeURIComponent(currentEventId));
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
    const res = await fetch('/api/schedule?event_id=' + encodeURIComponent(currentEventId));
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
    const res = await fetch('/api/schedule/generate?event_id=' + encodeURIComponent(currentEventId), { method: 'POST' });
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
    const res = await fetch('/api/actions?event_id=' + encodeURIComponent(currentEventId));
    const actions = await res.json();
    allActionProposals = actions;
    const pending = actions.filter(a => a.status === 'pending_approval');
    if (approvalCountBadge) approvalCountBadge.textContent = pending.length;
    
    const navApprovalBadge = document.getElementById('nav-approval-count');
    const headerCanvasBadge = document.getElementById('header-canvas-count');
    if (navApprovalBadge) navApprovalBadge.textContent = pending.length;
    if (headerCanvasBadge) headerCanvasBadge.textContent = pending.length;

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
    const res = await fetch('/api/pdf/fill?event_id=' + encodeURIComponent(currentEventId), { method: 'POST' });
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
    const res = await fetch('/api/pdf/documents?event_id=' + encodeURIComponent(currentEventId));
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

let allTasks = [];
let activeTaskFilter = 'all';

function filterTasks(status, btnElement) {
  activeTaskFilter = status;
  document.querySelectorAll('.task-filter-btn').forEach(btn => btn.classList.remove('active'));
  if (btnElement) btnElement.classList.add('active');
  renderTasksList();
}

const CATEGORY_ICONS = {
  'Catering': '🍱',
  'Venue': '🏛️',
  'AV': '🎧',
  'Audio/Visual': '🎧',
  'Logistics': '📦',
  'Outreach': '📢',
  'Speakers': '🎤',
  'Sponsors': '💰',
  'Legal': '⚖️',
  'Budget': '💵',
};

function renderTasksList() {
  const container = document.getElementById('tasks-list');
  if (!container) return;

  const filtered = activeTaskFilter === 'all' 
    ? allTasks 
    : allTasks.filter(t => t.status === activeTaskFilter);

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        No tasks found in <strong>${activeTaskFilter.replace('_', ' ')}</strong>.
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(t => {
    const nextStatus = t.status === 'todo' ? 'in_progress' : (t.status === 'in_progress' ? 'done' : 'todo');
    const catIcon = CATEGORY_ICONS[t.category] || '📌';
    
    let statusLabel = 'To Do';
    let statusIcon = '⚪';
    if (t.status === 'in_progress') {
      statusLabel = 'In Progress';
      statusIcon = '🔵';
    } else if (t.status === 'done') {
      statusLabel = 'Completed';
      statusIcon = '🟢';
    }

    return `
      <div class="task-card-v2">
        <div class="task-top-row">
          <div class="task-title-group">
            <span class="task-cat-badge">${catIcon} ${t.category}</span>
            <span class="task-id-badge">#${t.id}</span>
            <span class="task-title-text">${t.title}</span>
          </div>
          <button class="task-status-btn" onclick="toggleTaskStatus('${t.id}', '${nextStatus}')" title="Click to cycle status: To Do → In Progress → Completed">
            <span class="task-status-pill status-${t.status}">
              <span>${statusIcon}</span>
              <span>${statusLabel}</span>
            </span>
          </button>
        </div>

        <div class="task-meta-row">
          <div class="task-meta-item">
            <span>👤</span>
            <span>Assignee: <strong>${t.owner}</strong></span>
          </div>
          <div class="task-meta-item">
            <span>📅</span>
            <span>Target Deadline: <strong>${t.deadline}</strong></span>
          </div>
        </div>

        ${t.dependencies && t.dependencies !== 'None' ? `
          <div class="task-dep-alert">
            <span>🔒</span>
            <span><strong>Dependency Block:</strong> Requires completion of <code>${t.dependencies}</code> before execution.</span>
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

async function loadTasks() {
  try {
    const res = await fetch('/api/records/tasks?event_id=' + encodeURIComponent(currentEventId));
    const tasks = await res.json();
    allTasks = tasks;

    // Update counters in badges
    const tasksCountBadge = document.getElementById('tasks-count');
    const navTasksCount = document.getElementById('nav-tasks-count');
    const statTasks = document.getElementById('stat-tasks');
    
    const total = tasks.length;
    const done = tasks.filter(t => t.status === 'done').length;
    const inProg = tasks.filter(t => t.status === 'in_progress').length;
    const todo = tasks.filter(t => t.status === 'todo').length;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;

    if (tasksCountBadge) tasksCountBadge.textContent = total;
    if (navTasksCount) navTasksCount.textContent = total;
    if (statTasks) statTasks.textContent = `${done}/${total}`;

    // Update progress bar
    const bar = document.getElementById('task-progress-bar');
    const pctText = document.getElementById('task-progress-pct');
    const summaryText = document.getElementById('task-stats-summary');

    if (bar) bar.style.width = `${pct}%`;
    if (pctText) pctText.textContent = `${pct}% Complete`;
    if (summaryText) {
      summaryText.innerHTML = `
        <strong>${total} Total Tasks</strong> • 
        <span style="color:var(--accent-amber);">${todo} To Do</span> • 
        <span style="color:var(--accent-cyan);">${inProg} In Progress</span> • 
        <span style="color:var(--accent-emerald);">${done} Completed</span>
      `;
    }

    renderTasksList();
  } catch (err) {
    const container = document.getElementById('tasks-list');
    if (container) container.innerHTML = `<div class="empty-state">Failed to load tasks.</div>`;
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
    const res = await fetch('/api/records/speakers?event_id=' + encodeURIComponent(currentEventId));
    const speakers = await res.json();
    if (speakersCountBadge) speakersCountBadge.textContent = speakers.length;
    const navSpeakers = document.getElementById('nav-speakers-count');
    if (navSpeakers) navSpeakers.textContent = speakers.length;

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
    const res = await fetch('/api/vendor-requirements?event_id=' + encodeURIComponent(currentEventId));
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
    const res = await fetch('/api/records/vendors?event_id=' + encodeURIComponent(currentEventId));
    const vendors = await res.json();
    if (vendorsCountBadge) vendorsCountBadge.textContent = vendors.length;
    const navVendors = document.getElementById('nav-vendors-count');
    if (navVendors) navVendors.textContent = vendors.length;

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
    const res = await fetch('/api/records/sponsors?event_id=' + encodeURIComponent(currentEventId));
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
    const res = await fetch('/api/event/brief?event_id=' + encodeURIComponent(currentEventId), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date, attendee_count, location, budget, goals, dietary_specs, av_requirements })
    });
    if (res.ok) {
      closeModal('brief-modal');
      await loadEventsList();
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
      body: JSON.stringify({ title, owner, category, deadline, dependencies, event_id: currentEventId })
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
      body: JSON.stringify({ company_name, category, quote_amount, price_per_head, contact_email, details, event_id: currentEventId })
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
      body: JSON.stringify({ category, headcount, specification, unknowns, event_id: currentEventId })
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
loadEventsList().then(() => {
  loadAllRecords();
  loadConversations();
  loadMemories();
});
