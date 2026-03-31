import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send,
  Bot,
  User,
  Settings,
  Trash2,
  MessageSquare,
  Cpu,
  ChevronLeft,
  ChevronRight,
  PanelLeftClose,
  Loader2,
  X,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { fetchEventSource } from '@microsoft/fetch-event-source'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  toolCalls?: { name: string; args: Record<string, unknown>; result: string }[]
  isStreaming?: boolean
}

interface Conversation {
  id: number
  session_id: string
  title: string | null
  message_count: number
  updated_at: string
}

const MODELS = [
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'deepseek/deepseek-chat', label: 'DeepSeek' },
  { value: 'anthropic/claude-3-haiku', label: 'Claude 3 Haiku' },
  { value: 'ollama/llama3', label: 'Llama 3 (Local)' },
]

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('omni_session_id') || '')
  const [model, setModel] = useState(() => localStorage.getItem('omni_model') || 'gpt-4o-mini')
  const [showSidebar, setShowSidebar] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [showConversations, setShowConversations] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Load conversations on mount
  useEffect(() => {
    loadConversations()
  }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Save session and model to localStorage
  useEffect(() => {
    if (sessionId) localStorage.setItem('omni_session_id', sessionId)
    localStorage.setItem('omni_model', model)
  }, [sessionId, model])

  const loadConversations = async () => {
    try {
      const res = await fetch('/api/conversations?limit=50')
      const data = await res.json()
      setConversations(data.conversations || [])
    } catch (err) {
      console.error('Failed to load conversations:', err)
    }
  }

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
    }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Generate new session ID if needed
    const currentSessionId = sessionId || crypto.randomUUID()
    if (!sessionId) {
      setSessionId(currentSessionId)
    }

    // Add placeholder for assistant
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    }
    setMessages(prev => [...prev, assistantMessage])

    try {
      const controller = new AbortController()
      abortControllerRef.current = controller

      await fetchEventSource('/api/chat/stream', {
        method: 'GET',
        signal: controller.signal,
        openWhenHidden: true,
        query: {
          message: content,
          session_id: currentSessionId,
          model,
        },
        onopen: async (response) => {
          if (response.ok) {
            // Connection established
          }
        },
        onmessage: (event) => {
          if (event.data) {
            try {
              const data = JSON.parse(event.data)
              if (data.type === 'message') {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMessage.id
                      ? { ...msg, content: data.content, isStreaming: false }
                      : msg
                  )
                )
              } else if (data.type === 'tool') {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMessage.id
                      ? {
                          ...msg,
                          toolCalls: [
                            ...(msg.toolCalls || []),
                            { name: data.name, args: data.args, result: data.result },
                          ],
                        }
                      : msg
                  )
                )
              } else if (data.type === 'status') {
                // Status updates - could show loading indicator
              }
            } catch (e) {
              // Ignore parse errors for empty events
            }
          }
        },
        onerror: (err) => {
          console.error('SSE Error:', err)
          setIsLoading(false)
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessage.id
                ? { ...msg, content: 'Error: Connection failed', isStreaming: false }
                : msg
            )
          )
        },
        onclose: () => {
          setIsLoading(false)
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessage.id ? { ...msg, isStreaming: false } : msg
            )
          )
          loadConversations()
        },
      })
    } catch (err) {
      console.error('Failed to send message:', err)
      setIsLoading(false)
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: `Error: ${err}`, isStreaming: false }
            : msg
        )
      )
    }
  }, [isLoading, sessionId, model])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  const clearChat = () => {
    setMessages([])
    setSessionId(crypto.randomUUID())
  }

  const loadConversation = async (id: number) => {
    try {
      const res = await fetch(`/api/conversations/${id}`)
      const data = await res.json()
      if (data.messages) {
        const loadedMessages: Message[] = data.messages.map((m: {
          role: string;
          content: string;
          tool_calls?: { name: string; args: Record<string, unknown>; result: string }[];
        }) => ({
          id: m.tool_call_id || `msg-${m.id}`,
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content || '',
          toolCalls: m.tool_calls as Message['toolCalls'],
        }))
        setMessages(loadedMessages)
        setSessionId(data.conversation.session_id)
        setShowConversations(false)
      }
    } catch (err) {
      console.error('Failed to load conversation:', err)
    }
  }

  return (
    <div className="flex h-screen bg-dark-900 text-dark-100">
      {/* Sidebar */}
      <aside
        className={`${
          showSidebar ? 'w-64' : 'w-0'
        } bg-dark-950 border-r border-dark-800 flex flex-col transition-all duration-300 overflow-hidden`}
      >
        <div className="p-4 border-b border-dark-800 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-primary-400 flex items-center gap-2">
            <Bot size={20} />
            Project Omni
          </h1>
          <button
            onClick={() => setShowSidebar(false)}
            className="p-1 hover:bg-dark-800 rounded"
          >
            <ChevronLeft size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="p-3">
            <button
              onClick={() => setShowConversations(!showConversations)}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-dark-300 hover:bg-dark-800 rounded-lg"
            >
              <MessageSquare size={16} />
              Conversations
            </button>

            {showConversations && (
              <div className="mt-2 space-y-1">
                {conversations.map(convo => (
                  <button
                    key={convo.id}
                    onClick={() => loadConversation(convo.id)}
                    className="w-full text-left px-3 py-2 text-sm text-dark-400 hover:bg-dark-800 rounded truncate"
                  >
                    {convo.title || `Session ${convo.id}`}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="p-3 border-t border-dark-800">
          <button
            onClick={() => setShowSettings(true)}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-dark-300 hover:bg-dark-800 rounded"
          >
            <Settings size={16} />
            Settings
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 border-b border-dark-800 flex items-center justify-between px-4 bg-dark-950">
          {!showSidebar && (
            <button
              onClick={() => setShowSidebar(true)}
              className="p-2 hover:bg-dark-800 rounded-lg"
            >
              <PanelLeftClose size={20} />
            </button>
          )}

          <div className="flex items-center gap-4">
            <select
              value={model}
              onChange={e => setModel(e.target.value)}
              className="bg-dark-800 text-dark-200 text-sm rounded-lg px-3 py-1.5 border border-dark-700 focus:outline-none focus:border-primary-500"
            >
              {MODELS.map(m => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={clearChat}
            className="p-2 hover:bg-dark-800 rounded-lg text-dark-400 hover:text-dark-200"
            title="Clear chat"
          >
            <Trash2 size={18} />
          </button>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-dark-500">
              <Bot size={48} className="mb-4 opacity-50" />
              <p className="text-lg mb-2">Welcome to Project Omni</p>
              <p className="text-sm">Send a message to get started</p>
            </div>
          )}

          {messages.map(message => (
            <div
              key={message.id}
              className={`flex gap-3 ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.role !== 'user' && (
                <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
                  <Bot size={16} className="text-white" />
                </div>
              )}

              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                  message.role === 'user'
                    ? 'bg-primary-600 text-white'
                    : 'bg-dark-800 text-dark-100'
                }`}
              >
                {message.toolCalls && message.toolCalls.length > 0 && (
                  <div className="mb-2 space-y-1">
                    {message.toolCalls.map((tool, i) => (
                      <div
                        key={i}
                        className="text-xs bg-dark-900 rounded p-2 font-mono"
                      >
                        <span className="text-primary-400">{tool.name}</span>
                        <pre className="mt-1 text-dark-400 overflow-x-auto">
                          {JSON.stringify(tool.args, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}

                <div className="prose prose-invert max-w-none prose-sm">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '')
                        const isInline = !match
                        return isInline ? (
                          <code
                            className="bg-dark-700 px-1.5 py-0.5 rounded text-primary-300"
                            {...props}
                          >
                            {children}
                          </code>
                        ) : (
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        )
                      },
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>

                {message.isStreaming && (
                  <span className="inline-flex ml-2">
                    <Loader2 size={14} className="animate-spin" />
                  </span>
                )}
              </div>

              {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center flex-shrink-0">
                  <User size={16} className="text-dark-300" />
                </div>
              )}
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-dark-800">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
              placeholder="Send a message..."
              className="flex-1 bg-dark-800 text-dark-100 rounded-xl px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows={1}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="p-3 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-white transition-colors"
            >
              {isLoading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
            </button>
          </form>
          <p className="text-xs text-dark-500 mt-2 text-center">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-900 rounded-2xl p-6 w-full max-w-md border border-dark-700">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold">Settings</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="p-2 hover:bg-dark-800 rounded-lg"
              >
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Model
                </label>
                <select
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  className="w-full bg-dark-800 text-dark-200 rounded-lg px-3 py-2 border border-dark-700 focus:outline-none focus:border-primary-500"
                >
                  {MODELS.map(m => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Session ID
                </label>
                <input
                  type="text"
                  value={sessionId}
                  onChange={e => setSessionId(e.target.value)}
                  className="w-full bg-dark-800 text-dark-200 rounded-lg px-3 py-2 border border-dark-700 focus:outline-none focus:border-primary-500 font-mono text-sm"
                  placeholder="Auto-generated"
                />
              </div>

              <div className="pt-4 border-t border-dark-800">
                <div className="flex items-center gap-2 text-sm text-dark-400">
                  <Cpu size={16} />
                  <span>Available Tools: shell_exec, read_file, write_file, browser_search_and_extract</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App