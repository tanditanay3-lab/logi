import { Link } from 'react-router-dom'
import { Building2, Users, Settings, BarChart3, Activity, Package, Truck, Route } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'

export function DashboardPage() {
  const stats = [
    { label: 'Organizations', value: '0', icon: Building2, href: '/organizations' },
    { label: 'Users', value: '0', icon: Users, href: '/users' },
    { label: 'Plans', value: '0', icon: Package, href: '/plans' },
    { label: 'Active Routes', value: '0', icon: Route, href: '#' },
  ]

  const quickActions = [
    { label: 'Create Organization', href: '/organizations', icon: Building2 },
    { label: 'Manage Users', href: '/users', icon: Users },
    { label: 'View Plans', href: '/plans', icon: Package },
    { label: 'Settings', href: '#', icon: Settings },
  ]

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-lg p-6 text-white">
        <h1 className="text-2xl font-bold mb-2">Welcome to Lanework SaaS</h1>
        <p className="text-indigo-100">
          Manage your organization, users, and access to the Lanework agent platform.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <Card key={stat.label} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.label}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickActions.map((action) => (
            <Card key={action.label} className="hover:shadow-md transition-shadow">
              <CardContent className="pt-6">
                <div className="flex flex-col items-center space-y-3">
                  <action.icon className="h-8 w-8 text-indigo-600" />
                  <span className="font-medium">{action.label}</span>
                  <Button asChild variant="outline" size="sm">
                    <Link to={action.href}>Go to</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
        <Card>
          <CardHeader>
            <CardTitle>Activity Feed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-center py-8 text-muted-foreground">
              <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No recent activity</p>
              <p className="text-sm mt-1">Activity will appear here as you use the platform</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
