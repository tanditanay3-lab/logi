import React, { useState } from 'react'
import { Bell, Check, X, AlertTriangle, Package, Truck, Warehouse } from 'lucide-react'

interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  icon?: React.ElementType
  createdAt: string
  read: boolean
}

const NotificationCenter: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([
    {
      id: '1',
      type: 'success',
      title: 'Shipment Delivered',
      message: 'Shipment 1234567890 has been delivered to destination',
      icon: Package,
      createdAt: new Date(Date.now() - 3600000).toISOString(),
      read: false
    },
    {
      id: '2',
      type: 'warning',
      title: 'Low Stock Alert',
      message: 'SKU-001 is below reorder point (50 units remaining)',
      icon: Warehouse,
      createdAt: new Date(Date.now() - 1800000).toISOString(),
      read: false
    },
    {
      id: '3',
      type: 'info',
      title: 'Route Optimized',
      message: 'Route ROUTE-001 has been optimized with 5 stops',
      icon: Truck,
      createdAt: new Date(Date.now() - 900000).toISOString(),
      read: true
    },
  ])

  const unreadCount = notifications.filter(n => !n.read).length

  const toggleOpen = () => {
    setIsOpen(!isOpen)
  }

  const markAsRead = (id: string) => {
    setNotifications(notifications.map(n => 
      n.id === id ? { ...n, read: true } : n
    ))
  }

  const markAllAsRead = () => {
    setNotifications(notifications.map(n => ({ ...n, read: true })))
  }

  const clearAll = () => {
    setNotifications([])
  }

  const getIconColor = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return 'text-green-500'
      case 'warning':
        return 'text-yellow-500'
      case 'error':
        return 'text-red-500'
      case 'info':
        return 'text-blue-500'
      default:
        return 'text-secondary-500'
    }
  }

  const getBgColor = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return 'bg-green-50'
      case 'warning':
        return 'bg-yellow-50'
      case 'error':
        return 'bg-red-50'
      case 'info':
        return 'bg-blue-50'
      default:
        return 'bg-secondary-50'
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

  return (
    <div className="relative">
      {/* Notification bell */}
      <button
        onClick={toggleOpen}
        className="relative p-2 rounded-lg bg-secondary-100 hover:bg-secondary-200 transition-colors"
      >
        <Bell className="w-5 h-5 text-secondary-600" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
            {unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-40 bg-transparent"
            onClick={toggleOpen}
          />
          
          {/* Dropdown panel */}
          <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl shadow-lg border border-secondary-200 z-50 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-secondary-200">
              <h3 className="font-semibold text-secondary-900">Notifications</h3>
              <div className="flex gap-2">
                <button
                  onClick={markAllAsRead}
                  className="text-sm text-secondary-600 hover:text-secondary-900"
                >
                  Mark all as read
                </button>
                <button
                  onClick={clearAll}
                  className="text-sm text-red-600 hover:text-red-700"
                >
                  Clear all
                </button>
              </div>
            </div>

            {/* Notifications list */}
            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-8 text-center text-secondary-500">
                  <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No notifications</p>
                </div>
              ) : (
                notifications.map((notification) => (
                  <button
                    key={notification.id}
                    onClick={() => markAsRead(notification.id)}
                    className={`w-full p-4 text-left hover:bg-secondary-50 transition-colors ${notification.read ? 'bg-secondary-50' : 'bg-white'}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg ${getBgColor(notification.type)}`}>
                        {notification.icon ? (
                          <notification.icon className={`w-4 h-4 ${getIconColor(notification.type)}`} />
                        ) : (
                          <Bell className={`w-4 h-4 ${getIconColor(notification.type)}`} />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <p className="font-medium text-secondary-900">{notification.title}</p>
                          {!notification.read && (
                            <span className="w-2 h-2 bg-blue-500 rounded-full" />
                          )}
                        </div>
                        <p className="text-sm text-secondary-600">{notification.message}</p>
                        <p className="text-xs text-secondary-500 mt-1">
                          {formatTimeAgo(notification.createdAt)}
                        </p>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="p-3 border-t border-secondary-200 bg-secondary-50">
              <Link
                to="/notifications"
                onClick={toggleOpen}
                className="block text-center text-sm text-primary-600 hover:underline"
              >
                View all notifications
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default NotificationCenter
