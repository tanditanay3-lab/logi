import { Outlet, Link, useNavigate } from 'react-router-dom'
import { Building2, Users, Package, Settings, LogOut, Menu, X, BarChart3, Home } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../components/ui/button'
import { Sheet, SheetContent, SheetTrigger } from '../components/ui/sheet'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu'

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const navItems = [
    { label: 'Dashboard', href: '/', icon: Home },
    { label: 'Organizations', href: '/organizations', icon: Building2 },
    { label: 'Users', href: '/users', icon: Users },
    { label: 'Plans', href: '/plans', icon: Package },
    { label: 'Usage', href: '#', icon: BarChart3 },
    { label: 'Settings', href: '#', icon: Settings },
  ]

  const user = JSON.parse(localStorage.getItem('user') || '{}')

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile Sidebar */}
      <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="md:hidden fixed top-4 left-4 z-50">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-[250px] p-0">
          <div className="flex h-full flex-col">
            <div className="p-4 border-b">
              <h2 className="font-semibold text-lg">Lanework SaaS</h2>
            </div>
            <nav className="flex-1 p-2">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium hover:bg-muted transition-colors"
                >
                  <item.icon className="h-5 w-5" />
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="p-2 border-t">
              <Button variant="ghost" onClick={handleLogout} className="w-full justify-start">
                <LogOut className="h-5 w-5 mr-2" />
                Log out
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      {/* Desktop Sidebar */}
      <div className={`hidden md:flex flex-col border-r bg-background h-full transition-all duration-300 ${isCollapsed ? 'w-[80px]' : 'w-[250px]'}`}>
        <div className="p-4 border-b flex items-center justify-between">
          {!isCollapsed && <h2 className="font-semibold text-lg">Lanework SaaS</h2>}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            {isCollapsed ? <Menu className="h-5 w-5" /> : <X className="h-5 w-5" />}
          </Button>
        </div>
        
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              to={item.href}
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium hover:bg-muted transition-colors"
            >
              <item.icon className="h-5 w-5" />
              {!isCollapsed && item.label}
            </Link>
          ))}
        </nav>

        <div className="p-2 border-t">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="w-full justify-start">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center">
                    <span className="text-sm font-medium text-indigo-600">
                      {user.name?.charAt(0).toUpperCase() || 'U'}
                    </span>
                  </div>
                  {!isCollapsed && (
                    <>
                      <div className="flex flex-col items-start">
                        <span className="text-sm font-medium">{user.name || 'User'}</span>
                        <span className="text-xs text-muted-foreground">{user.email}</span>
                      </div>
                    </>
                  )}
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" side="right" className="w-[200px]">
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="border-b p-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="md:hidden">
              <Menu className="h-5 w-5" onClick={() => setIsMobileMenuOpen(true)} />
            </Button>
            <h1 className="text-xl font-semibold">Dashboard</h1>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
