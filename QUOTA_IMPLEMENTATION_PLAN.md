# Quota Tracker Improvement Plan

## Phase 1: UI/UX Overhaul (Visual Impact)
- [x] 1.1 Ganti provider avatar dari text initials → PNG logo (`/providers/{id}.png`)
- [x] 1.2 Ganti quota bar style → table-based dengan emoji (🟢🟡🔴)
- [x] 1.3 Tambah reset time display format "Today, 12:00 PM"
- [x] 1.4 Ubah layout grid → 2-column (lebih compact)
- [x] 1.5 Color-coded badge untuk low quota cards
- [x] 1.6 Connection status indicator (active/inactive) lebih jelas (2px dot)

## Phase 2: Filtering & Sorting (No Backend Changes)
- [x] 2.1 Provider filter dropdown
- [x] 2.2 Account status filter (All / Active / Inactive)
- [x] 2.3 Quota sort dropdown (Default / % Low-High / % High-Low)
- [x] 2.4 Expiring first toggle (sort by reset time)
- [x] 2.5 Search box cari connection by name
- [x] 2.6 Clear all filters button

## Phase 3: Connection Management (Frontend + Existing Backend API)
- [x] 3.1 Toggle active/inactive per connection (optimistic update)
- [x] 3.2 Edit connection name (modal + optimistic update)
- [x] 3.3 Delete connection (confirmation modal + optimistic remove)
- [x] 3.4 Bulk: "Disable Depleted" (quota ≤ 5%)
- [x] 3.5 Bulk: "Enable All" (re-enable inactive connections)

## Phase 4: Polish
- [x] 4.1 Auto-refresh interval configurable (30s/60s/180s)
- [x] 4.2 Pagination (page size 10/20/50)
- [x] 4.3 Quota caching di localStorage (5 min TTL, background refresh)
- [x] 4.4 Empty state lebih informative (OAuth hint)
- [x] 4.5 Responsive mobile layout (2-col grid, flex-wrap filters)
