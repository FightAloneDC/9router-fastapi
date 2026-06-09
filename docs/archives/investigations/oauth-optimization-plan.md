# OAuth Provider Optimization Plan

## Current State Analysis

### OAuth Providers (7 total)
| Provider | Status | Flow Type | Notes |
|----------|--------|-----------|-------|
| claude | deprecated | authorization_code_pkce | Risk notice |
| antigravity | deprecated, hidden | authorization_code | Google-based |
| codex | deprecated | authorization_code_pkce | Risk notice |
| github | deprecated | device_code | Risk notice |
| cursor | active | import_token | Auto-detect from local IDE |
| kilocode | active | device_code | |
| cline | active | authorization_code | |

### Free Providers (also OAuth-like, 5 total)
| Provider | Status | Flow Type | Notes |
|----------|--------|-----------|-------|
| kiro | active | device_code | AWS Builder ID, IDC, social login |
| qwen | deprecated | device_code | Discontinued by Alibaba |
| gemini-cli | deprecated | authorization_code | Risk notice |
| iflow | hidden | authorization_code | |
| opencode | active | noAuth | Passthrough models |

### Current Issues

1. **Edit Flow Broken**: OAuth connections use `AddKeyModal` for editing, which is designed for API keys. This doesn't work properly because:
   - OAuth connections don't have user-supplied API keys
   - The modal shows irrelevant fields (API Key, Base URL, etc.)
   - No way to edit OAuth-specific fields (priority, proxy pool, name)

2. **ConnectionRow Display**: The current `ConnectionRow` doesn't differentiate between OAuth and API key connections visually:
   - Uses `Key` icon for all connections (should use `Lock` for OAuth)
   - Doesn't show OAuth-specific display name (email/name)
   - Doesn't show token expiry status

3. **Missing OAuth Edit Modal**: No dedicated modal for editing OAuth connection settings (name, priority, proxy pool)

4. **Token Status Not Visible**: No UI indication of:
   - Token expiry time
   - Last refresh time
   - Refresh errors

5. **Inconsistent OAuth Modal Routing**: The provider-specific modal routing in `ProviderDetailPage` is hardcoded with if/else chains

---

## Optimization Plan

### Phase 1: ConnectionRow OAuth Display ✅
**Goal**: Visually distinguish OAuth connections from API key connections

**Changes**:
- `frontend/src/pages/ProviderDetailPage.jsx` (ConnectionRow component)
  - Import `Lock` icon from lucide-react
  - Add `isOAuth` prop to ConnectionRow
  - Use `Lock` icon for OAuth connections, `Key` for API key
  - Show OAuth display name (email → name → displayName → "OAuth Account")
  - Show token expiry badge if `expiresAt` is present

**Reference**: `_reference/components/ConnectionRow.js` lines 68-71, 132-134

### Phase 2: OAuth Edit Modal ✅
**Goal**: Dedicated modal for editing OAuth connection settings

**Changes**:
- `frontend/src/pages/ProviderDetailPage.jsx`
  - Create new `OAuthEditModal` component
  - Fields: Name, Priority, Proxy Pool, isActive toggle
  - No API Key field (OAuth tokens are managed server-side)
  - Show read-only token info: email, expiry, last error

**Reference**: `_reference/components/ConnectionRow.js` edit flow

### Phase 3: ProviderDetailPage OAuth Integration ✅
**Goal**: Integrate OAuth-specific flows into the main page

**Changes**:
- `frontend/src/pages/ProviderDetailPage.jsx`
  - Pass `isOAuth` prop to ConnectionRow (line 2253)
  - Use `OAuthEditModal` instead of `AddKeyModal` for OAuth edit (line 2407)
  - Add OAuth-specific empty state icon (Lock vs Key)
  - Add token refresh status indicator

### Phase 4: OAuth Modal UX Improvements ✅
**Goal**: Better UX for OAuth connection flow

**Changes**:
- `frontend/src/components/OAuthModal.jsx`
  - Add loading states for each step
  - Better error messages
  - Add "Re-authenticate" option for expired tokens
  - Show provider-specific deprecation notices

### Phase 5: Token Status Display ✅
**Goal**: Show OAuth token lifecycle information

**Changes**:
- `frontend/src/pages/ProviderDetailPage.jsx` (ConnectionRow)
  - Show `expiresAt` as countdown timer
  - Show `lastError` if present
  - Show "Refresh Failed" badge if token refresh failed
  - Add "Refresh Now" button for manual token refresh

---

## Implementation Details

### 1. ConnectionRow OAuth Display

```jsx
// In ConnectionRow component
function ConnectionRow({ connection, proxyPools, isOAuth, ... }) {
  const isEmail = (v) => typeof v === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  const displayName = isOAuth
    ? (isEmail(connection.email) ? connection.email 
      : (isEmail(connection.name) ? connection.name 
      : (connection.name || connection.email || connection.displayName || "OAuth Account")))
    : connection.name;

  // Token expiry detection
  const providerSpecific = connection.provider_specific || {};
  const expiresAt = providerSpecific.expiresAt;
  const isExpired = expiresAt && new Date(expiresAt).getTime() < Date.now();

  return (
    <div>
      {/* Icon */}
      {isOAuth ? <Lock size={16} /> : <Key size={16} />}
      
      {/* Display name */}
      <p>{displayName}</p>
      
      {/* Status badges */}
      <Badge>{status}</Badge>
      {isExpired && <Badge variant="danger">Token Expired</Badge>}
      {providerSpecific.lastError && <Badge variant="warning">Refresh Error</Badge>}
    </div>
  );
}
```

### 2. OAuthEditModal Component

```jsx
function OAuthEditModal({ isOpen, connection, proxyPools, onClose, onSave }) {
  const [name, setName] = useState('');
  const [priority, setPriority] = useState(0);
  const [proxyPoolId, setProxyPoolId] = useState('');

  useEffect(() => {
    if (connection) {
      setName(connection.name || '');
      setPriority(connection.priority ?? 0);
      setProxyPoolId(connection.proxy_pool_id || '');
    }
  }, [connection]);

  const handleSave = async () => {
    await providersApi.updateProvider(connection.id, {
      name: name.trim(),
      priority,
      proxyPoolId: proxyPoolId || null,
    });
    onSave();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit OAuth Connection">
      <Input label="Name" value={name} onChange={...} />
      <Input label="Priority" type="number" value={priority} onChange={...} />
      <Select label="Proxy Pool" value={proxyPoolId} onChange={...}>
        {proxyPools.map(pool => <option key={pool.id} value={pool.id}>{pool.name}</option>)}
      </Select>
      
      {/* Read-only info */}
      <div className="text-xs text-zinc-500">
        <p>Email: {connection.email || 'N/A'}</p>
        <p>Token Expiry: {connection.provider_specific?.expiresAt || 'N/A'}</p>
        <p>Last Error: {connection.provider_specific?.lastError || 'None'}</p>
      </div>
    </Modal>
  );
}
```

### 3. ProviderDetailPage Integration

```jsx
// In ProviderDetailPage
const isOAuth = !!OAUTH_PROVIDERS[providerId] || !!FREE_PROVIDERS[providerId];

// ConnectionRow rendering
<ConnectionRow
  connection={conn}
  isOAuth={isOAuth}
  proxyPools={proxyPools}
  ...
/>

// Edit modal routing
{selectedConnection && (
  isOAuth ? (
    <OAuthEditModal
      isOpen={showEditModal}
      connection={selectedConnection}
      proxyPools={proxyPools}
      onClose={() => { setShowEditModal(false); setSelectedConnection(null) }}
      onSave={async () => { setShowEditModal(false); setSelectedConnection(null); await fetchConnections() }}
    />
  ) : (
    <AddKeyModal
      isOpen={showEditModal}
      providerId={providerId}
      editConnection={selectedConnection}
      ...
    />
  )
)}
```

---

## Testing Checklist

- [ ] OAuth connections show Lock icon instead of Key icon
- [ ] OAuth connections display email/name correctly
- [ ] OAuth edit modal opens when clicking Edit on OAuth connection
- [ ] OAuth edit modal can update name, priority, proxy pool
- [ ] Token expiry shows as countdown timer
- [ ] Token refresh errors display correctly
- [ ] Add Connection button opens correct modal for OAuth vs API key
- [ ] Provider-specific modals (Kiro, Cursor, GitLab) still work
- [ ] Deprecated providers show deprecation notice
- [ ] No regression for API key providers

---

## Files to Modify

1. `frontend/src/pages/ProviderDetailPage.jsx`
   - ConnectionRow: Add OAuth display logic
   - Main page: Add OAuthEditModal routing
   - Import Lock icon

2. `frontend/src/components/OAuthEditModal.jsx` (new file)
   - Dedicated OAuth connection edit modal

3. `frontend/src/components/OAuthModal.jsx`
   - UX improvements (optional, lower priority)

---

## Success Criteria

1. OAuth connections are visually distinct from API key connections
2. OAuth connections can be edited (name, priority, proxy pool) without breaking token flow
3. Token status (expiry, errors) is visible in the UI
4. No regression for existing API key providers
5. All OAuth provider flows (Kiro, Cursor, GitLab, generic) continue to work
