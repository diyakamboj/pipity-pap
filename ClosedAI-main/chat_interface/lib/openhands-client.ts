"use client"

import { useState, useCallback } from "react"

export interface OpenHandsMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  status: 'sending' | 'sent' | 'receiving' | 'received' | 'error'
  metadata?: {
    files?: string[]
    artifacts?: any
    tool_calls?: any[]
  }
}

interface Conversation {
  messages: OpenHandsMessage[]
  isRunning: boolean
  error: string | null
  sendMessage: (prompt: string) => Promise<void>
  run: () => Promise<void>
  clear: () => void
}

function createConversation(): Conversation {
  const [messages, setMessages] = useState<OpenHandsMessage[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = useCallback(async (prompt: string) => {
    if (!prompt.trim()) return

    const userMessage: OpenHandsMessage = {
      id: `user-${Date.now()}-${Math.random()}`,
      role: 'user',
      content: prompt,
      timestamp: new Date(),
      status: 'sent'
    }

    setMessages(prev => [...prev, userMessage])
    setError(null)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to send message')
      }

      const data = await response.json()

      const assistantMessage: OpenHandsMessage = {
        id: `assistant-${Date.now()}-${Math.random()}`,
        role: 'assistant',
        content: data.message || 'No response received',
        timestamp: new Date(),
        status: 'received'
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      const errorMessage: OpenHandsMessage = {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: new Date(),
        status: 'error'
      }
      setMessages(prev => [...prev, errorMessage])
    }
  }, [])

  const run = useCallback(async () => {
    setIsRunning(true)
    try {
      // Run any pending messages or process the conversation
      // This could trigger streaming responses from the agent
      console.log('Running conversation with', messages.length, 'messages')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error running conversation')
    } finally {
      setIsRunning(false)
    }
  }, [messages.length])

  const clear = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return {
    messages,
    isRunning,
    error,
    sendMessage,
    run,
    clear
  }
}

export { createConversation }
export type { Conversation }