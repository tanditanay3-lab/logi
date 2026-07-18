import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle, Clock, XCircle, AlertTriangle, Search, RefreshCw, Filter } from 'lucide-react'
import { agentTaskApi } from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'

interface AgentTaskFilter {
  agentType?: string
  status?: string
}

const AgentTaskStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'pending_approval':
        return 'bg-yellow-100 text-yellow-700'
      case 'approved':
        return 'bg-green-100 text-green-700'
      case 'auto_executed':
        return 'bg-blue-100 text-blue-700'
      case 'failed':
        return 'bg-red-100 text-red-700'
      case 'completed':
        return 'bg-green-100 text-green-700'
      case 'rejected':
        return 'bg-red-100 text-red-700'
      default:
        return 'bg-secondary-100 text-secondary-700'
    }
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor()}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

const AgentTasks: React.FC = () => {
  const [filters, setFilters] = useState<AgentTaskFilter>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['agent-tasks', filters, page, pageSize],
    queryFn: async () => {
      const response = await agentTaskApi.list({
        agent_type: filters.agentType as any,
        status: filters.status as any,
        limit: pageSize,
        offset: (page - 1) * pageSize
      })
      return response
    },
    keepPreviousData: true,
  })

  const handleRefresh = () => {
    refetch()
  }

  const handleFilterChange = (key: keyof AgentTaskFilter, value: string | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value || undefined }))
    setPage(1)
  }

  const clearFilters = () => {
    setFilters({})
    setPage(1)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        Error loading agent tasks: {error?.message}
      </div>
    )
  }

  const tasks = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Agent Tasks</h1>
          <p className="text-secondary-600 mt-1">Track all agent actions and approvals</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="btn btn-secondary gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <select
            value={filters.agentType || ''}
            onChange={(e) => handleFilterChange('agentType', e.target.value)}
            className="select"
          >
            <option value="">All Agents</option>
            <option value="shipment-tracking">Shipment Tracking</option>
            <option value="inventory">Inventory</option>
            <option value="route-optimization">Route Optimization</option>
            <option value="warehouse-ops">Warehouse Ops</option>
            <option value="fleet-management">Fleet Management</option>
            <option value="customer-communication">Customer Communication</option>
            <option value="demand-forecasting">Demand Forecasting</option>
            <option value="freight-procurement">Freight Procurement</option>
            <option value="voice">Voice</option>
          </select>
          <select
            value={filters.status || ''}
            onChange={(e) => handleFilterChange('status', e.target.value)}
            className="select"
          >
            <option value="">All Statuses</option>
            <option value="pending_approval">Pending Approval</option>
            <option value="approved">Approved</option>
            <option value="auto_executed">Auto Executed</option>
            <option value="failed">Failed</option>
            <option value="completed">Completed</option>
            <option value="rejected">Rejected</option>
          </select>
          <button
            onClick={clearFilters}
            className="btn btn-secondary gap-2"
          >
            <Filter className="w-4 h-4" />
            Clear
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            {total} Task{total !== 1 ? 's' : ''}
          </h2>
        </div>
        
        {tasks.length === 0 ? (
          <div className="text-center py-12 text-secondary-500">
            <CheckCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No agent tasks found</p>
            <p className="text-sm mt-1">Try adjusting your filters</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Task ID</th>
                    <th>Agent</th>
                    <th>Action</th>
                    <th>Status</th>
                    <th>Trust Level</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr key={task.id}>
                      <td className="font-mono text-sm">
                        <Link 
                          to={`/agent-tasks/${task.id}`} 
                          className="text-primary-600 hover:underline"
                        >
                          {task.id}
                        </Link>
                      </td>
                      <td>{task.agent_type.replace('-', ' ')}</td>
                      <td className="max-w-[200px] truncate">{task.action_type}</td>
                      <td>
                        <AgentTaskStatusBadge status={task.status} />
                      </td>
                      <td>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          task.trust_level === 'fully_autonomous' ? 'bg-purple-100 text-purple-700' :
                          task.trust_level === 'auto_execute_low_risk' ? 'bg-blue-100 text-blue-700' :
                          'bg-secondary-100 text-secondary-700'
                        }`}>
                          {task.trust_level.replace('_', ' ')}
                        </span>
                      </td>
                      <td>{new Date(task.created_at).toLocaleString()}</td>
                      <td>
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/agent-tasks/${task.id}`}
                            className="p-2 text-secondary-500 hover:bg-secondary-100 rounded-lg"
                            title="View"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          {task.status === 'pending_approval' && (
                            <>
                              <button
                                className="p-2 text-green-600 hover:bg-green-100 rounded-lg"
                                title="Approve"
                              >
                                <CheckCircle className="w-4 h-4" />
                              </button>
                              <button
                                className="p-2 text-red-600 hover:bg-red-100 rounded-lg"
                                title="Reject"
                              >
                                <XCircle className="w-4 h-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-secondary-200">
                <div className="text-sm text-secondary-500">
                  Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1 text-sm rounded-lg border border-secondary-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <span className="text-sm">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1 text-sm rounded-lg border border-secondary-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default AgentTasks
