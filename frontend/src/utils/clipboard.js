/**
 * Clipboard helper with fallback for insecure contexts.
 *
 * navigator.clipboard is only available in secure contexts (HTTPS or http://localhost).
 * When accessed via LAN IP/hostname over HTTP, the API is undefined.
 *
 * This helper:
 * 1. Uses navigator.clipboard.writeText() if available (modern API, async)
 * 2. Falls back to document.execCommand('copy') via a temporary textarea (legacy, works in insecure context)
 *
 * Returns a Promise<boolean> — true if copy succeeded, false otherwise.
 */
export async function copyToClipboard(text) {
  // Modern API path (secure context)
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (err) {
      // Fall through to legacy path if writeText rejects (e.g. permission denied)
      console.warn('navigator.clipboard.writeText failed, falling back:', err)
    }
  }

  // Legacy fallback — works in insecure contexts (HTTP over LAN)
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    // Make it invisible but selectable
    textarea.style.position = 'fixed'
    textarea.style.top = '0'
    textarea.style.left = '0'
    textarea.style.width = '2em'
    textarea.style.height = '2em'
    textarea.style.padding = '0'
    textarea.style.border = 'none'
    textarea.style.outline = 'none'
    textarea.style.boxShadow = 'none'
    textarea.style.background = 'transparent'
    textarea.setAttribute('readonly', '')
    document.body.appendChild(textarea)
    textarea.select()
    textarea.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch (err) {
    console.error('Clipboard fallback failed:', err)
    return false
  }
}
