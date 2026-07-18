import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Package, Search, Plus, RefreshCw, Filter, MoreVertical, Eye, Edit, Trash2 } from 'lucide-react'
import { shipmentApi } from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'

interface ShipmentFilter {
  status?: string
  carrier?: string
  trackingNumber?: string
}

const ShipmentStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'in_transit':
        return 'bg-blue-100 text-blue-700'
      case 'delivered':
        return 'bg-green-100 text-green-700'
      case 'delayed':
        return 'bg-yellow-100 text-yellow-700'
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

const Shipments: React.FC = () => {
  const [filters, setFilters] = useState<ShipmentFilter>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['shipments', filters, page, pageSize],
    queryFn: async () => {
      const response = await shipmentApi.list({
        status: filters.status,
        carrier: filters.carrier,
        tracking_number: filters.trackingNumber,
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

  const handleFilterChange = (key: keyof ShipmentFilter, value: string | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value || undefined }))
    setPage(1) // Reset to first page when filters change
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      setFilters(prev => ({ ...prev, trackingNumber: searchQuery.trim() }))
      setPage(1)
    }
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
        Error loading shipments: {error?.message}
      </div>
    )
  }

  const shipments = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Shipments</h1>
          <p className="text-secondary-600 mt-1">Track and manage all shipments</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="btn btn-secondary gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <Link to="/shipments/new" className="btn btn-primary gap-2">
            <Plus className="w-4 h-4" />
            New Shipment
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
            <input
              type="text"
              placeholder="Search by tracking number..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
            />
          </div>
          <select
            value={filters.status || ''}
            onChange={(e) => handleFilterChange('status', e.target.value)}
            className="select"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="in_transit">In Transit</option>
            <option value="delivered">Delivered</option>
            <option value="delayed">Delayed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            value={filters.carrier || ''}
            onChange={(e) => handleFilterChange('carrier', e.target.value)}
            className="select"
          >
            <option value="">All Carriers</option>
            <option value="FedEx">FedEx</option>
            <option value="UPS">UPS</option>
            <option value="USPS">USPS</option>
            <option value="DHL">DHL</option>
          </select>
          <button
            type="button"
            onClick={clearFilters}
            className="btn btn-secondary gap-2"
          >
            <Filter className="w-4 h-4" />
            Clear
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            {total} Shipment{total !== 1 ? 's' : ''}
          </h2>
        </div>
        
        {shipments.length === 0 ? (
          <div className="text-center py-12 text-secondary-500">
            <Package className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No shipments found</p>
            <p className="text-sm mt-1">Try adjusting your filters</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Tracking #</th>
                    <th>Carrier</th>
                    <th>Status</th>
                    <th>Origin</th>
                    <th>Destination</th>
                    <th>ETA</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {shipments.map((shipment) => (
                    <tr key={shipment.id}>
                      <td className="font-medium">
                        <Link 
                          to={`/shipments/${shipment.id}`} 
                          className="text-primary-600 hover:underline"
                        >
                          {shipment.tracking_number}
                        </Link>
                      </td>
                      <td>{shipment.carrier}</td>
                      <td>
                        <ShipmentStatusBadge status={shipment.status} />
                      </td>
                      <td className="max-w-[200px] truncate">
                        {shipment.origin?.city}, {shipment.origin?.state}
                      </td>
                      <td className="max-w-[200px] truncate">
                        {shipment.destination?.city}, {shipment.destination?.state}
                      </td>
                      <td>
                        {shipment.estimated_delivery 
                          ? new Date(shipment.estimated_delivery).toLocaleDateString()
                          : 'N/A'}
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <button
                            className="p-2 text-secondary-500 hover:bg-secondary-100 rounded-lg"
                            title="View"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            className="p-2 text-secondary-500 hover:bg-secondary-100 rounded-lg"
                            title="Edit"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            className="p-2 text-red-500 hover:bg-red-100 rounded-lg"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
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

export default Shipments
