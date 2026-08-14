import { useState } from 'react'
import { Copy, Check, ExternalLink, Boxes, MessageSquare, Image, Volume2, Mic, Binary, Search, Globe, ArrowUpDown } from 'lucide-react'
import { SKILLS, SKILLS_TREE_URL, getSkillRawUrl, getSkillBlobUrl } from '../constants/skills'
import Card, { CardContent } from '../components/ui/Card'
import Badge from '../components/ui/Badge'

const ICON_MAP = {
  Hub: Boxes, MessageSquare, Image, Volume2, Mic, Binary, Search, Globe,
  ArrowUpDown,
}

function CopyButton({ value, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="px-2.5 py-1 rounded-md bg-blue-600 text-white text-[11px] font-medium hover:bg-blue-700 transition-colors shrink-0 inline-flex items-center gap-1"
      title={value}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      {copied ? 'Copied!' : label}
    </button>
  )
}

function SkillRow({ skill }) {
  const url = getSkillRawUrl(skill.id)
  const Icon = ICON_MAP[skill.icon] || Hub

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-xl border transition-colors ${
        skill.isEntry
          ? 'border-blue-500/40 bg-blue-500/5'
          : 'border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50'
      }`}
    >
      <div
        className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
          skill.isEntry ? 'bg-blue-600 text-white' : 'bg-blue-600/10 text-blue-400'
        }`}
      >
        <Icon size={18} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-semibold text-sm text-zinc-100">{skill.name}</h3>
          {skill.isEntry && <Badge variant="primary" size="sm">START HERE</Badge>}
          {skill.endpoint && (
            <Badge variant="default" size="sm">
              <code className="text-[10px]">{skill.endpoint}</code>
            </Badge>
          )}
        </div>
        <p className="text-xs text-zinc-400 mt-0.5">{skill.description}</p>
        <a
          href={getSkillBlobUrl(skill.id)}
          target="_blank"
          rel="noreferrer"
          className="text-[11px] text-zinc-500 hover:text-blue-400 mt-1 inline-flex items-center gap-1 break-all"
        >
          {url}
          <ExternalLink size={10} />
        </a>
      </div>

      <CopyButton value={url} />
    </div>
  )
}

export default function SkillsPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Quick start card */}
      <Card>
        <CardContent>
          <div className="text-xs text-zinc-500 mb-2">
            Paste this to your AI agent:
          </div>
          <div className="px-3 py-2 rounded-lg bg-zinc-800 font-mono text-[12px] text-zinc-200 break-all">
            Read this skill and use it: {getSkillRawUrl('9router')}
          </div>
        </CardContent>
      </Card>

      {/* Skill list */}
      <div className="space-y-2">
        {SKILLS.map((skill) => (
          <SkillRow key={skill.id} skill={skill} />
        ))}
      </div>

      {/* GitHub link */}
      <Card>
        <CardContent>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">
                More on GitHub
              </h2>
              <p className="text-xs text-zinc-400 mt-0.5">
                Browse source, README, and examples.
              </p>
            </div>
            <a
              href={SKILLS_TREE_URL}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-blue-400 hover:underline inline-flex items-center gap-1"
            >
              View on GitHub
              <ExternalLink size={14} />
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
