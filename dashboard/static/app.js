/* Claw Dashboard v2 — Alpine.js app + page components */

// --- Auth helpers ---
function getAuthHeader() {
  // Session cookies handle auth now; keep Basic fallback for backward compat
  const user = sessionStorage.getItem('claw_user');
  const pass = sessionStorage.getItem('claw_pass');
  if (!user || !pass) return null;
  return 'Basic ' + btoa(user + ':' + pass);
}

function clearAuth() {
  sessionStorage.removeItem('claw_user');
  sessionStorage.removeItem('claw_pass');
}

function isLoggedIn() {
  // With cookie auth, we optimistically assume logged in unless kicked out
  return true;
}

// --- API helpers ---
async function api(path, opts = {}) {
  const url = '/api' + path;
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  const auth = getAuthHeader();
  if (auth) headers['Authorization'] = auth;
  const config = { ...opts, headers };
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }
  const resp = await fetch(url, config);
  if (resp.status === 401) {
    clearAuth();
    window.location.href = '/login.html';
    throw new Error('Authentication required');
  }
  if (resp.status === 204) return null;
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

const GET = (path) => api(path);
const POST = (path, body) => api(path, { method: 'POST', body });
const DEL = (path) => api(path, { method: 'DELETE' });

// --- Theme ---
function getTheme() {
  return localStorage.getItem('claw_theme') || 'dark';
}

function setTheme(theme) {
  localStorage.setItem('claw_theme', theme);
  document.documentElement.setAttribute('data-theme', theme);
}

// Apply saved theme on load
(function() {
  const saved = getTheme();
  if (saved === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();

// --- Time formatting ---
function timeAgo(ts) {
  if (!ts) return '';
  const now = Date.now() / 1000;
  const diff = now - ts;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

function formatTime(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

// --- Main app ---
function app() {
  return {
    page: 'home',
    loading: false,
    status: [],
    toasts: [],
    unreadCount: 0,
    theme: getTheme(),
    navMap: {
      channels: 'msg',
      ssh: 'ssh',
      cron: 'cron',
      workflows: 'workflows',
      memory: 'memory',
      skills: 'skills',
      vault: 'vault',
      watchers: 'watchers',
      audit: 'audit',
      browser: 'browser',
    },

    init() {
      // Hash routing
      const hash = location.hash.replace('#/', '') || 'home';
      this.page = hash;
      this.loadStatus();
      this.pollUnread();

      window.addEventListener('hashchange', () => {
        this.page = location.hash.replace('#/', '') || 'home';
      });
    },

    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      setTheme(this.theme);
    },

    doLogout() {
      fetch('/logout', { method: 'POST' }).then(() => {
        clearAuth();
        window.location.href = '/login.html';
      });
    },

    go(p) {
      this.page = p;
      location.hash = '#/' + p;
    },

    async loadStatus() {
      this.loading = true;
      try {
        const data = await GET('/status');
        this.status = data.subsystems;
      } catch (e) {
        // If auth fails, redirect handled by api()
        if (!e.message.includes('Authentication')) {
          this.toast('Failed to load status: ' + e.message, 'error');
        }
      }
      this.loading = false;
    },

    async pollUnread() {
      try {
        const data = await GET('/notifications/unread');
        this.unreadCount = data.count;
      } catch (e) { /* ignore */ }
      // Poll every 30 seconds
      setTimeout(() => this.pollUnread(), 30000);
    },

    toast(msg, type = 'info') {
      this.toasts.push({ msg, type });
    },
  };
}

// --- Page components ---

function cronPage() {
  return {
    jobs: [],
    showAdd: false,
    showLogs: false,
    logs: [],
    newJob: { name: '', schedule: '', job_type: 'shell', command: '' },

    async load() {
      try {
        this.jobs = await GET('/cron/jobs');
      } catch (e) {
        _toast(this, 'Failed to load jobs', 'error');
      }
    },

    async addJob() {
      try {
        await POST('/cron/jobs', this.newJob);
        this.showAdd = false;
        this.newJob = { name: '', schedule: '', job_type: 'shell', command: '' };
        await this.load();
        _toast(this, 'Job created', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async deleteJob(id) {
      if (!confirm('Delete this job?')) return;
      try {
        await DEL('/cron/jobs/' + id);
        await this.load();
        _toast(this, 'Job deleted', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async toggleJob(j) {
      try {
        const action = j.enabled ? 'disable' : 'enable';
        await POST('/cron/jobs/' + j.id + '/' + action);
        await this.load();
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async runJob(id) {
      try {
        await POST('/cron/jobs/' + id + '/run');
        await this.load();
        _toast(this, 'Job executed', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async viewLogs(id) {
      try {
        this.logs = await GET('/cron/jobs/' + id + '/logs');
        this.showLogs = true;
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

function msgPage() {
  return {
    channels: [],
    profiles: [],
    sendForm: { channel: '', target: '', message: '' },

    async load() {
      try {
        this.channels = await GET('/msg/channels');
        this.profiles = await GET('/msg/profiles');
        const configured = this.channels.find(c => c.configured);
        if (configured) this.sendForm.channel = configured.name;
      } catch (e) {
        _toast(this, 'Failed to load messaging', 'error');
      }
    },

    async send() {
      try {
        const res = await POST('/msg/send', this.sendForm);
        _toast(this, res.ok ? 'Message sent' : ('Send failed: ' + res.error), res.ok ? 'success' : 'error');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async testChannel(name) {
      try {
        const res = await POST('/msg/test/' + name);
        _toast(this, res.ok ? 'Test sent to ' + name : ('Test failed: ' + res.error), res.ok ? 'success' : 'error');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async sendProfile(name) {
      try {
        await POST('/msg/profiles/' + name + '/send', { message: 'Claw dashboard test' });
        _toast(this, 'Sent via profile: ' + name, 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

function sshPage() {
  return {
    hosts: [],
    results: [],
    healthResults: [],
    runForm: { target: 'all', command: 'uptime' },

    async load() {
      try {
        this.hosts = await GET('/ssh/hosts');
      } catch (e) {
        _toast(this, 'Failed to load hosts', 'error');
      }
    },

    async run() {
      try {
        this.results = await POST('/ssh/run', this.runForm);
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async runHealth() {
      _toast(this, 'Running health check...', 'info');
      try {
        this.healthResults = await GET('/ssh/health');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

function workflowPage() {
  return {
    workflows: [],
    detail: null,
    runResults: [],

    async load() {
      try {
        this.workflows = await GET('/workflows');
      } catch (e) {
        _toast(this, 'Failed to load workflows', 'error');
      }
    },

    async inspect(name) {
      try {
        this.detail = await GET('/workflows/' + name);
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async validate(name) {
      try {
        const res = await POST('/workflows/' + name + '/validate');
        _toast(this, res.valid ? 'Valid' : ('Errors: ' + res.errors.join(', ')),
               res.valid ? 'success' : 'error');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async runDry(name) {
      try {
        this.runResults = await POST('/workflows/' + name + '/run', { dry_run: true });
        _toast(this, 'Dry run complete', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async runLive(name) {
      if (!confirm('Run workflow "' + name + '" for real?')) return;
      try {
        this.runResults = await POST('/workflows/' + name + '/run', { dry_run: false });
        _toast(this, 'Workflow complete', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

function memoryPage() {
  return {
    memories: [],
    stats: null,
    searchQ: '',
    showAdd: false,
    newMem: { key: '', value: '', category: 'fact', tagsStr: '' },

    async load() {
      try {
        this.memories = await GET('/memory');
      } catch (e) {
        _toast(this, 'Failed to load memories', 'error');
      }
    },

    async search() {
      if (!this.searchQ.trim()) { return this.load(); }
      try {
        this.memories = await GET('/memory/search?q=' + encodeURIComponent(this.searchQ));
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async loadStats() {
      try {
        this.stats = await GET('/memory/stats');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async add() {
      try {
        const tags = this.newMem.tagsStr ? this.newMem.tagsStr.split(',').map(t => t.trim()) : [];
        await POST('/memory', {
          key: this.newMem.key,
          value: this.newMem.value,
          category: this.newMem.category,
          tags,
        });
        this.showAdd = false;
        this.newMem = { key: '', value: '', category: 'fact', tagsStr: '' };
        await this.load();
        _toast(this, 'Memory saved', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async forget(key, category) {
      if (!confirm('Delete memory "' + key + '"?')) return;
      try {
        await DEL('/memory/' + encodeURIComponent(key) + '?category=' + encodeURIComponent(category));
        await this.load();
        _toast(this, 'Memory deleted', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

function skillsPage() {
  return {
    skills: [],
    detail: null,
    runResult: null,

    async load() {
      try {
        this.skills = await GET('/skills');
      } catch (e) {
        _toast(this, 'Failed to load skills', 'error');
      }
    },

    async info(name) {
      try {
        this.detail = await GET('/skills/' + name);
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async runSkill(name) {
      try {
        this.runResult = await POST('/skills/' + name + '/run', { args: {} });
        _toast(this, 'Skill executed', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

function auditPage() {
  return {
    entries: [],
    searchQ: '',

    async load() {
      try {
        this.entries = await GET('/audit/tail?n=50');
      } catch (e) {
        _toast(this, 'Failed to load audit log', 'error');
      }
    },

    async search() {
      if (!this.searchQ.trim()) { return this.load(); }
      try {
        this.entries = await GET('/audit/search?q=' + encodeURIComponent(this.searchQ));
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

function vaultPage() {
  return {
    vaultStatus: { initialized: false, key_count: 0 },
    keys: [],

    async load() {
      try {
        this.vaultStatus = await GET('/vault/status');
        this.keys = await GET('/vault/keys');
      } catch (e) {
        _toast(this, 'Failed to load vault', 'error');
      }
    },
  };
}

function watcherPage() {
  return {
    rules: [],

    async load() {
      try {
        this.rules = await GET('/watchers/rules');
      } catch (e) {
        _toast(this, 'Failed to load watchers', 'error');
      }
    },
  };
}

function browserPage() {
  return {
    engineStatus: {
      engine_online: false,
      status: 'unknown',
      uptime_seconds: 0,
      active_sessions: 0,
      sessions: [],
      profiles: [],
      error: '',
    },
    navForm: { url: '', profile: 'default' },
    navResult: null,
    screenshotData: null,

    async load() {
      try {
        this.engineStatus = await GET('/browser/status');
      } catch (e) {
        this.engineStatus.engine_online = false;
        this.engineStatus.error = e.message;
        _toast(this, 'Failed to load browser engine status', 'error');
      }
    },

    formatUptime(seconds) {
      if (!seconds) return '-';
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      const s = Math.floor(seconds % 60);
      if (h > 0) return h + 'h ' + m + 'm';
      if (m > 0) return m + 'm ' + s + 's';
      return s + 's';
    },

    async doNavigate() {
      if (!this.navForm.url.trim()) return;
      this.screenshotData = null;
      try {
        this.navResult = await POST('/browser/navigate', {
          url: this.navForm.url,
          profile: this.navForm.profile,
        });
        if (this.navResult.ok) {
          _toast(this, 'Navigated to ' + this.navResult.title, 'success');
        } else {
          _toast(this, 'Navigation failed: ' + (this.navResult.error || 'unknown'), 'error');
        }
        await this.load();
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async doScreenshot() {
      if (!this.navForm.url.trim()) return;
      try {
        const res = await POST('/browser/screenshot', {
          url: this.navForm.url,
          profile: this.navForm.profile,
          full_page: true,
        });
        if (res.ok) {
          this.navResult = { url: res.url, title: res.title, ok: true };
          this.screenshotData = res.image_base64;
          _toast(this, 'Screenshot captured', 'success');
        } else {
          _toast(this, 'Screenshot failed: ' + (res.error || 'unknown'), 'error');
        }
        await this.load();
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async screenshotSession(profile) {
      try {
        const res = await POST('/browser/screenshot', { profile, full_page: true });
        if (res.ok) {
          this.screenshotData = res.image_base64;
          _toast(this, 'Screenshot captured', 'success');
        } else {
          _toast(this, 'Screenshot failed: ' + (res.error || 'unknown'), 'error');
        }
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async closeSession(profile) {
      if (!confirm('Close browser session "' + profile + '"?')) return;
      try {
        await DEL('/browser/sessions/' + profile);
        _toast(this, 'Session closed', 'success');
        await this.load();
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async closeAllSessions() {
      if (!confirm('Close all browser sessions?')) return;
      try {
        await DEL('/browser/sessions');
        _toast(this, 'All sessions closed', 'success');
        await this.load();
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },
  };
}

// ============================================
// NEW: Chat page component
// ============================================

function chatPage() {
  return {
    conversations: [],
    currentConv: null,
    messages: [],
    inputMsg: '',
    streaming: false,
    streamingText: '',

    async load() {
      try {
        this.conversations = await GET('/chat/conversations');
      } catch (e) {
        _toast(this, 'Failed to load conversations', 'error');
      }
    },

    async newConversation() {
      try {
        const conv = await POST('/chat/conversations');
        this.conversations.unshift(conv);
        this.selectConversation(conv.id);
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async selectConversation(cid) {
      try {
        const conv = await GET('/chat/conversations/' + cid);
        this.currentConv = conv;
        this.messages = conv.messages || [];
        this.$nextTick(() => this.scrollToBottom());
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async deleteConversation(cid) {
      if (!confirm('Delete this conversation?')) return;
      try {
        await DEL('/chat/conversations/' + cid);
        this.conversations = this.conversations.filter(c => c.id !== cid);
        if (this.currentConv && this.currentConv.id === cid) {
          this.currentConv = null;
          this.messages = [];
        }
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async sendMessage() {
      if (!this.inputMsg.trim() || this.streaming) return;

      const msg = this.inputMsg.trim();
      this.inputMsg = '';

      // Add user message to UI
      this.messages.push({ role: 'user', content: msg, ts: Date.now() / 1000 });
      this.$nextTick(() => this.scrollToBottom());

      // Start streaming
      this.streaming = true;
      this.streamingText = '';

      const cid = this.currentConv ? this.currentConv.id : '';
      const params = new URLSearchParams({ message: msg });
      if (cid) params.set('conversation_id', cid);

      try {
        const auth = getAuthHeader();
        const headers = {};
        if (auth) headers['Authorization'] = auth;

        const resp = await fetch('/api/chat/stream?' + params.toString(), { headers });

        if (resp.status === 401) {
          clearAuth();
          window.location.href = '/login.html';
          return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'meta') {
                if (!this.currentConv) {
                  this.currentConv = { id: data.conversation_id };
                  await this.load(); // Refresh sidebar
                }
              } else if (data.type === 'chunk') {
                this.streamingText += data.content;
                this.$nextTick(() => this.scrollToBottom());
              } else if (data.type === 'done') {
                // Add complete assistant message
                this.messages.push({
                  role: 'assistant',
                  content: this.streamingText,
                  ts: Date.now() / 1000,
                });
                this.streamingText = '';
                this.streaming = false;
                this.$nextTick(() => this.scrollToBottom());
                await this.load(); // Refresh sidebar for title update
              }
            } catch (e) { /* skip parse errors */ }
          }
        }
      } catch (e) {
        _toast(this, 'Stream error: ' + e.message, 'error');
        this.streaming = false;
        this.streamingText = '';
      }
    },

    scrollToBottom() {
      const el = document.getElementById('chatMessages');
      if (el) el.scrollTop = el.scrollHeight;
    },

    formatTime(ts) {
      return timeAgo(ts);
    },
  };
}

// ============================================
// NEW: Notifications page component
// ============================================

function notificationsPage() {
  return {
    notifications: [],
    unreadOnly: false,

    async load() {
      try {
        const qs = this.unreadOnly ? '?unread_only=true' : '';
        this.notifications = await GET('/notifications' + qs);
      } catch (e) {
        _toast(this, 'Failed to load notifications', 'error');
      }
    },

    async markRead(nid) {
      try {
        await POST('/notifications/' + nid + '/read');
        const n = this.notifications.find(x => x.id === nid);
        if (n) n.read = true;
        // Update badge
        _updateUnreadBadge(this);
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async markAllRead() {
      try {
        await POST('/notifications/read-all');
        this.notifications.forEach(n => n.read = true);
        _updateUnreadBadge(this);
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async deleteNotification(nid) {
      try {
        await DEL('/notifications/' + nid);
        this.notifications = this.notifications.filter(n => n.id !== nid);
        _updateUnreadBadge(this);
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    formatTime(ts) {
      return timeAgo(ts);
    },

    levelIcon(level) {
      const map = { info: 'i', warning: '!', error: 'x', success: '+' };
      return map[level] || 'i';
    },
  };
}

function _updateUnreadBadge(ctx) {
  // Trigger a re-poll on the main app
  GET('/notifications/unread').then(data => {
    let el = document.body;
    if (el && el._x_dataStack) {
      for (const d of el._x_dataStack) {
        if ('unreadCount' in d) {
          d.unreadCount = data.count;
          return;
        }
      }
    }
  }).catch(() => {});
}

// ============================================
// NEW: Jobs page component
// ============================================

function jobsPage() {
  return {
    jobs: [],
    filter: '',
    sseSource: null,

    async load() {
      try {
        const qs = this.filter ? '?status=' + this.filter : '';
        this.jobs = await GET('/jobs' + qs);
      } catch (e) {
        _toast(this, 'Failed to load jobs', 'error');
      }
    },

    async createJob() {
      const name = prompt('Job name:');
      if (!name) return;
      try {
        await POST('/jobs', { name, job_type: 'shell' });
        await this.load();
        _toast(this, 'Job created', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    async deleteJob(jid) {
      if (!confirm('Delete this job?')) return;
      try {
        await DEL('/jobs/' + jid);
        await this.load();
        _toast(this, 'Job deleted', 'success');
      } catch (e) {
        _toast(this, e.message, 'error');
      }
    },

    statusTag(s) {
      const map = { queued: '', running: 'tag-yellow', completed: 'tag-green', failed: 'tag-red' };
      return map[s] || '';
    },

    formatTime(ts) {
      return ts ? timeAgo(ts) : '-';
    },

    formatDuration(d) {
      if (!d) return '-';
      if (d < 1) return (d * 1000).toFixed(0) + 'ms';
      if (d < 60) return d.toFixed(1) + 's';
      return (d / 60).toFixed(1) + 'm';
    },

    jobCounts() {
      const counts = { queued: 0, running: 0, completed: 0, failed: 0 };
      this.jobs.forEach(j => { counts[j.status] = (counts[j.status] || 0) + 1; });
      return counts;
    },
  };
}

// ============================================
// NEW: Settings page component
// ============================================

function settingsPage() {
  return {
    overview: null,

    async load() {
      try {
        this.overview = await GET('/settings/overview');
      } catch (e) {
        _toast(this, 'Failed to load settings', 'error');
      }
    },
  };
}

// --- Toast helper (works from nested Alpine components) ---
function _toast(ctx, msg, type) {
  let el = ctx.$el;
  while (el && !el._x_dataStack) {
    el = el.parentElement;
  }
  if (el && el._x_dataStack) {
    for (const data of el._x_dataStack) {
      if (data.toasts) {
        data.toasts.push({ msg, type });
        return;
      }
    }
  }
  const body = document.body;
  if (body._x_dataStack) {
    for (const data of body._x_dataStack) {
      if (data.toasts) {
        data.toasts.push({ msg, type });
        return;
      }
    }
  }
}
