import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Package,
  Warehouse,
  Truck,
  Users,
  MessageSquare,
  CheckCircle,
  Settings,
  BarChart3,
  Bell,
  X
} from 'lucide-react'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const location = useLocation()

  const navItems = [
    { 
      name: 'Dashboard', 
      href: '/', 
      icon: LayoutDashboard,
      exact: true
    },
    { 
      name: 'Shipments', 
      href: '/shipments', 
      icon: Package,
      badge: 'NEW'
    },
    { 
      name: 'Inventory', 
      href: '/inventory', 
      icon: Warehouse
    },
    { 
      name: 'Routes', 
      href: '/routes', 
      icon: Truck
    },
    { 
      name: 'Chat Copilot', 
      href: '/chat', 
      icon: MessageSquare,
      badge: 'BETA'
    },
    { 
      name: 'Agent Tasks', 
      href: '/agent-tasks', 
      icon: CheckCircle
    },
    { 
      name: 'Approvals', 
      href: '/approvals', 
      icon: Users,
      badge: '3' // Would be dynamic
    },
    { 
      name: 'Analytics', 
      href: '/analytics', 
      icon: BarChart3,
      comingSoon: true
    },
    { 
      name: 'Notifications', 
      href: '/notifications', 
      icon: Bell,
      comingSoon: true
    },
    { 
      name: 'Settings', 
      href: '/settings', 
      icon: Settings
    },
  ]

  const NavItem: React.FC<{
    item: {
      name: string
      href: string
      icon: React.ElementType
      exact?: boolean
      badge?: string
      comingSoon?: boolean
    }
  }> = ({ item }) => {
    const isActive = item.exact 
      ? location.pathname === item.href 
      : location.pathname.startsWith(item.href)

    return (
      <NavLink
        to={item.href}
        className={({ isActive }) => 
          isActive 
            ? 'sidebar-link-active' 
            : 'sidebar-link-inactive'
        }
        onClick={onClose}
      >
        <item.icon className="w-5 h-5" />
        <span className="flex-1">{item.name}</span>
        {item.badge && !item.comingSoon && (
          <span className="px-2 py-0.5 bg-primary-100 text-primary-700 text-xs font-medium rounded-full">
            {item.badge}
          </span>
        )}
        {item.comingSoon && (
          <span className="px-2 py-0.5 bg-secondary-200 text-secondary-600 text-xs font-medium rounded-full">
            Soon
          </span>
        )}
      </NavLink>
    )
  }

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside 
        className={`fixed top-0 left-0 z-50 h-full w-64 bg-white border-r border-secondary-200 transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:z-auto ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-secondary-200">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <Truck className="w-5 h-5 text-white" />
            </div>
            <span className="font-semibold text-secondary-900">Lanework</span>
          </div>
          <button onClick={onClose} className="lg:hidden p-1 rounded-lg hover:bg-secondary-100">
            <X className="w-5 h-5 text-secondary-500" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex flex-col p-4">
          <div className="space-y-1">
            {navItems.map((item) => (
              <NavItem key={item.name} item={item} />
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-secondary-200 bg-secondary-50">
          <div className="text-xs text-secondary-500">
            <p>v1.0.0</p>
            <p className="mt-1">Agentic Operating System</p>
          </div>
        </div>
      </aside>
    </>
  )
}

export default Sidebar
