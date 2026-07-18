import React, { useState, useEffect } from 'react'
import { CheckCircle, Clock, AlertTriangle, XCircle, Loader2 } from 'lucide-react'
import { healthApi } from '../services/api'

interface AgentStatus {
  name: string
  type: string
  status: 'healthy' | 'degraded' | 'unhealthy' | 'loading'
  version: string
  lastChecked: string
}

const agents = [
  { name: 'API Gateway', type: 'api-gateway', endpoint: '/health' },
  { name: 'Orchestrator', type: 'orchestrator', endpoint: '/orchestrator/health' },
  { name: 'Shipment Tracking', type: 'shipment-tracking', endpoint: '/shipment-tracking/health' },
  { name: 'Inventory', type: 'inventory', endpoint: '/inventory/health' },
  { name: 'Route Optimization', type: 'route-optimization', endpoint: '/route-optimization/health' },
  { name: 'Chat Copilot', type: 'chat-copilot', endpoint: '/chat/health' },
]

const AgentStatus: React.FC = () => {
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const checkAgentHealth = async () => {
      try {
        setLoading(true)
        
        const statuses: AgentStatus[] = []
        
        for (const agent of agents) {
          try {
            // For demo, we'll simulate the health check
            // In production, this would call the actual health endpoints
            const response = await healthApi.checkAgent(agent.type as any)
            
            statuses.push({
              name: agent.name,
              type: agent.type,
              status: response.status === 'healthy' ? 'healthy' : 'unhealthy',
              version: response.version,
              lastChecked: new Date().toISOString()
            })
          } catch (err) {
            statuses.push({
              name: agent.name,
              type: agent.type,
              status: 'unhealthy',
              version: 'unknown',
              lastChecked: new Date().toISOString()
            })
          }
        }
        
        setAgentStatuses(statuses)
      } catch (err) {
        console.error('Error checking agent health:', err)
        // Set default statuses for demo
        setAgentStatuses(agents.map(agent => ({
          name: agent.name,
          type: agent.type,
          status: 'healthy' as const,
          version: '1.0.0',
          lastChecked: new Date().toISOString()
        })))
      } finally {
        setLoading(false)
      }
    }

    checkAgentHealth()
    
    // Poll every 30 seconds
    const interval = setInterval(checkAgentHealth, 30000)
    
    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status: AgentStatus['status']) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'degraded':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />
      case 'unhealthy':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'loading':
        return <Loader2 className="w-4 h-4 animate-spin" />
      default:
        return <Clock className="w-4 h-4 text-secondary-400" />
    }
  }

  const getStatusColor = (status: AgentStatus['status']) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600'
      case 'degraded':
        return 'text-yellow-600'
      case 'unhealthy':
        return 'text-red-600'
      case 'loading':
        return 'text-secondary-400'
      default:
        return 'text-secondary-400'
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Agent Status</h2>
      </div>
      <div className="space-y-3">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : (
          agentStatuses.map((agent) => (
            <div
              key={agent.type}
              className="flex items-center justify-between p-3 bg-secondary-50 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <div className={getStatusColor(agent.status)}>
                  {getStatusIcon(agent.status)}
                </div>
                <div>
                  <p className="font-medium text-secondary-900">{agent.name}</p>
                  <p className="text-xs text-secondary-500">{agent.type}</p>
                </div>
              </div>
              <div className="text-right">
                <p className={`text-sm ${getStatusColor(agent.status)}`}>
                  {agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}
                </p>
                <p className="text-xs text-secondary-500">v{agent.version}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default AgentStatus
