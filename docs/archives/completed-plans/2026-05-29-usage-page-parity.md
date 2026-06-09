# Usage Page Enhancement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the FastAPI Usage page (Overview + Details tabs) to feature parity with the Node.js 9router version, plus practical enhancements.

**Architecture:** The FastAPI project already has a fully functional UsagePage with stat cards, charts, tables, and a detail drawer. This plan adds: (1) latency display in Details table, (2) interactive ProviderTopology graph, (3) SSE real-time updates, (4) practical enhancements like CSV export and model filtering.

**Tech Stack:** React 19, Recharts, @xyflow/react (new), FastAPI, SQLAlchemy, PostgreSQL

---

## Gap Analysis: FastAPI vs Node.js

| Feature | Node.js | FastAPI | Status |
|---------|---------|---------|--------|
| Stat cards (4) | Yes | Yes | Done |
| Usage chart (tokens/cost) | Yes | Yes | Done |
| Recent requests table | Yes | Yes | Done |
| Provider status list | Yes | Yes | Done |
| Sortable expandable table (4 views) | Yes | Yes | Done |
| **Provider topology graph** | Yes (ReactFlow) | No | **Missing** |
| **SSE real-time updates** | Yes | No | **Missing** |
| Period selector | Yes | Yes | Done |
| Details filter panel | Yes | Yes | Done |
| Details paginated table | Yes | Yes | Done |
| **Latency columns (TTFT/Total)** | Yes | No (data exists, not shown) | **Missing** |
| Detail drawer (4 JSON sections) | Yes | Yes | Done |
| Thinking content extraction | Yes | Yes | Done |
| **Model filter in Details** | No | No | **Enhancement** |
| **CSV export** | No | No | **Enhancement** |

---

### Task 1: Add Latency Columns to Details Table

**Files:**
- Modify: `frontend/src/pages/UsagePage.jsx:1088-1099` (table header)
- Modify: `frontend/src/pages/UsagePage.jsx:1118-1162` (table rows)

The backend already returns `latency_ttft` and `latency_total` in request details. The data is available on each `detail` object but not displayed in the table.

- [ ] **Step 1: Add Latency column header**

In `UsagePage.jsx`, find the `<thead>` of the Details table (around line 1090). Add a new `<th>` after "Output Tokens" and before "Cost":

```jsx
<th className="text-right px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Latency</th>
```

- [ ] **Step 2: Add Latency cell in table rows**

In the same table's `<tbody>`, find the row rendering (around line 1118). After the Output Tokens `<td>` (line 1138) and before the Cost `<td>` (line 1140), add:

```jsx
<td className="px-4 py-3 text-right text-xs text-zinc-400">
  <div className="flex flex-col gap-0.5">
    <span className="font-mono">{detail.latency_ttft ? `${detail.latency_ttft}ms` : '—'}</span>
    <span className="font-mono text-zinc-500">{detail.latency_total ? `${detail.latency_total}ms` : '—'}</span>
  </div>
</td>
```

- [ ] **Step 3: Update colSpan in loading/empty states**

Find the loading row (`colSpan="8"` around line 1104) and empty row (`colSpan="8"` around line 1113). Update both to `colSpan="9"` to account for the new column.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/UsagePage.jsx
git commit -m "feat(usage): add latency TTFT/Total columns to Details table"
```

---

### Task 2: Add Model Filter to Details Tab

**Files:**
- Modify: `frontend/src/pages/UsagePage.jsx:941-957` (RequestDetailsTab state)
- Modify: `frontend/src/pages/UsagePage.jsx:1032-1083` (filter panel)
- Modify: `frontend/src/api/usage.js` (add model param to getRequestDetails)
- Modify: `backend/app/routers/usage.py:423-505` (request-details endpoint)

- [ ] **Step 1: Add model filter state**

In `RequestDetailsTab`, add `model` to the filters state (around line 953):

```js
const [filters, setFilters] = useState({
  provider: '',
  model: '',
  startDate: '',
  endDate: '',
})
```

- [ ] **Step 2: Add model filter to API call**

In `fetchDetails` callback (around line 971), add model to filterParams:

```js
if (filters.model) filterParams.model = filters.model
```

- [ ] **Step 3: Add model filter input to filter panel**

In the filter card grid (around line 1036), add a model text input after the provider dropdown:

```jsx
<div className="flex flex-col gap-2">
  <label className="text-sm font-medium text-zinc-300">Model</label>
  <input
    type="text"
    placeholder="e.g. gpt-4o"
    value={filters.model}
    onChange={(e) => setFilters({ ...filters, model: e.target.value })}
    className="h-9 px-3 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 w-full"
  />
</div>
```

- [ ] **Step 4: Update hasActiveFilters**

Add `filters.model` to the hasActiveFilters check (around line 1029):

```js
const hasActiveFilters = filters.provider || filters.model || filters.startDate || filters.endDate
```

- [ ] **Step 5: Update clearFilters**

Ensure `handleClearFilters` resets model too (around line 1025):

```js
const handleClearFilters = () => {
  setFilters({ provider: '', model: '', startDate: '', endDate: '' })
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/UsagePage.jsx frontend/src/api/usage.js
git commit -m "feat(usage): add model filter to Details tab"
```

---

### Task 3: Install @xyflow/react for Provider Topology

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install dependency**

```bash
cd /home/mint/dev/9router-fastapi/frontend && npm install @xyflow/react
```

- [ ] **Step 2: Verify installation**

```bash
grep "@xyflow/react" /home/mint/dev/9router-fastapi/frontend/package.json
```

Expected: `"@xyflow/react": "^1.x.x"` in dependencies.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "deps: add @xyflow/react for provider topology visualization"
```

---

### Task 4: Create ProviderTopology Component

**Files:**
- Create: `frontend/src/components/ProviderTopology.jsx`

This component renders an interactive graph with a center "9Router" node and provider nodes arranged in an ellipse around it. Edges are color-coded: green=active, amber=last used, red=error, gray=inactive.

- [ ] **Step 1: Create the ProviderTopology component**

Create `frontend/src/components/ProviderTopology.jsx`:

```jsx
import { useMemo, useState, useEffect, useCallback, useRef } from 'react'
import {
  ReactFlow,
  Handle,
  Position,
  Controls,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { AI_PROVIDERS } from '../constants/providers'

const ACTIVE_TIMEOUT_MS = 60000

function getProviderConfig(providerId) {
  return AI_PROVIDERS[providerId] || { color: '#6b7280', name: providerId }
}

function getProviderImageUrl(providerId) {
  return `/providers/${providerId}.png`
}

function ProviderNode({ data }) {
  const { label, color, imageUrl, textIcon, active } = data
  const [imgError, setImgError] = useState(false)

  return (
    <div
      className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg border-2 transition-all duration-300 bg-zinc-900"
      style={{
        borderColor: active ? color : '#3f3f46',
        boxShadow: active ? `0 0 16px ${color}40` : 'none',
        minWidth: '150px',
      }}
    >
      <Handle type="target" position={Position.Top} id="top" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Bottom} id="bottom" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Left} id="left" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Right} id="right" className="!bg-transparent !border-0 !w-0 !h-0" />

      <div
        className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${color}15` }}
      >
        {!imgError ? (
          <img src={imageUrl} alt={label} className="w-6 h-6 rounded-sm object-contain" onError={() => setImgError(true)} />
        ) : (
          <span className="text-sm font-bold" style={{ color }}>{textIcon}</span>
        )}
      </div>

      <span
        className="text-sm font-medium truncate"
        style={{ color: active ? color : '#e4e4e7' }}
      >
        {label}
      </span>

      {active && (
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: color }} />
          <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: color }} />
        </span>
      )}
    </div>
  )
}

function RouterNode({ data }) {
  return (
    <div className="flex items-center justify-center px-5 py-3 rounded-xl border-2 border-blue-500 bg-blue-500/5 shadow-md min-w-[130px]">
      <Handle type="source" position={Position.Top} id="top" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} id="bottom" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Left} id="left" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Right} id="right" className="!bg-transparent !border-0 !w-0 !h-0" />

      <span className="text-sm font-bold text-blue-400">9Router</span>
      {data.activeCount > 0 && (
        <span className="ml-2 px-1.5 py-0.5 rounded-full bg-blue-500 text-white text-xs font-bold">
          {data.activeCount}
        </span>
      )}
    </div>
  )
}

const nodeTypes = { provider: ProviderNode, router: RouterNode }

function buildLayout(providers, activeSet, lastSet, errorSet) {
  const nodeW = 180
  const nodeH = 30
  const routerW = 120
  const routerH = 44
  const nodeGap = 24
  const count = providers.length

  const minRx = ((nodeW + nodeGap) * count) / (2 * Math.PI)
  const rx = Math.max(320, minRx)
  const ry = Math.max(200, rx * 0.55)

  if (count === 0) {
    return {
      nodes: [{ id: 'router', type: 'router', position: { x: 0, y: 0 }, data: { activeCount: 0 }, draggable: false }],
      edges: [],
    }
  }

  const nodes = []
  const edges = []

  nodes.push({
    id: 'router',
    type: 'router',
    position: { x: -routerW / 2, y: -routerH / 2 },
    data: { activeCount: activeSet.size },
    draggable: false,
  })

  const edgeStyle = (active, last, error) => {
    if (error) return { stroke: '#ef4444', strokeWidth: 2.5, opacity: 0.9 }
    if (active) return { stroke: '#22c55e', strokeWidth: 2.5, opacity: 0.9 }
    if (last) return { stroke: '#f59e0b', strokeWidth: 2, opacity: 0.7 }
    return { stroke: '#3f3f46', strokeWidth: 1, opacity: 0.3 }
  }

  providers.forEach((p, i) => {
    const config = getProviderConfig(p.provider)
    const active = activeSet.has(p.provider?.toLowerCase())
    const last = !active && lastSet.has(p.provider?.toLowerCase())
    const error = !active && errorSet.has(p.provider?.toLowerCase())
    const nodeId = `provider-${p.provider}`

    const angle = -Math.PI / 2 + (2 * Math.PI * i) / count
    const cx = rx * Math.cos(angle)
    const cy = ry * Math.sin(angle)

    let sourceHandle, targetHandle
    if (Math.abs(angle + Math.PI / 2) < Math.PI / 4 || Math.abs(angle - 3 * Math.PI / 2) < Math.PI / 4) {
      sourceHandle = 'top'; targetHandle = 'bottom'
    } else if (Math.abs(angle - Math.PI / 2) < Math.PI / 4) {
      sourceHandle = 'bottom'; targetHandle = 'top'
    } else if (cx > 0) {
      sourceHandle = 'right'; targetHandle = 'left'
    } else {
      sourceHandle = 'left'; targetHandle = 'right'
    }

    nodes.push({
      id: nodeId,
      type: 'provider',
      position: { x: cx - nodeW / 2, y: cy - nodeH / 2 },
      data: {
        label: (config.name !== p.provider ? config.name : null) || p.name || p.provider,
        color: config.color || '#6b7280',
        imageUrl: getProviderImageUrl(p.provider),
        textIcon: config.textIcon || (p.provider || '?').slice(0, 2).toUpperCase(),
        active,
      },
      draggable: false,
    })

    edges.push({
      id: `e-${nodeId}`,
      source: 'router',
      sourceHandle,
      target: nodeId,
      targetHandle,
      animated: active,
      style: edgeStyle(active, last, error, config.color),
    })
  })

  return { nodes, edges }
}

export default function ProviderTopology({ providers = [], activeRequests = [], lastProvider = '', errorProvider = '' }) {
  const activeKey = useMemo(
    () => activeRequests.map((r) => r.provider?.toLowerCase()).filter(Boolean).sort().join(','),
    [activeRequests]
  )
  const lastKey = lastProvider?.toLowerCase() || ''
  const errorKey = errorProvider?.toLowerCase() || ''

  const activeSet = useMemo(() => new Set(activeKey ? activeKey.split(',') : []), [activeKey])
  const lastSet = useMemo(() => new Set(lastKey ? [lastKey] : []), [lastKey])
  const errorSet = useMemo(() => new Set(errorKey ? [errorKey] : []), [errorKey])

  const { nodes, edges } = useMemo(
    () => buildLayout(providers, activeSet, lastSet, errorSet),
    [providers, activeSet, lastKey, errorKey]
  )

  const providersKey = useMemo(
    () => providers.map((p) => p.provider).sort().join(','),
    [providers]
  )

  const rfInstance = useRef(null)
  const containerRef = useRef(null)
  const fitOpts = { padding: 0.2, duration: 200 }

  const onInit = useCallback((instance) => {
    rfInstance.current = instance
    setTimeout(() => instance.fitView(fitOpts), 50)
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      if (rfInstance.current) rfInstance.current.fitView(fitOpts)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (rfInstance.current) {
      const id = setTimeout(() => rfInstance.current.fitView(fitOpts), 50)
      return () => clearTimeout(id)
    }
  }, [nodes.length])

  return (
    <div ref={containerRef} className="h-[320px] w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/30 sm:h-[480px]">
      {providers.length === 0 ? (
        <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
          No providers connected
        </div>
      ) : (
        <ReactFlow
          key={providersKey}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={fitOpts}
          minZoom={0.1}
          maxZoom={2}
          onInit={onInit}
          proOptions={{ hideAttribution: true }}
          panOnDrag
          zoomOnScroll
          zoomOnPinch
          zoomOnDoubleClick
          preventScrolling={false}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Controls showInteractive={false} />
        </ReactFlow>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify the component compiles**

```bash
cd /home/mint/dev/9router-fastapi/frontend && npx vite build 2>&1 | tail -5
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ProviderTopology.jsx
git commit -m "feat(usage): add ProviderTopology interactive graph component"
```

---

### Task 5: Integrate ProviderTopology into Overview Tab

**Files:**
- Modify: `frontend/src/pages/UsagePage.jsx:1-28` (imports)
- Modify: `frontend/src/pages/UsagePage.jsx:1293-1383` (Overview tab layout)

- [ ] **Step 1: Add ProviderTopology import**

At the top of `UsagePage.jsx`, add the import after the existing imports (around line 30):

```js
import ProviderTopology from '../components/ProviderTopology'
```

- [ ] **Step 2: Restructure Overview layout**

Replace the current Overview content section (lines 1300-1381) with a layout that includes the topology. The new layout places the topology full-width between the stat cards and the chart/recent/ provider section:

```jsx
<>
  {/* Stat cards */}
  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <StatCard
      icon={Activity}
      label="Total Requests"
      value={formatNumber(stats?.totalRequests)}
      bgClass="bg-blue-600/20"
      textClass="text-blue-400"
    />
    <StatCard
      icon={ArrowDownLeft}
      label="Input Tokens"
      value={formatTokens(stats?.totalPromptTokens)}
      subValue={formatNumber(stats?.totalPromptTokens)}
      bgClass="bg-indigo-600/20"
      textClass="text-indigo-400"
    />
    <StatCard
      icon={ArrowUpRight}
      label="Output Tokens"
      value={formatTokens(stats?.totalCompletionTokens)}
      subValue={formatNumber(stats?.totalCompletionTokens)}
      bgClass="bg-emerald-600/20"
      textClass="text-emerald-400"
    />
    <StatCard
      icon={DollarSign}
      label="Est. Cost"
      value={formatCost(stats?.totalCost)}
      bgClass="bg-amber-600/20"
      textClass="text-amber-400"
    />
  </div>

  {/* Provider Topology */}
  <ProviderTopology
    providers={stats?.byProvider || []}
  />

  {/* Chart + Recent Requests + Provider Status */}
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <UsageChart
      data={chartData}
      chartMode={chartMode}
      onToggleMode={setChartMode}
    />
    <RecentRequests requests={stats?.recentRequests || []} />
    <ProviderStatus providers={stats?.byProvider || []} />
  </div>

  {/* Table controls: view selector + view mode toggle */}
  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div className="flex items-center gap-2">
      <label className="text-xs text-zinc-500 uppercase tracking-wider">View:</label>
      <select
        value={tableView}
        onChange={(e) => setUrlParam('view', e.target.value)}
        className="h-8 px-3 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-200 cursor-pointer"
      >
        {Object.entries(TABLE_VIEWS).map(([key, def]) => (
          <option key={key} value={key}>{def.label}</option>
        ))}
      </select>
    </div>
    <SegmentedControl
      options={[
        { value: 'tokens', label: 'Tokens' },
        { value: 'cost', label: 'Costs' },
      ]}
      value={viewMode}
      onChange={(v) => setUrlParam('vm', v)}
      size="sm"
    />
  </div>

  {/* Usage table */}
  <UsageTable
    view={tableView}
    data={currentViewData}
    viewMode={viewMode}
    sortBy={sortBy}
    sortOrder={sortOrder}
    onSortChange={handleSortChange}
  />
</>
```

- [ ] **Step 3: Verify in browser**

Start the dev server and check the Overview tab:

```bash
cd /home/mint/dev/9router-fastapi/frontend && npm run dev
```

Expected: Provider topology graph appears between stat cards and chart section. Provider nodes are arranged in an ellipse around the center 9Router node.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/UsagePage.jsx
git commit -m "feat(usage): integrate ProviderTopology into Overview tab"
```

---

### Task 6: Add SSE Endpoint for Real-Time Usage Updates

**Files:**
- Create: `backend/app/routers/usage_stream.py`
- Modify: `backend/app/main.py` (register new router)

- [ ] **Step 1: Create the SSE endpoint**

Create `backend/app/routers/usage_stream.py`:

```python
"""SSE endpoint for real-time usage stats updates."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.database import get_db
from app.models.usage import UsageHistory
from app.routers.auth import get_current_user

router = APIRouter(tags=["usage-stream"])

# Simple in-memory event bus for usage updates
_subscribers: list[asyncio.Queue] = []


def notify_usage_update():
    """Called after each usage save to notify SSE clients."""
    for q in _subscribers:
        try:
            q.put_nowait("update")
        except asyncio.QueueFull:
            pass


async def _event_generator(queue: asyncio.Queue):
    """SSE generator that yields events from the queue."""
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25)
                yield f"event: {event}\ndata: {{}}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive ping
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/usage/stream")
async def usage_stream(
    _user=Depends(get_current_user),
):
    """SSE endpoint for real-time usage updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.append(queue)

    async def generate():
        try:
            async for event in _event_generator(queue):
                yield event
        finally:
            _subscribers.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: Register the router in main.py**

In `backend/app/main.py`, import and include the stream router. Find where other routers are included and add:

```python
from app.routers import usage_stream

app.include_router(usage_stream.router, prefix="/api")
```

- [ ] **Step 3: Hook notify_usage_update into the proxy**

In `backend/app/routers/v1_proxy.py`, after `save_request_usage()` is called (find the line that calls it), add:

```python
from app.routers.usage_stream import notify_usage_update
# ... after save_request_usage() call:
notify_usage_update()
```

- [ ] **Step 4: Verify SSE endpoint works**

```bash
# Start the backend, then:
curl -N -H "Authorization: Bearer <token>" http://localhost:8000/api/usage/stream
```

Expected: SSE stream opens, sends `: keepalive` every 25 seconds.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/usage_stream.py backend/app/main.py backend/app/routers/v1_proxy.py
git commit -m "feat(usage): add SSE endpoint for real-time usage updates"
```

---

### Task 7: Add SSE Client to Frontend for Auto-Refresh

**Files:**
- Modify: `frontend/src/pages/UsagePage.jsx:1200-1262` (UsagePage main component)

- [ ] **Step 1: Add SSE connection to UsagePage**

In the `UsagePage` component, add an SSE connection that auto-refreshes data when updates arrive. Add this after the existing `useEffect` for fetching data (around line 1262):

```js
// SSE for real-time updates
useEffect(() => {
  if (activeTab !== 'overview') return

  const token = localStorage.getItem('token')
  if (!token) return

  let eventSource
  let reconnectTimer

  const connect = () => {
    eventSource = new EventSource(`/api/usage/stream?token=${token}`)

    eventSource.addEventListener('update', () => {
      fetchData(period)
    })

    eventSource.onerror = () => {
      eventSource.close()
      // Reconnect after 5 seconds
      reconnectTimer = setTimeout(connect, 5000)
    }
  }

  connect()

  return () => {
    if (eventSource) eventSource.close()
    if (reconnectTimer) clearTimeout(reconnectTimer)
  }
}, [activeTab, period, fetchData])
```

- [ ] **Step 2: Verify auto-refresh works**

Start the dev server, open the Usage Overview tab, then make an API request through the proxy. The stats should update automatically without manual refresh.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/UsagePage.jsx
git commit -m "feat(usage): add SSE client for real-time auto-refresh on Overview tab"
```

---

### Task 8: Add CSV Export to Details Tab

**Files:**
- Modify: `frontend/src/pages/UsagePage.jsx` (RequestDetailsTab)

- [ ] **Step 1: Add export function**

Add this helper function before the `RequestDetailsTab` component:

```js
function exportToCSV(details) {
  const headers = ['Timestamp', 'Model', 'Provider', 'Input Tokens', 'Output Tokens', 'Cost', 'Latency TTFT', 'Latency Total', 'Status']
  const rows = details.map((d) => [
    new Date(d.timestamp).toISOString(),
    d.model,
    d.provider,
    d.prompt_tokens || 0,
    d.completion_tokens || 0,
    d.cost || 0,
    d.latency_ttft || 0,
    d.latency_total || 0,
    d.status,
  ])

  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `usage-details-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: Add Export button to Details tab**

In the `RequestDetailsTab` filter card (around line 1083), add an Export button alongside Clear Filters:

```jsx
<button
  onClick={() => exportToCSV(details)}
  disabled={details.length === 0}
  className="h-9 px-4 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer w-full"
>
  Export CSV
</button>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/UsagePage.jsx
git commit -m "feat(usage): add CSV export button to Details tab"
```

---

### Task 9: Add Request Detail Cap to Backend

**Files:**
- Modify: `backend/app/services/usage_tracking.py`

The Node.js version caps request_details at 200 records with FIFO deletion. The FastAPI version has no cap, which can lead to unbounded table growth.

- [ ] **Step 1: Add cleanup logic to save_request_detail**

In `backend/app/services/usage_tracking.py`, after the `save_request_detail` function inserts a new record, add cleanup logic:

```python
# Cap request_details at MAX_DETAILS records
MAX_DETAILS = 500

async def cleanup_old_details(db: AsyncSession):
    """Delete oldest request_details if count exceeds MAX_DETAILS."""
    count_result = await db.execute(select(func.count(RequestDetail.id)))
    count = count_result.scalar() or 0
    if count > MAX_DETAILS:
        # Delete oldest records beyond the cap
        excess = count - MAX_DETAILS
        old_records = await db.execute(
            select(RequestDetail.id)
            .order_by(RequestDetail.timestamp.asc())
            .limit(excess)
        )
        old_ids = [r[0] for r in old_records.all()]
        if old_ids:
            await db.execute(
                delete(RequestDetail).where(RequestDetail.id.in_(old_ids))
            )
            await db.commit()
```

Call `await cleanup_old_details(db)` after each `save_request_detail` insertion.

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/usage_tracking.py
git commit -m "feat(usage): cap request_details at 500 records with FIFO cleanup"
```

---

### Task 10: Final Integration Test

- [ ] **Step 1: Start both backend and frontend**

```bash
# Terminal 1: Backend
cd /home/mint/dev/9router-fastapi/backend && uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd /home/mint/dev/9router-fastapi/frontend && npm run dev
```

- [ ] **Step 2: Verify Overview tab**

- Stat cards display correctly
- Provider topology graph shows connected providers
- Chart renders with tokens/cost toggle
- Recent requests table updates
- Provider status list shows all active providers
- Sortable table with 4 view modes works
- SSE auto-refreshes data when new requests arrive

- [ ] **Step 3: Verify Details tab**

- Filter panel has Provider, Model, Start Date, End Date filters
- Model filter works (type "gpt" and see filtered results)
- Latency columns show TTFT and Total milliseconds
- Detail drawer shows all 4 JSON sections
- CSV export downloads a file
- Pagination works correctly

- [ ] **Step 4: Final commit with all changes**

```bash
git add -A
git status
# Review changes, then commit if needed
```
