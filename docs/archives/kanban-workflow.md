# Workflow Kanban Hermes Agent

Dokumen ini menjelaskan cara kerja sistem Kanban di Hermes Agent, berdasarkan workflow yang sudah diterapkan di project 9router-fastapi.

---

## Ringkasan

Hermes Agent menggunakan **Kanban Board** untuk mengatur dan mendistribusikan task ke worker agents. Ada dua role utama:

- **Orchestrator** — mengatur task, membuat card, mendistribusi ke worker (role gw)
- **Worker** — mengerjakan task, delegasi coding ke CLI agents

---

## 1. Arsitektur

```
┌─────────────────────────────────────────────────────────┐
│                    USER (lo)                             │
│              Report bug / request feature                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│               ORCHESTRATOR (Hermes gw)                   │
│  - Terima request dari user                              │
│  - Buat task di kanban board                             │
│  - Assign ke worker profile                              │
│  - Dispatch task                                         │
│  - Monitor progress                                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              KANBAN BOARD (SQLite)                       │
│  - Task queue (ready → running → done/blocked)           │
│  - Dependency tracking (parents)                         │
│  - Priority ordering                                     │
│  - Comment thread per task                               │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              WORKER (Hermes agent)                        │
│  - Baca task body                                        │
│  - Pilih CLI agent berdasarkan task size                 │
│  - Delegasi coding ke CLI agent                          │
│  - Verify hasil                                          │
│  - Report back (complete/block)                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              CLI AGENTS (4 pilihan)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │  Kilo    │ │ OpenCode │ │  Qoder   │ │ OpenClaude│  │
│  │ (free)   │ │ (free)   │ │ ($300)   │ │(unlimited)│  │
│  │ small    │ │ small    │ │ medium   │ │ large     │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Task Lifecycle

```
created → ready → running → done
                    │
                    ▼
                 blocked (butuh input user / review)
                    │
                    ▼
                 unblock → running → done
```

### Status Penjelasan

| Status | Arti |
|--------|------|
| `created` | Task baru dibuat, belum assigned |
| `ready` | Sudah assigned, siap di-dispatch |
| `running` | Sedang dikerjakan worker |
| `done` | Selesai |
| `blocked` | Butuh input user atau review |

---

## 3. Delegation Strategy (4 CLI Agents)

Task coding **WAJIB** didelegasikan ke CLI agent. Worker tidak boleh code langsung.

| Task Size | Agent | Model | Command |
|-----------|-------|-------|---------|
| **Small** (quick fix, 1 file) | Kilo | `kilo/deepseek/deepseek-v4-flash:free` | `kilo run 'task' --model kilo/deepseek/deepseek-v4-flash:free` |
| **Small** (alt) | OpenCode | `opencode/qwen3.6-plus-free` | `opencode run 'task' --model opencode/qwen3.6-plus-free` |
| **Medium** (multi-file, moderate) | Qoder | auto | `qodercli -p 'task'` |
| **Large** (complex, full-stack) | OpenClaude | MIMO (unlimited) | `openclaude -p 'task' --dangerously-skip-permissions --max-turns 50` |

### Kenapa pakai delegation?

1. **Spesialisasi** — setiap agent punya kekuatan berbeda
2. **Cost efficiency** — small task pakai free models, large task pakai unlimited
3. **Parallelisasi** — bisa jalan beberapa agent sekaligus
4. **Quality** — coding agent lebih fokus daripada general Hermes agent

---

## 4. Membuat Task yang Benar

### Task Body Template

```markdown
## Goal
[Deskripsi jelas apa yang harus dikerjakan]

## Delegation
Agent: [kilo|opencode|qoder|openclaude]
Command: terminal(command="[agent] [flags] '[task]'", workdir="/path/to/project")

## Context
- File yang harus dibaca: [list file]
- File yang harus diubah: [list file]
- Constraint: [apa yang TIDAK boleh diubah]

## DO NOT
- Jangan rebuild docker containers (hot-reload enabled)
- Jangan ubah file di luar scope
- Jangan touch file yang tidak disebutkan

## Verification
- [Cara cek apakah task berhasil]
```

### Contoh Task Body (Benar)

```markdown
## Goal
Fix "Base URL is required" error when adding API key to known providers.

## Delegation
Agent: openclaude
Command: terminal(command="openclaude -p 'Fix base URL validation in backend/app/routers/providers.py. Known providers should get default base URL from PROVIDER_DEFAULTS. Only custom providers should require base_url in request.' --dangerously-skip-permissions --max-turns 30", workdir="/home/mint/dev/9router-fastapi")

## Context
- File: backend/app/routers/providers.py line 544
- Function: _get_base_url() at line 86 already has fallback to PROVIDER_DEFAULTS
- Problem: PROVIDER_DEFAULTS might not have all providers listed
- Check PROVIDER_DEFAULTS dict and add missing providers

## DO NOT
- Jangan rebuild docker containers — hot-reload enabled via volume mounts
- Jangan hapus error messages tanpa fix logic-nya
- Jangan touch frontend — ini backend-only fix

## Verification
1. POST /providers/deepseek/connections with only apiKey (no baseUrl)
2. Should succeed without "Base URL is required" error
```

### Contoh Task Body (Salah)

```markdown
## Goal
Fix the base URL issue.

❌ Terlalu vague — worker tidak tahu file mana, line mana, apa yang harus diubah
❌ Tidak ada delegation command — worker code langsung
❌ Tidak ada DO NOT — worker bisa rewrite seluruh file
```

---

## 5. Docker Hot-Reload

Project 9router-fastapi menggunakan Docker Compose dengan hot-reload:

```yaml
# docker-compose.override.yml (auto-loaded)
backend:
  volumes:
    - ./backend:/app        # source mounted
  command: uvicorn ... --reload  # auto-reload on change

frontend:
  volumes:
    - ./frontend:/app       # source mounted
  command: npm run dev       # Vite HMR
```

### Rules

1. **JANGAN** `docker compose up --build` setelah edit file
2. Edit file langsung → auto-reload dalam 1-2 detik
3. **HANYA** rebuild kalau dependency berubah (pyproject.toml, package.json, Dockerfile)
4. Selalu include instruksi ini di task body: `DO NOT rebuild docker containers — hot-reload enabled`

---

## 6. Command Reference

### Orchestrator Commands

```bash
# Buat task
hermes kanban create "Task title" --priority 1 --body "..."
hermes kanban create "Task title" --priority 1 --skill multi-agent-delegation --body "..."

# Assign & dispatch
hermes kanban assign <task_id> <profile>
hermes kanban dispatch --max 1

# Monitor
hermes kanban list
hermes kanban show <task_id>

# Manage
hermes kanban block <task_id> "reason"
hermes kanban archive <task_id>
```

### Worker Commands (via terminal tool)

```bash
# Delegate to Kilo (free, small tasks)
terminal(command="kilo run 'Fix the error handler' --model kilo/deepseek/deepseek-v4-flash:free", workdir="/home/mint/dev/9router-fastapi")

# Delegate to OpenCode (free, small tasks)
terminal(command="opencode run 'Fix the error handler' --model opencode/qwen3.6-plus-free", workdir="/home/mint/dev/9router-fastapi")

# Delegate to Qoder ($300, medium tasks)
terminal(command="qodercli -p 'Refactor the providers backend'", workdir="/home/mint/dev/9router-fastapi")

# Delegate to OpenClaude (unlimited, large tasks)
terminal(command="openclaude -p 'Implement full OAuth flow for all providers' --dangerously-skip-permissions --max-turns 50", workdir="/home/mint/dev/9router-fastapi")
```

---

## 7. Pitfalls yang Harus Dihindari

### Untuk Orchestrator

| Pitfall | Solusi |
|---------|--------|
| Task body vague | Tulis exact file, line, apa yang harus diubah |
| Lupa delegation command | SELALU include `terminal(command=...)` di task body |
| Lupa hot-reload instruction | SELALU tulis "DO NOT rebuild docker containers" |
| Pakai 1 agent aja | Distribute: Kilo/OpenCode (small), Qoder (medium), OpenClaude (large) |
| Pre-research sendiri | Jangan baca source code — bikin task, worker yang riset |
| Manual UI testing | Jangan buka browser — bikin task, worker yang test |

### Untuk Worker

| Pitfall | Solusi |
|---------|--------|
| Code langsung | SELALU delegate ke CLI agent via `terminal()` |
| Rebuild container setelah edit | Edit file langsung — hot-reload jalan otomatis |
| Gak verify hasil | SELALU cek hasil delegation sebelum complete |
| Instruksi vague ke agent | Tulis task spesifik ke CLI agent, bukan "fix it" |

---

## 8. Best Practices

### Task Body Quality

Task body adalah **faktor #1** yang menentukan kualitas output worker. Instruksi yang bagus:

1. **Spesifik** — exact file, line number, function name
2. **Complete** — semua context yang dibutuhkan worker ada di body
3. **Constrained** — DO NOT list untuk mencegah worker rewrite hal yang tidak perlu
4. **Verifiable** — cara cek apakah task berhasil
5. **Delegation command** — exact `terminal(command=...)` call

### Multi-Agent Distribution

```
Request dari user
    │
    ├─ Small fix? ──→ Task dengan Kilo/OpenCode delegation
    ├─ Medium work? ──→ Task dengan Qoder delegation
    └─ Large feature? ──→ Task dengan OpenClaude delegation
```

### Comment Thread

Setiap task punya comment thread untuk komunikasi antar agent:

```python
# Worker kasih update progress
kanban_comment(body="Scanned 5/12 files, found 3 issues")

# Worker minta clarification
kanban_block(reason="Need decision: use IP or user_id for rate limiting?")
```

---

## 9. Contoh Workflow Lengkap

### User: "Bug add API key, base URL error"

1. **Orchestrator** terima request
2. **Orchestrator** bikin task:
   ```
   hermes kanban create "FIX: Base URL validation error" --priority 1 --body "...delegation command...DO NOT rebuild containers..."
   ```
3. **Orchestrator** assign & dispatch
4. **Worker** start, baca task body
5. **Worker** jalankan delegation:
   ```
   terminal(command="openclaude -p 'Fix base URL...' --dangerously-skip-permissions", workdir="...")
   ```
6. **OpenClaude** baca source, fix code, test
7. **OpenClaude** selesai, return hasil ke worker
8. **Worker** verify hasil
9. **Worker** `kanban_complete(summary="Fixed...", metadata={...})`
10. **Orchestrator** monitor, update user

---

## 10. Setup Awal

```bash
# Init kanban board
hermes kanban init
hermes kanban boards create 9router --name "9Router FastAPI"
hermes kanban boards switch 9router

# Install & start gateway (dispatcher)
hermes gateway install
hermes gateway start

# Set iteration budget untuk unlimited model
hermes config set agent.max_turns 500
hermes config set max_iterations 200

# Restart gateway
hermes gateway restart
```

---

*Dokumen ini dibuat berdasarkan workflow aktual di project 9router-fastapi.*
*Terakhir diupdate: 18 Mei 2026*
