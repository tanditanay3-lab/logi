import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { 
  Package, 
  Truck, 
  Warehouse, 
  MessageSquare,
  CheckCircle,
  Clock,
  AlertTriangle,
  BarChart3,
  Users,
  Settings
} from 'lucide-react'
import { shipmentApi, inventoryApi, routeApi, agentTaskApi } from '../services/api'
import StatCard from '../components/StatCard'
import RecentActivity from '../components/RecentActivity'
import AgentStatus from '../components/AgentStatus'
import LoadingSpinner from '../components/LoadingSpinner'

interface DashboardStats {
  shipments: {
    total: number
    in_transit: number
    delivered: number
    delayed: number
  }
  inventory: {
    total_items: number
    low_stock: number
    out_of_stock: number
  }
  routes: {
    total: number
    pending: number
    in_progress: number
    completed: number
  }
  agent_tasks: {
    total: number
    pending_approval: number
    auto_executed: number
    failed: number
  }
}

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true)
        
        // Fetch all stats in parallel
        const [shipmentStats, inventoryStats, routeStats, taskStats] = await Promise.all([
          shipmentApi.stats(),
          inventoryApi.stats(),
          routeApi.stats(),
          agentTaskApi.list({ limit: 1000 })
        ])

        setStats({
          shipments: shipmentStats,
          inventory: inventoryStats,
          routes: routeStats,
          agent_tasks: {
            total: taskStats.total,
            pending_approval: taskStats.items.filter(t => t.status === 'pending_approval').length,
            auto_executed: taskStats.items.filter(t => t.status === 'auto_executed').length,
            failed: taskStats.items.filter(t => t.status === 'failed').length,
          }
        })
      } catch (err) {
        setError('Failed to load dashboard statistics')
        console.error('Error fetching stats:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        {error}
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="text-center py-8 text-secondary-500">
        No data available
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-secondary-900">Dashboard</h1>
        <p className="text-secondary-600 mt-1">Welcome back! Here's what's happening in your operation.</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Shipment Stats */}
        <StatCard
          title="Shipments"
          value={stats.shipments.total}
          icon={<Truck className="w-6 h-6 text-primary-600" />}
          color="primary"
          trend={stats.shipments.in_transit - stats.shipments.delivered}
          trendDirection={stats.shipments.in_transit > stats.shipments.delivered ? 'up' : 'down'}
        >
          <div className="space-y-2 mt-4">
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">In Transit</span>
              <span className="font-medium">{stats.shipments.in_transit}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Delivered</span>
              <span className="font-medium text-green-600">{stats.shipments.delivered}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Delayed</span>
              <span className="font-medium text-red-600">{stats.shipments.delayed}</span>
            </div>
          </div>
        </StatCard>

        {/* Inventory Stats */}
        <StatCard
          title="Inventory"
          value={stats.inventory.total_items}
          icon={<Warehouse className="w-6 h-6 text-green-600" />}
          color="green"
          trend={stats.inventory.low_stock}
          trendDirection="down"
        >
          <div className="space-y-2 mt-4">
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Total Items</span>
              <span className="font-medium">{stats.inventory.total_items}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Low Stock</span>
              <span className="font-medium text-yellow-600">{stats.inventory.low_stock}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Out of Stock</span>
              <span className="font-medium text-red-600">{stats.inventory.out_of_stock}</span>
            </div>
          </div>
        </StatCard>

        {/* Route Stats */}
        <StatCard
          title="Routes"
          value={stats.routes.total}
          icon={<BarChart3 className="w-6 h-6 text-blue-600" />}
          color="blue"
          trend={stats.routes.in_progress}
          trendDirection="up"
        >
          <div className="space-y-2 mt-4">
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Pending</span>
              <span className="font-medium">{stats.routes.pending}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">In Progress</span>
              <span className="font-medium text-blue-600">{stats.routes.in_progress}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Completed</span>
              <span className="font-medium text-green-600">{stats.routes.completed}</span>
            </div>
          </div>
        </StatCard>

        {/* Agent Tasks Stats */}
        <StatCard
          title="Agent Tasks"
          value={stats.agent_tasks.total}
          icon={<Users className="w-6 h-6 text-purple-600" />}
          color="purple"
          trend={stats.agent_tasks.pending_approval}
          trendDirection={stats.agent_tasks.pending_approval > 0 ? 'up' : 'down'}
        >
          <div className="space-y-2 mt-4">
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Pending</span>
              <span className="font-medium text-yellow-600">{stats.agent_tasks.pending_approval}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Auto-Executed</span>
              <span className="font-medium text-green-600">{stats.agent_tasks.auto_executed}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-secondary-600">Failed</span>
              <span className="font-medium text-red-600">{stats.agent_tasks.failed}</span>
            </div>
          </div>
        </StatCard>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2">
          <RecentActivity />
        </div>

        {/* Agent Status */}
        <div>
          <AgentStatus />
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Quick Actions</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Link
            to="/shipments"
            className="flex flex-col items-center gap-2 p-4 bg-secondary-50 rounded-lg hover:bg-secondary-100 transition-colors"
          >
            <Package className="w-6 h-6 text-primary-600" />
            <span className="text-sm font-medium text-secondary-700">View Shipments</span>
          </Link>
          <Link
            to="/inventory"
            className="flex flex-col items-center gap-2 p-4 bg-secondary-50 rounded-lg hover:bg-secondary-100 transition-colors"
          >
            <Warehouse className="w-6 h-6 text-green-600" />
            <span className="text-sm font-medium text-secondary-700">Check Inventory</span>
          </Link>
          <Link
            to="/routes"
            className="flex flex-col items-center gap-2 p-4 bg-secondary-50 rounded-lg hover:bg-secondary-100 transition-colors"
          >
            <Truck className="w-6 h-6 text-blue-600" />
            <span className="text-sm font-medium text-secondary-700">Manage Routes</span>
          </Link>
          <Link
            to="/chat"
            className="flex flex-col items-center gap-2 p-4 bg-secondary-50 rounded-lg hover:bg-secondary-100 transition-colors"
          >
            <MessageSquare className="w-6 h-6 text-purple-600" />
            <span className="text-sm font-medium text-secondary-700">Chat Copilot</span>
          </Link>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
