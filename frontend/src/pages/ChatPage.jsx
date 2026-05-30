import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Send, Loader2, Bot, User, Settings2, Copy, Check,
  Square, RefreshCw, Trash2, MessageSquare, Plus, PanelLeft,
  Pencil, X,
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { chatApi } from '../api/chat'
import { copyToClipboard } from '../utils/clipboard'


export default function ChatPage() {
  const token = useAuthStore(s => s.token)

  // Conversation state
  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [loadingConversations, setLoadingConversations] = useState(false)

  // Chat state
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [availableModels, setAvailableModels] = useState([])
  const [loadingModels, setLoadingModels] = useState(true)
  const [streaming, setStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState('')
  const [temperature, setTemperature] = useState(0.7)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [showSettings, setShowSettings] = useState(false)
  const [copiedIdx, setCopiedIdx] = useState(null)
  const [error, setError] = useState('')

  // Editing state
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')

  const messagesEndRef = useRef(null)
  const abortControllerRef = useRef(null)
  const textareaRef = useRef(null)

  // Fetch models
  useEffect(() => {
    setLoadingModels(true)
    fetch('/v1/models', {
      headers: { 'Authorization': `Bearer ${token || ''}` },
    })
      .then(r => r.json())
      .then(data => {
        const excludePattern = /embed|rerank|tts|stt|robot|voice|deepgram/i
        const models = (data.data || []).filter(m => {
          if (excludePattern.test(m.id)) return false
          const type = m.type || ''
          return type === 'llm' || type === 'chat' || type === 'combo' || !type
        })
        setAvailableModels(models)
        if (models.length > 0 && !selectedModel) {
          setSelectedModel(models[0].id)
        }
      })
      .catch(() => {})
      .finally(() => setLoadingModels(false))
  }, [token])

  // Fetch conversations list
  const fetchConversations = useCallback(async () => {
    setLoadingConversations(true)
    try {
      const res = await chatApi.getConversations()
      console.log('[chat] conversations loaded:', res.data)
      setConversations(res.data || [])
    } catch (e) {
      console.error('[chat] fetchConversations error:', e)
    } finally {
      setLoadingConversations(false)
    }
  }, [])

  useEffect(() => { fetchConversations() }, [fetchConversations])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamContent])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  // Load conversation
  const loadConversation = useCallback(async (id) => {
    try {
      const res = await chatApi.getConversation(id)
      const conv = res.data
      setMessages(conv.messages || [])
      setCurrentConversationId(id)
      if (conv.model) setSelectedModel(conv.model)
    } catch {}
  }, [])

  // New chat
  const handleNewChat = () => {
    setCurrentConversationId(null)
    setMessages([])
    setStreamContent('')
    setError('')
  }

  // Save messages to backend
  const saveMessage = useCallback(async (conversationId, role, content) => {
    try {
      await chatApi.saveMessage(conversationId, { role, content })
    } catch {}
  }, [])

  // Update conversation title
  const updateTitle = useCallback(async (id, title) => {
    try {
      await chatApi.updateConversation(id, { title })
      fetchConversations()
    } catch {}
  }, [fetchConversations])

  // Delete conversation
  const handleDeleteConversation = useCallback(async (id) => {
    try {
      await chatApi.deleteConversation(id)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (currentConversationId === id) {
        handleNewChat()
      }
    } catch {}
  }, [currentConversationId])

  // Start editing title
  const startEditTitle = (id, title) => {
    setEditingId(id)
    setEditTitle(title)
  }

  // Save edited title
  const saveEditTitle = () => {
    if (editingId && editTitle.trim()) {
      updateTitle(editingId, editTitle.trim())
    }
    setEditingId(null)
    setEditTitle('')
  }

  // Send message
  const handleSend = useCallback(async () => {
    if (!input.trim() || !selectedModel || streaming) return

    const userContent = input.trim()
    const userMessage = { role: 'user', content: userContent }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setInput('')
    setError('')
    setStreaming(true)
    setStreamContent('')

    // Auto-create conversation if needed
    let convId = currentConversationId
    if (!convId) {
      try {
        const title = userContent.length > 50 ? userContent.slice(0, 50) + '...' : userContent
        console.log('[chat] creating conversation:', title, selectedModel)
        const res = await chatApi.createConversation({ title, model: selectedModel })
        console.log('[chat] conversation created:', res.data)
        convId = res.data.id
        setCurrentConversationId(convId)
        fetchConversations()
      } catch (e) {
        console.error('[chat] createConversation error:', e)
      }
    }

    // Save user message
    if (convId) {
      saveMessage(convId, 'user', userContent)
    }

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    try {
      const res = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token || ''}`,
        },
        body: JSON.stringify({
          model: selectedModel,
          messages: newMessages.map(m => ({ role: m.role, content: m.content })),
          temperature,
          max_tokens: maxTokens,
          stream: true,
        }),
        signal: abortController.signal,
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.error?.message || `HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data === '[DONE]') continue
            try {
              const parsed = JSON.parse(data)
              const content = parsed.choices?.[0]?.delta?.content || ''
              fullContent += content
              setStreamContent(fullContent)
            } catch {}
          }
        }
      }

      if (fullContent) {
        setMessages([...newMessages, { role: 'assistant', content: fullContent }])
        // Save assistant message
        if (convId) {
          saveMessage(convId, 'assistant', fullContent)
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message)
      }
    } finally {
      setStreaming(false)
      setStreamContent('')
      abortControllerRef.current = null
    }
  }, [input, selectedModel, messages, temperature, maxTokens, token, streaming, currentConversationId, fetchConversations, saveMessage])

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleCopy = (content, idx) => {
    copyToClipboard(content).then(ok => {
      if (ok) {
        setCopiedIdx(idx)
        setTimeout(() => setCopiedIdx(null), 2000)
      }
    })
  }

  const handleClear = () => {
    setMessages([])
    setStreamContent('')
    setError('')
  }

  const handleRetry = (msgIdx) => {
    const userMsgIdx = messages.findLastIndex((m, i) => i < msgIdx && m.role === 'user')
    if (userMsgIdx >= 0) {
      const newMessages = messages.slice(0, userMsgIdx)
      const userMsg = messages[userMsgIdx]
      setMessages(newMessages)
      setInput(userMsg.content)
    }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] -my-4 lg:-my-6 -mx-4 lg:-mx-6">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-900/50 flex flex-col">
          <div className="p-2 border-b border-zinc-800">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 cursor-pointer"
            >
              <Plus size={14} />
              New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
            {loadingConversations ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 size={14} className="animate-spin text-zinc-600" />
              </div>
            ) : conversations.length === 0 ? (
              <p className="text-xs text-zinc-600 text-center py-4">No conversations yet</p>
            ) : (
              conversations.map(conv => (
                <div
                  key={conv.id}
                  className={`group flex items-center gap-1 px-2 py-1.5 rounded-lg cursor-pointer ${
                    currentConversationId === conv.id
                      ? 'bg-zinc-800 text-zinc-200'
                      : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-300'
                  }`}
                  onClick={() => loadConversation(conv.id)}
                >
                  <MessageSquare size={12} className="shrink-0" />
                  {editingId === conv.id ? (
                    <div className="flex-1 flex items-center gap-1 min-w-0">
                      <input
                        value={editTitle}
                        onChange={e => setEditTitle(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') saveEditTitle(); if (e.key === 'Escape') setEditingId(null) }}
                        onBlur={saveEditTitle}
                        className="flex-1 min-w-0 bg-zinc-700 border border-zinc-600 rounded px-1.5 py-0.5 text-xs text-zinc-200"
                        autoFocus
                        onClick={e => e.stopPropagation()}
                      />
                      <button
                        onClick={e => { e.stopPropagation(); setEditingId(null) }}
                        className="p-0.5 text-zinc-500 hover:text-zinc-300 cursor-pointer"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className="flex-1 min-w-0 truncate text-xs">{conv.title}</span>
                      <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
                        <button
                          onClick={e => { e.stopPropagation(); startEditTitle(conv.id, conv.title) }}
                          className="p-0.5 text-zinc-600 hover:text-zinc-300 cursor-pointer"
                        >
                          <Pencil size={10} />
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); handleDeleteConversation(conv.id) }}
                          className="p-0.5 text-zinc-600 hover:text-red-400 cursor-pointer"
                        >
                          <Trash2 size={10} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="shrink-0 flex items-center justify-between gap-3 px-4 py-2 border-b border-zinc-800 bg-zinc-900/50">
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 cursor-pointer"
            >
              <PanelLeft size={14} />
            </button>
            <select
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              disabled={loadingModels}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-xs text-zinc-200 max-w-[200px] truncate"
            >
              {loadingModels ? (
                <option>Loading...</option>
              ) : availableModels.length === 0 ? (
                <option>No models</option>
              ) : (
                availableModels.map(m => (
                  <option key={m.id} value={m.id}>{m.id}</option>
                ))
              )}
            </select>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${showSettings ? 'bg-zinc-700 text-zinc-200' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'}`}
            >
              <Settings2 size={14} />
            </button>
            <button
              onClick={handleClear}
              disabled={messages.length === 0}
              className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="shrink-0 flex items-center gap-4 px-4 py-2 border-b border-zinc-800 bg-zinc-900/50">
            <label className="flex items-center gap-1.5 text-xs text-zinc-400">
              Temp:
              <input
                type="number"
                value={temperature}
                onChange={e => setTemperature(Number(e.target.value) || 0)}
                min={0}
                max={2}
                step={0.1}
                className="w-14 bg-zinc-800 border border-zinc-700 rounded px-1.5 py-0.5 text-xs text-zinc-200 text-center"
              />
            </label>
            <label className="flex items-center gap-1.5 text-xs text-zinc-400">
              Max tokens:
              <input
                type="number"
                value={maxTokens}
                onChange={e => setMaxTokens(Number(e.target.value) || 256)}
                min={1}
                max={128000}
                className="w-16 bg-zinc-800 border border-zinc-700 rounded px-1.5 py-0.5 text-xs text-zinc-200 text-center"
              />
            </label>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !streaming ? (
            <div className="flex flex-col items-center justify-center h-full px-4">
              <MessageSquare size={40} className="text-zinc-700 mb-3" />
              <p className="text-sm text-zinc-500">Send a message to start chatting</p>
            </div>
          ) : (
            <div className="px-4 py-4 space-y-3">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 ${
                    msg.role === 'user' ? 'bg-zinc-700' : 'bg-primary-600/20'
                  }`}>
                    {msg.role === 'user' ? (
                      <User size={14} className="text-zinc-300" />
                    ) : (
                      <Bot size={14} className="text-primary-400" />
                    )}
                  </div>
                  <div className={`min-w-0 max-w-[80%] ${msg.role === 'user' ? 'text-right' : ''}`}>
                    <div className={`inline-block rounded-xl px-3 py-2 text-left ${
                      msg.role === 'user'
                        ? 'bg-primary-600 text-white'
                        : 'bg-zinc-800 text-zinc-200'
                    }`}>
                      <p className="text-sm whitespace-pre-wrap break-words">{msg.content}</p>
                    </div>
                    {msg.role === 'assistant' && (
                      <div className="flex items-center gap-1.5 mt-1">
                        <button
                          onClick={() => handleCopy(msg.content, idx)}
                          className="p-1 rounded text-zinc-600 hover:text-zinc-400 cursor-pointer"
                        >
                          {copiedIdx === idx ? <Check size={11} className="text-green-500" /> : <Copy size={11} />}
                        </button>
                        <button
                          onClick={() => handleRetry(idx)}
                          className="p-1 rounded text-zinc-600 hover:text-zinc-400 cursor-pointer"
                        >
                          <RefreshCw size={11} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Streaming */}
              {streaming && (
                <div className="flex gap-2.5">
                  <div className="w-7 h-7 rounded-md bg-primary-600/20 flex items-center justify-center shrink-0">
                    <Bot size={14} className="text-primary-400" />
                  </div>
                  <div className="min-w-0 max-w-[80%]">
                    {streamContent ? (
                      <div className="inline-block rounded-xl px-3 py-2 bg-zinc-800 text-zinc-200">
                        <p className="text-sm whitespace-pre-wrap break-words">{streamContent}</p>
                      </div>
                    ) : (
                      <div className="inline-block rounded-xl px-3 py-2 bg-zinc-800">
                        <Loader2 size={14} className="animate-spin text-zinc-500" />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="max-w-md mx-auto">
                  <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 break-words">
                    {error}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="shrink-0 border-t border-zinc-800 bg-zinc-900/30 p-3">
          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message... (Shift+Enter for new line)"
              rows={3}
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2.5 text-sm text-zinc-200 resize-none focus:outline-none focus:border-primary-500 placeholder-zinc-600 min-h-[76px] max-h-[200px]"
              disabled={streaming}
            />
            {streaming ? (
              <button
                onClick={handleStop}
                className="shrink-0 p-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white cursor-pointer"
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim() || !selectedModel}
                className="shrink-0 p-2.5 rounded-xl bg-primary-600 hover:bg-primary-700 text-white disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
