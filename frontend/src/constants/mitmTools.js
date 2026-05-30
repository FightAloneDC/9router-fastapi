// MITM-managed IDE tools and their intercepted hosts
export const MITM_TOOLS = {
  antigravity: {
    name: 'Antigravity',
    icon: 'GG',
    color: '#4285F4',
    hosts: ['antigravity.google', 'codeassist.google.com'],
    description: 'Google Antigravity IDE with MITM',
  },
  copilot: {
    name: 'GitHub Copilot',
    icon: 'GH',
    color: '#000000',
    hosts: ['copilot-proxy.githubusercontent.com', 'api.githubcopilot.com'],
    description: 'GitHub Copilot IDE with MITM',
  },
  kiro: {
    name: 'Kiro',
    icon: 'KI',
    color: '#FF9900',
    hosts: ['kiro.dev', 'api.kiro.dev'],
    description: 'Kiro IDE with MITM',
  },
  cursor: {
    name: 'Cursor',
    icon: 'CU',
    color: '#00D4AA',
    hosts: ['cursor.sh', 'api.cursor.sh'],
    description: 'Cursor IDE with MITM (coming soon)',
  },
}
