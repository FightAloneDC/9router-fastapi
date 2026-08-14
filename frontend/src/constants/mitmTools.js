// MITM-managed IDE tools and their intercepted hosts
export const MITM_TOOLS = {
  antigravity: {
    name: 'Antigravity',
    icon: 'GG',
    color: '#4285F4',
    hosts: [
      'daily-cloudcode-pa.googleapis.com',
      'cloudcode-pa.googleapis.com',
    ],
    description: 'Google Antigravity IDE with MITM',
  },
  copilot: {
    name: 'GitHub Copilot',
    icon: 'GH',
    color: '#000000',
    hosts: ['api.individual.githubcopilot.com'],
    description: 'GitHub Copilot IDE with MITM',
  },
  kiro: {
    name: 'Kiro',
    icon: 'KI',
    color: '#FF9900',
    hosts: [
      'runtime.us-east-1.kiro.dev',
      'q.us-east-1.amazonaws.com',
      'codewhisperer.us-east-1.amazonaws.com',
    ],
    description: 'Kiro IDE with MITM',
  },
  cursor: {
    name: 'Cursor',
    icon: 'CU',
    color: '#00D4AA',
    hosts: ['api2.cursor.sh'],
    description: 'Cursor IDE with MITM (coming soon)',
  },
}
