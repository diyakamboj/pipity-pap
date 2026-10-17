"use client"

import { useState, useEffect, useCallback, useRef } from "react"

// HR Agent SDK Types (aligned with actual SDK structure)
export interface HRAgentMessage {
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

export interface HRAgentConfig {
  llm: {
    model: string
    api_key: string
    base_url?: string
  }
  workspace?: {
    working_dir: string
    host: string
    port: number
  }
  tools?: string[]
  max_workers?: number
  security_analyzer?: any
  confirmation_policy?: any
  session_api_key?: string
}

export interface HRAgentEvent {
  type: 'message' | 'token' | 'tool_call' | 'error' | 'status' | 'step' | 'skill' | 'mcp' | 'memory' | 'database' | 'subagent' | 'task' | 'file' | 'api' | 'log' | 'retry'
  data: any
  timestamp: Date
  conversation_id?: string
}

// WebSocket connection state
export interface WebSocketState {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  reconnectAttempts: number
}

class HRAgentClient {
  private ws: WebSocket | null = null
  private config: HRAgentConfig
  private eventCallbacks: Array<(event: HRAgentEvent) => void> = []
  private messageCallbacks: Array<(message: HRAgentMessage) => void> = []
  private statusCallbacks: Array<(status: string) => void> = []
  private reconnectTimer: NodeJS.Timeout | null = null
  private heartbeatTimer: NodeJS.Timeout | null = null
  private reconnectAttempts: number = 0
  private conversationId: string | null = null

  constructor(config: HRAgentConfig) {
    this.config = config
  }

  public connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        // Determine WebSocket URL based on configuration
        // Use real HR Agent WebSocket endpoint from runtime.server.sockets.py
        if (!this.conversationId) {
          throw new Error('No conversation ID set. Call connectToConversation first.')
        }

        let wsUrl: string
        const path = `/sockets/events/${this.conversationId}?resend_mode=all`
        if (this.config.workspace?.host) {
          // Use HR Agent's events socket endpoint
          wsUrl = `ws://${this.config.workspace.host}:${this.config.workspace.port}${path}`
        } else {
          // Default to localhost for local development
          wsUrl = `ws://localhost:8001${path}`
        }

        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          console.log('HR Agent WebSocket connected to events endpoint')

          // First-message auth for HR Agent (recommended approach from runtime.server.sockets.py)
          if (this.config.session_api_key) {
            const authMessage = {
              type: 'auth',
              session_api_key: this.config.session_api_key
            }
            this.ws?.send(JSON.stringify(authMessage))
            console.log('Sent first-message authentication to HR Agent')
          }

          this.startHeartbeat()
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            this.handleMessage(data)
          } catch (error) {
            console.error('Failed to parse HR Agent WebSocket message:', error)
            this.emitEvent('error', { message: 'Failed to parse HR Agent message', error })
          }
        }

        this.ws.onerror = (error) => {
          console.error('HR Agent WebSocket error:', error)
          this.emitEvent('error', { message: 'HR Agent WebSocket connection error', error })
        }

        this.ws.onclose = () => {
          console.log('HR Agent WebSocket disconnected from events endpoint')
          this.stopHeartbeat()
          this.scheduleReconnect()
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  public disconnect(): void {
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.conversationId = null
  }

  public connectToConversation(conversationId: string): Promise<void> {
    this.conversationId = conversationId
    return this.connect()
  }

  public sendMessage(prompt: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('HR Agent WebSocket is not connected')
    }

    if (!this.conversationId) {
      throw new Error('No conversation ID set. Call connectToConversation first.')
    }

    const message = {
      type: 'user_message',
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
      session_id: `session-${Date.now()}`,
      conversation_id: this.conversationId
    }

    this.ws.send(JSON.stringify(message))
    this.emitEvent('message', message)
  }

  public setConversationId(conversationId: string): void {
    this.conversationId = conversationId
  }

  public onEvent(callback: (event: HRAgentEvent) => void): void {
    this.eventCallbacks.push(callback)
  }

  public onMessage(callback: (message: HRAgentMessage) => void): void {
    this.messageCallbacks.push(callback)
  }

  public onStatus(callback: (status: string) => void): void {
    this.statusCallbacks.push(callback)
  }

  private handleMessage(data: any): void {
    const event: HRAgentEvent = {
      type: data.type || 'message',
      data: data,
      timestamp: new Date()
    }

    this.emitEvent(event.type, event.data)

    // Convert to HRAgentMessage format for chat integration
    if (data.type === 'token' || data.type === 'message') {
      const hrMessage: HRAgentMessage = {
        id: `hr-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        role: data.role || 'assistant',
        content: data.content || '',
        timestamp: new Date(),
        status: 'received',
        metadata: data.metadata || {}
      }
      this.messageCallbacks.forEach(callback => callback(hrMessage))
    }

    if (data.type === 'status') {
      this.statusCallbacks.forEach(callback => callback(data.status))
    }
  }

  private emitEvent(type: HRAgentEvent["type"], data: any): void {
    const event: HRAgentEvent = { type, data, timestamp: new Date() }
    this.eventCallbacks.forEach(callback => callback(event))
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }

    // Exponential backoff for reconnection
    const delay = Math.min(1000 * Math.pow(2, this.getReconnectAttempts()), 30000)
    this.reconnectTimer = setTimeout(() => {
      console.log(`Attempting to reconnect to HR Agent (attempt ${this.getReconnectAttempts() + 1})`)
      this.connect().catch(error => {
        console.error('Reconnection failed:', error)
      })
    }, delay)
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'heartbeat', timestamp: Date.now() }))
      }
    }, 30000) // 30 seconds
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private getReconnectAttempts(): number {
    return this.reconnectAttempts
  }
}

// React hook for HR Agent client integration
export function useHRAgentClient(config: HRAgentConfig) {
  const [client, setClient] = useState<HRAgentClient | null>(null)
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isConnecting: false,
    error: null,
    reconnectAttempts: 0
  })
  const clientRef = useRef<HRAgentClient | null>(null)

  const connect = useCallback(async () => {
    if (clientRef.current) {
      clientRef.current.disconnect()
    }

    setState(prev => ({ ...prev, isConnecting: true, error: null }))

    try {
      const newClient = new HRAgentClient(config)
      clientRef.current = newClient
      setClient(newClient)

      // Setup event listeners
      newClient.onEvent((event) => {
        setState(prev => ({ ...prev, error: event.type === 'error' ? event.data.message : null }))
      })

      newClient.onMessage((message) => {
        // Messages are handled via the regular chat store
      })

      newClient.onStatus((status) => {
        console.log('HR Agent status:', status)
      })

      await newClient.connect()
      setState({ isConnected: true, isConnecting: false, error: null, reconnectAttempts: 0 })
    } catch (error) {
      setState(prev => ({
        ...prev,
        isConnecting: false,
        error: error instanceof Error ? error.message : 'Connection failed'
      }))
      setClient(null)
      clientRef.current = null
    }
  }, [config])

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect()
    }
    setClient(null)
    setState({ isConnected: false, isConnecting: false, error: null, reconnectAttempts: 0 })
    clientRef.current = null
  }, [])

  const sendMessage = useCallback((prompt: string) => {
    if (clientRef.current) {
      clientRef.current.sendMessage(prompt)
    } else {
      throw new Error('HR Agent client not connected')
    }
  }, [])

  // Auto-connect on mount
  useEffect(() => {
    connect()
    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect()
      }
    }
  }, [connect])

  return {
    ...state,
    connect,
    disconnect,
    sendMessage,
    isHRConnected: state.isConnected,
    hrError: state.error
  }
}

export type { HRAgentClient }
export default HRAgentClient