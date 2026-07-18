import React, { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { MessageSquare, Send, Loader2, User, Bot, Clock } from 'lucide-react'
import { chatApi } from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
}

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: suggestedPrompts } = useQuery({
    queryKey: ['suggested-prompts'],
    queryFn: async () => {
      const response = await chatApi.getSuggestedPrompts()
      return response
    },
  })

  const { mutate: sendMessage } = useMutation({
    mutationFn: async (message: string) => {
      return await chatApi.sendMessage({
        message,
        conversation_id: conversationId || undefined
      })
    },
    onMutate: () => {
      setIsSending(true)
    },
    onSuccess: (response) => {
      const assistantMessage: ChatMessage = {
        id: response.message_id,
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        metadata: {
          agent_type: response.agent_type,
          requires_approval: response.requires_approval
        }
      }
      setMessages(prev => [...prev, assistantMessage])
      if (!conversationId) {
        setConversationId(response.conversation_id)
      }
    },
    onError: (error) => {
      console.error('Error sending message:', error)
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMessage])
    },
    onSettled: () => {
      setIsSending(false)
      setInputValue('')
    },
  })

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || isSending) return

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString(),
    }

    setMessages(prev => [...prev, userMessage])
    sendMessage(inputValue.trim())
  }

  const handlePromptSelect = (prompt: string) => {
    setInputValue(prompt)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-secondary-900">Chat Copilot</h1>
        <p className="text-secondary-600 mt-1">
          Ask questions and get answers from your Lanework agents
        </p>
      </div>

      {/* Chat container */}
      <div className="card flex flex-col h-[600px]">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-secondary-500">
              <MessageSquare className="w-16 h-16 mb-4 opacity-50" />
              <p className="text-lg font-medium">Start a conversation</p>
              <p className="text-sm mt-1 text-center max-w-md">
                Ask about shipments, inventory, routes, or any other logistics questions
              </p>
              
              {/* Suggested prompts */}
              {suggestedPrompts && suggestedPrompts.length > 0 && (
                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
                  {suggestedPrompts.map((prompt, index) => (
                    <button
                      key={index}
                      onClick={() => handlePromptSelect(prompt)}
                      className="p-3 bg-secondary-50 rounded-lg text-left text-sm hover:bg-secondary-100 transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${message.role === 'user' 
                    ? 'bg-primary-600 text-white rounded-br-none' 
                    : 'bg-secondary-100 text-secondary-900 rounded-bl-none'}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {message.role === 'user' ? (
                      <User className="w-4 h-4" />
                    ) : (
                      <Bot className="w-4 h-4" />
                    )}
                    <span className="text-xs opacity-70">
                      {message.role === 'user' ? 'You' : 'Lanework AI'}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  <p className={`text-xs mt-2 ${message.role === 'user' ? 'text-primary-200' : 'text-secondary-500'}`}>
                    {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))
          )}
          
          {isSending && (
            <div className="flex justify-start">
              <div className="bg-secondary-100 rounded-2xl rounded-bl-none px-4 py-3">
                <div className="flex items-center gap-2">
                  <Bot className="w-4 h-4" />
                  <span className="text-xs opacity-70">Lanework AI</span>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="border-t border-secondary-200 p-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Type your message..."
              disabled={isSending}
              className="flex-1 input"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  handleSend(e)
                }
              }}
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || isSending}
              className="btn btn-primary px-6 gap-2 disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
              Send
            </button>
          </div>
          <p className="text-xs text-secondary-500 mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </form>
      </div>

      {/* Info */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">About Chat Copilot</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-secondary-50 rounded-lg">
            <h3 className="font-semibold text-secondary-900 mb-2">Supported Agents</h3>
            <ul className="space-y-1 text-sm text-secondary-600">
              <li>• Shipment Tracking</li>
              <li>• Inventory Management</li>
              <li>• Route Optimization</li>
              <li>• Customer Communication</li>
            </ul>
          </div>
          <div className="p-4 bg-secondary-50 rounded-lg">
            <h3 className="font-semibold text-secondary-900 mb-2">Example Questions</h3>
            <ul className="space-y-1 text-sm text-secondary-600">
              <li>• "Where is shipment 1234567890?"</li>
              <li>• "What's the inventory level for SKU-001?"</li>
              <li>• "Optimize my routes for tomorrow"</li>
              <li>• "Report a road closure on route ROUTE-001"</li>
            </ul>
          </div>
          <div className="p-4 bg-secondary-50 rounded-lg">
            <h3 className="font-semibold text-secondary-900 mb-2">Capabilities</h3>
            <ul className="space-y-1 text-sm text-secondary-600">
              <li>• Natural language understanding</li>
              <li>• Multi-agent routing</li>
              <li>• Context-aware responses</li>
              <li>• Approval workflows</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Chat
