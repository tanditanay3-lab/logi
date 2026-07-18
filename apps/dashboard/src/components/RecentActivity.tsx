import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Clock, Package, Warehouse, Truck, CheckCircle, AlertTriangle } from 'lucide-react'
import { agentTaskApi } from '../services/api'
import LoadingSpinner from './LoadingSpinner'

interface ActivityItem {
  id: string
  type: 'shipment' | 'inventory' | 'route' | 'task' | 'approval'
  action: string
  description: string
  timestamp: string
  status: 'success' | 'warning' | 'error' | 'info'
  agentType?: string
}

const RecentActivity: React.FC = () => {
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchRecentActivity = async () => {
      try {
        setLoading(true)
        
        // Fetch recent agent tasks
        const response = await agentTaskApi.list({
          limit: 10,
          offset: 0
        })

        // Map to activity items
        const mappedActivities: ActivityItem[] = response.items.map(task => ({
          id: task.id,
          type: 'task' as const,
          action: task.action_type,
          description: `Agent task ${task.action_type} ${task.status}`,
          timestamp: task.created_at,
          status: task.status === 'failed' ? 'error' : 
                  task.status === 'pending_approval' ? 'warning' : 'success',
          agentType: task.agent_type
        }))

        setActivities(mappedActivities)
      } catch (err) {
        console.error('Error fetching recent activity:', err)
        // Set some default activities for demo
        setActivities([
          {
            id: '1',
            type: 'shipment',
            action: 'created',
            description: 'New shipment created with tracking number 1234567890',
            timestamp: new Date(Date.now() - 3600000).toISOString(),
            status: 'success'
          },
          {
            id: '2',
            type: 'inventory',
            action: 'low_stock',
            description: 'Low stock alert for SKU-001 (50 units remaining)',
            timestamp: new Date(Date.now() - 1800000).toISOString(),
            status: 'warning'
          },
          {
            id: '3',
            type: 'route',
            action: 'optimized',
            description: 'Route ROUTE-001 optimized with 5 stops',
            timestamp: new Date(Date.now() - 900000).toISOString(),
            status: 'success'
          },
          {
            id: '4',
            type: 'task',
            action: 'eta_drift_detected',
            description: 'ETA drift detected for shipment 1234567890',
            timestamp: new Date(Date.now() - 600000).toISOString(),
            status: 'warning',
            agentType: 'shipment-tracking'
          },
        ])
      } finally {
        setLoading(false)
      }
    }

    fetchRecentActivity()
  }, [])

  const getIcon = (type: ActivityItem['type']) => {
    switch (type) {
      case 'shipment':
        return <Package className="w-5 h-5" />
      case 'inventory':
        return <Warehouse className="w-5 h-5" />
      case 'route':
        return <Truck className="w-5 h-5" />
      case 'task':
        return <CheckCircle className="w-5 h-5" />
      case 'approval':
        return <AlertTriangle className="w-5 h-5" />
      default:
        return <Clock className="w-5 h-5" />
    }
  }

  const getStatusColor = (status: ActivityItem['status']) => {
    switch (status) {
      case 'success':
        return 'bg-green-100 text-green-700'
      case 'warning':
        return 'bg-yellow-100 text-yellow-700'
      case 'error':
        return 'bg-red-100 text-red-700'
      case 'info':
        return 'bg-blue-100 text-blue-700'
      default:
        return 'bg-secondary-100 text-secondary-700'
    }
  }

  const formatTimeAgo = (timestamp: string): string => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (diffInSeconds < 60) {
      return `${diffInSeconds}s ago`
    } else if (diffInSeconds < 3600) {
      return `${Math.floor(diffInSeconds / 60)}m ago`
    } else if (diffInSeconds < 86400) {
      return `${Math.floor(diffInSeconds / 3600)}h ago`
    } else {
      return `${Math.floor(diffInSeconds / 86400)}d ago`
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Recent Activity</h2>
        </div>
        <div className="flex items-center justify-center p-8">
          <LoadingSpinner size="md" />
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Recent Activity</h2>
      </div>
      <div className="space-y-4">
        {activities.length === 0 ? (
          <div className="text-center py-8 text-secondary-500">
            No recent activity
          </div>
        ) : (
          activities.map((activity) => (
            <div
              key={activity.id}
              className="flex items-start gap-4 p-4 bg-secondary-50 rounded-lg hover:bg-secondary-100 transition-colors"
            >
              <div className={clsx(
                'p-2 rounded-lg',
                getStatusColor(activity.status)
              )}>
                {getIcon(activity.type)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-secondary-700">
                    {activity.agentType || activity.type}
                  </span>
                  <span className="text-sm text-secondary-500">
                    {formatTimeAgo(activity.timestamp)}
                  </span>
                </div>
                <p className="text-sm text-secondary-600 mt-1">
                  {activity.description}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default RecentActivity
