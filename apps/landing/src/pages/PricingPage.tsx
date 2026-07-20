import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Check, X, Star, Rocket, Clock, Users, Package } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card'
import { formatPrice } from '../lib/utils'
import { plansApi } from '../lib/api'
import toast from 'react-hot-toast'

interface Plan {
  id: string
  name: string
  description: string
  price: number
  interval: string
  trial_period_days: number
  features: Record<string, boolean>
  max_agent_tasks_per_month: number
  max_api_calls_per_month: number
  max_shipments_tracked: number
  is_active: boolean
  sort_order: number
}

export function PricingPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')

  useEffect(() => {
    fetchPlans()
  }, [])

  const fetchPlans = async () => {
    try {
      setIsLoading(true)
      const response = await plansApi.list()
      setPlans(response.data.plans || [])
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to fetch plans')
      // Fallback to demo plans
      setPlans([
        {
          id: 'plan_starter',
          name: 'Starter',
          description: 'Perfect for small logistics operations',
          price: 299,
          interval: 'monthly',
          trial_period_days: 14,
          features: {
            shipment_tracking: true,
            route_optimization: true,
            inventory_management: false,
            voice_agent: false,
            demand_forecasting: false,
            fleet_management: false,
          },
          max_agent_tasks_per_month: 1000,
          max_api_calls_per_month: 10000,
          max_shipments_tracked: 1000,
          is_active: true,
          sort_order: 1,
        },
        {
          id: 'plan_pro',
          name: 'Professional',
          description: 'For growing logistics businesses',
          price: 799,
          interval: 'monthly',
          trial_period_days: 14,
          features: {
            shipment_tracking: true,
            route_optimization: true,
            inventory_management: true,
            voice_agent: true,
            demand_forecasting: false,
            fleet_management: false,
          },
          max_agent_tasks_per_month: 10000,
          max_api_calls_per_month: 100000,
          max_shipments_tracked: 10000,
          is_active: true,
          sort_order: 2,
        },
        {
          id: 'plan_enterprise',
          name: 'Enterprise',
          description: 'For large-scale logistics operations',
          price: 1999,
          interval: 'monthly',
          trial_period_days: 30,
          features: {
            shipment_tracking: true,
            route_optimization: true,
            inventory_management: true,
            voice_agent: true,
            demand_forecasting: true,
            fleet_management: true,
          },
          max_agent_tasks_per_month: 100000,
          max_api_calls_per_month: 1000000,
          max_shipments_tracked: 100000,
          is_active: true,
          sort_order: 3,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const popularPlan = plans.find(p => p.name === 'Professional') || plans[1]

  const featureList = [
    'Shipment Tracking',
    'Route Optimization',
    'Inventory Management',
    'Voice Agent',
    'Demand Forecasting',
    'Fleet Management',
  ]

  return (
    <div className="space-y-16">
      {/* Header */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4"
          >
            Simple, Transparent Pricing
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-xl text-gray-600 max-w-2xl mx-auto"
          >
            Choose the plan that fits your logistics operation. All plans include a free trial.
          </motion.p>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="flex justify-center mt-8"
          >
            <div className="bg-gray-100 rounded-lg p-1 flex">
              <button
                onClick={() => setBillingCycle('monthly')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  billingCycle === 'monthly'
                    ? 'bg-white text-gray-900 shadow'
                    : 'text-gray-600'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingCycle('yearly')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  billingCycle === 'yearly'
                    ? 'bg-white text-gray-900 shadow'
                    : 'text-gray-600'
                }`}
              >
                Yearly (Save 20%)
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Loading pricing...</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {plans.map((plan, index) => {
                const isPopular = plan.id === popularPlan?.id
                const price = billingCycle === 'yearly' ? plan.price * 12 * 0.8 : plan.price
                const interval = billingCycle === 'yearly' ? 'year' : plan.interval
                
                return (
                  <motion.div
                    key={plan.id}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: index * 0.1 }}
                    className="relative"
                  >
                    {isPopular && (
                      <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                        <span className="bg-gradient-to-r from-blue-500 to-indigo-600 text-white px-4 py-1 rounded-full text-sm font-medium">
                          Most Popular
                        </span>
                      </div>
                    )}
                    
                    <Card className={`h-full ${isPopular ? 'border-2 border-blue-600 shadow-xl' : ''}`}>
                      <CardHeader>
                        <CardTitle className="text-center">{plan.name}</CardTitle>
                        <CardDescription className="text-center">{plan.description}</CardDescription>
                      </CardHeader>
                      
                      <CardContent className="text-center">
                        <div className="mb-6">
                          <span className="text-4xl font-bold text-gray-900">
                            {formatPrice(price, interval)}
                          </span>
                          {billingCycle === 'yearly' && (
                            <span className="ml-2 text-sm text-green-600 bg-green-100 px-2 py-1 rounded">
                              20% off
                            </span>
                          )}
                        </div>
                        
                        <div className="mb-6">
                          <p className="text-sm text-gray-600 mb-2">Includes:</p>
                          <ul className="space-y-2 text-sm">
                            <li className="flex items-center justify-center">
                              <Check className="h-4 w-4 text-green-500 mr-2" />
                              {plan.max_agent_tasks_per_month.toLocaleString()} agent tasks/month
                            </li>
                            <li className="flex items-center justify-center">
                              <Check className="h-4 w-4 text-green-500 mr-2" />
                              {plan.max_api_calls_per_month.toLocaleString()} API calls/month
                            </li>
                            <li className="flex items-center justify-center">
                              <Check className="h-4 w-4 text-green-500 mr-2" />
                              {plan.max_shipments_tracked.toLocaleString()} shipments tracked
                            </li>
                            <li className="flex items-center justify-center">
                              <Check className="h-4 w-4 text-green-500 mr-2" />
                              {plan.trial_period_days} day free trial
                            </li>
                          </ul>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 mb-6">
                          {Object.entries(plan.features).map(([key, value]) => {
                            const featureName = featureList.find(f => 
                              key.toLowerCase().includes(f.toLowerCase()) || 
                              f.toLowerCase().includes(key.toLowerCase())
                            ) || key
                            return (
                              <div key={key} className="flex items-center">
                                {value ? (
                                  <Check className="h-3 w-3 text-green-500 mr-1" />
                                ) : (
                                  <X className="h-3 w-3 text-red-500 mr-1" />
                                )}
                                <span>{featureName}</span>
                              </div>
                            )
                          })}
                        </div>
                      </CardContent>
                      
                      <CardFooter>
                        <Button 
                          size="lg" 
                          className="w-full"
                          asChild
                        >
                          <Link to="http://localhost:3000/onboarding">
                            Get Started
                          </Link>
                        </Button>
                      </CardFooter>
                    </Card>
                  </motion.div>
                )
              })}
            </div>
          )}
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-16 bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              Frequently Asked Questions
            </h2>
            <p className="text-xl text-gray-600">
              Everything you need to know about Lanework
            </p>
          </motion.div>
          
          <div className="space-y-4">
            {[
              {
                question: 'What is Lanework?',
                answer: 'Lanework is an AI-powered logistics operating system that automates your logistics operations with 9 specialized agents working continuously in the background.',
              },
              {
                question: 'How does the free trial work?',
                answer: 'All plans include a free trial period (14 days for most plans, 30 days for Enterprise). No credit card required to start.',
              },
              {
                question: 'Can I upgrade or downgrade my plan?',
                answer: 'Yes, you can change your plan at any time. Upgrades take effect immediately, and downgrades apply at the start of your next billing cycle.',
              },
              {
                question: 'What agents are included?',
                answer: 'We have 9 specialized agents: Shipment Tracking, Inventory Management, Route Optimization, Warehouse Operations, Fleet Management, Customer Communication, Demand Forecasting, Freight Procurement, and Voice Agent.',
              },
              {
                question: 'Is there a limit to the number of users?',
                answer: 'No, all plans include unlimited users. You can add as many team members as you need.',
              },
            ].map((faq, index) => (
              <motion.div
                key={faq.question}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="border rounded-lg p-6"
              >
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{faq.question}</h3>
                <p className="text-gray-600">{faq.answer}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl font-bold text-gray-900 mb-4"
          >
            Ready to Get Started?
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-xl text-gray-600 max-w-2xl mx-auto mb-8"
          >
            Join the future of logistics automation today.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <Button size="lg" asChild>
              <Link to="http://localhost:3000/onboarding">
                Start Free Trial
                <Rocket className="h-5 w-5 ml-2" />
              </Link>
            </Button>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
