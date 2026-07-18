import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Truck, Search, Plus, RefreshCw, Filter, Clock, CheckCircle, XCircle, PlayCircle } from 'lucide-react'
import { routeApi } from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'

interface RouteFilter {
  status?: string
  driverId?: string
  vehicleId?: string
  date?: string
}

const RouteStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'assigned':
        return 'bg-blue-100 text-blue-700'
      case 'in_progress':
        return 'bg-yellow-100 text-yellow-700'
      case 'completed':
        return 'bg-green-100 text-green-700'
      case 'cancelled':
        return 'bg-red-100 text-red-700'
      case 'pending':
        return 'bg-secondary-100 text-secondary-700'
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

const RoutesPage: React.FC = () => {
  const [filters, setFilters] = useState<RouteFilter>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['routes', filters, page, pageSize],
    queryFn: async () => {
      const response = await routeApi.list({
        status: filters.status as any,
        driver_id: filters.driverId,
        vehicle_id: filters.vehicleId,
        date: filters.date,
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

  const handleFilterChange = (key: keyof RouteFilter, value: string | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value || undefined }))
    setPage(1)
  }

  const clearFilters = () => {
    setFilters({})
    setSearchQuery('')
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
        Error loading routes: {error?.message}
      </div>
    )
  }

  const routes = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Routes</h1>
          <p className="text-secondary-600 mt-1">Manage and optimize delivery routes</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="btn btn-secondary gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <Link to="/routes/new" className="btn btn-primary gap-2">
            <Plus className="w-4 h-4" />
            New Route
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <select
            value={filters.status || ''}
            onChange={(e) => handleFilterChange('status', e.target.value)}
            className="select"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="assigned">Assigned</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            value={filters.driverId || ''}
            onChange={(e) => handleFilterChange('driverId', e.target.value)}
            className="select"
          >
            <option value="">All Drivers</option>
            <option value="driver_001">Driver 1</option>
            <option value="driver_002">Driver 2</option>
          </select>
          <select
            value={filters.vehicleId || ''}
            onChange={(e) => handleFilterChange('vehicleId', e.target.value)}
            className="select"
          >
            <option value="">All Vehicles</option>
            <option value="vehicle_001">Vehicle 1</option>
            <option value="vehicle_002">Vehicle 2</option>
          </select>
          <input
            type="date"
            value={filters.date || ''}
            onChange={(e) => handleFilterChange('date', e.target.value)}
            className="input"
          />
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
            {total} Route{total !== 1 ? 's' : ''}
          </h2>
        </div>
        
        {routes.length === 0 ? (
          <div className="text-center py-12 text-secondary-500">
            <Truck className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No routes found</p>
            <p className="text-sm mt-1">Try adjusting your filters</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Route #</th>
                    <th>Name</th>
                    <th>Driver</th>
                    <th>Vehicle</th>
                    <th>Date</th>
                    <th>Stops</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {routes.map((route) => (
                    <tr key={route.id}>
                      <td className="font-medium">
                        <Link 
                          to={`/routes/${route.id}`} 
                          className="text-primary-600 hover:underline"
                        >
                          {route.id}
                        </Link>
                      </td>
                      <td>{route.name}</td>
                      <td>{route.driver_id || 'Unassigned'}</td>
                      <td>{route.vehicle_id || 'Unassigned'}</td>
                      <td>{new Date(route.date).toLocaleDateString()}</td>
                      <td>{route.total_stops}</td>
                      <td>
                        <RouteStatusBadge status={route.status} />
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/routes/${route.id}`}
                            className="p-2 text-secondary-500 hover:bg-secondary-100 rounded-lg"
                            title="View"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          {route.status === 'pending' && (
                            <button
                              className="p-2 text-green-600 hover:bg-green-100 rounded-lg"
                              title="Assign"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                          )}
                          {route.status === 'assigned' && (
                            <button
                              className="p-2 text-blue-600 hover:bg-blue-100 rounded-lg"
                              title="Start"
                            >
                              <PlayCircle className="w-4 h-4" />
                            </button>
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

export default RoutesPage
