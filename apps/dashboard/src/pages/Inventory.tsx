import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Warehouse, Search, Plus, RefreshCw, Filter, AlertTriangle, Package, ArrowUp, ArrowDown } from 'lucide-react'
import { inventoryApi } from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'

interface InventoryFilter {
  warehouseId?: string
  category?: string
  lowStock?: boolean
}

const InventoryStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-700'
      case 'inactive':
        return 'bg-secondary-100 text-secondary-700'
      case 'quarantined':
        return 'bg-red-100 text-red-700'
      default:
        return 'bg-secondary-100 text-secondary-700'
    }
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor()}`}>
      {status}
    </span>
  )
}

const StockLevelIndicator: React.FC<{ quantity: number; reorderPoint: number }> = ({ quantity, reorderPoint }) => {
  const percentage = (quantity / reorderPoint) * 100
  const isLow = quantity <= reorderPoint
  const isCritical = quantity <= reorderPoint * 0.5

  const getColor = () => {
    if (isCritical) return 'bg-red-500'
    if (isLow) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 rounded-full bg-secondary-200 overflow-hidden">
        <div
          className={`h-full ${getColor()}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <span className={`text-xs font-medium ${isCritical ? 'text-red-600' : isLow ? 'text-yellow-600' : 'text-green-600'}`}>
        {quantity} / {reorderPoint}
      </span>
    </div>
  )
}

const Inventory: React.FC = () => {
  const [filters, setFilters] = useState<InventoryFilter>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['inventory', filters, page, pageSize],
    queryFn: async () => {
      const response = await inventoryApi.list({
        warehouse_id: filters.warehouseId,
        category: filters.category,
        low_stock: filters.lowStock,
        sku: searchQuery || undefined,
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

  const handleFilterChange = (key: keyof InventoryFilter, value: string | boolean | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value || undefined }))
    setPage(1)
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
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
        Error loading inventory: {error?.message}
      </div>
    )
  }

  const items = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Inventory</h1>
          <p className="text-secondary-600 mt-1">Manage stock across all warehouses</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="btn btn-secondary gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <Link to="/inventory/new" className="btn btn-primary gap-2">
            <Plus className="w-4 h-4" />
            New Item
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
              placeholder="Search by SKU or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
            />
          </div>
          <select
            value={filters.warehouseId || ''}
            onChange={(e) => handleFilterChange('warehouseId', e.target.value)}
            className="select"
          >
            <option value="">All Warehouses</option>
            <option value="warehouse_001">Warehouse 1</option>
            <option value="warehouse_002">Warehouse 2</option>
          </select>
          <select
            value={filters.category || ''}
            onChange={(e) => handleFilterChange('category', e.target.value)}
            className="select"
          >
            <option value="">All Categories</option>
            <option value="electronics">Electronics</option>
            <option value="clothing">Clothing</option>
            <option value="food">Food</option>
          </select>
          <button
            type="button"
            onClick={() => handleFilterChange('lowStock', filters.lowStock ? undefined : true)}
            className={`btn ${filters.lowStock ? 'btn-primary' : 'btn-secondary'} gap-2`}
          >
            <AlertTriangle className="w-4 h-4" />
            Low Stock
          </button>
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
            {total} Item{total !== 1 ? 's' : ''}
          </h2>
        </div>
        
        {items.length === 0 ? (
          <div className="text-center py-12 text-secondary-500">
            <Warehouse className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No inventory items found</p>
            <p className="text-sm mt-1">Try adjusting your filters</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Warehouse</th>
                    <th>Stock Level</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="font-mono font-medium">{item.sku}</td>
                      <td className="max-w-[200px] truncate">{item.name}</td>
                      <td>{item.category || 'N/A'}</td>
                      <td>{item.warehouse_id || 'N/A'}</td>
                      <td>
                        <StockLevelIndicator 
                          quantity={item.quantity_on_hand} 
                          reorderPoint={item.reorder_point}
                        />
                      </td>
                      <td>
                        <InventoryStatusBadge status={item.status} />
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/inventory/${item.id}`}
                            className="p-2 text-secondary-500 hover:bg-secondary-100 rounded-lg"
                            title="View"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          <Link
                            to={`/inventory/${item.id}/edit`}
                            className="p-2 text-secondary-500 hover:bg-secondary-100 rounded-lg"
                            title="Edit"
                          >
                            <Edit className="w-4 h-4" />
                          </Link>
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

export default Inventory
