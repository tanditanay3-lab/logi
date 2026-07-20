import { useState, useEffect } from 'react'
import { Package, Plus, Loader2, MoreVertical, Pencil, Trash2, DollarSign, Users, Calendar } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { planApi } from '../lib/api'
import toast from 'react-hot-toast'

interface Plan {
  id: string
  name: string
  description: string
  price: number
  interval: string
  trial_period_days: number
  max_agent_tasks_per_month: number
  max_api_calls_per_month: number
  max_storage_gb: number
  max_voice_minutes_per_month: number
  max_shipments_tracked: number
  max_routes_optimized: number
  max_inventory_items: number
  features: any
  stripe_price_id: string
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchPlans()
  }, [])

  const fetchPlans = async () => {
    try {
      setIsLoading(true)
      const response = await planApi.list()
      setPlans(response.data.plans || [])
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to fetch plans')
    } finally {
      setIsLoading(false)
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(price)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Plans</h1>
        <p className="text-muted-foreground mt-1">
          Manage pricing plans for your SaaS
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : plans.length === 0 ? (
        <Card>
          <CardContent className="pt-8 text-center">
            <Package className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No plans yet</h3>
            <p className="text-muted-foreground mb-4">
              Create your first plan to get started
            </p>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Plan
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map((plan) => (
            <Card key={plan.id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      {plan.name}
                    </CardTitle>
                    <CardDescription>{plan.description}</CardDescription>
                  </div>
                  <Button variant="ghost" size="icon">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="text-3xl font-bold">
                    {formatPrice(plan.price)}
                    <span className="text-sm font-normal text-muted-foreground">
                      /{plan.interval}
                    </span>
                  </div>

                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-muted-foreground" />
                      <span>{plan.max_agent_tasks_per_month.toLocaleString()} agent tasks/month</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span>{plan.trial_period_days} day trial</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-muted-foreground" />
                      <span>{plan.max_api_calls_per_month.toLocaleString()} API calls/month</span>
                    </div>
                  </div>

                  <div className="pt-4 border-t space-y-2">
                    <p className="text-sm font-medium">Features:</p>
                    <div className="grid grid-cols-2 gap-1 text-xs">
                      {Object.entries(plan.features).map(([key, value]) => (
                        <div key={key} className="flex items-center gap-1">
                          <span className="text-green-500">●</span>
                          <span>{key}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2 pt-4">
                    <Button variant="outline" size="sm" className="flex-1">
                      <Pencil className="h-3 w-3 mr-1" />
                      Edit
                    </Button>
                    <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                      <Trash2 className="h-3 w-3 mr-1" />
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
