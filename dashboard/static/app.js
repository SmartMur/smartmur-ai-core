/* Claw Dashboard — Alpine.js app + page components */

// --- API helpers ---
async function api(path, opts = {}) {
  const url = '/api' + path;
  const config = { headers: { 'Content-Type': 'application/json' }, ...opts };
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }
  const resp = await fetch(url, config);
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

// --- Main app ---
function app() {
  return {
    page: 'home',
    loading: false,
    status: [],
    toasts: [],
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

      window.addEventListener('hashchange', () => {
        this.page = location.hash.replace('#/', '') || 'home';
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
        this.toast('Failed to load status: ' + e.message, 'error');
      }
      this.loading = false;
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
        this.$root.__x.$data.toasts.push({ msg: 'Failed to load jobs', type: 'error' });
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
    profiles: [],

    async load() {
      try {
        this.profiles = await GET('/browser/profiles');
      } catch (e) {
        _toast(this, 'Failed to load browser profiles', 'error');
      }
    },
  };
}

// --- Toast helper (works from nested Alpine components) ---
function _toast(ctx, msg, type) {
  // Walk up to find the root app data
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
  // Fallback: find body's Alpine data
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
