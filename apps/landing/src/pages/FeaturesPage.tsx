import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Truck, Package, Route, Warehouse, BarChart3, Voice, Robot, Zap, Shield, Clock, Users } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'

export function FeaturesPage() {
  const agentFeatures = [
    {
      icon: Truck,
      title: 'Shipment Tracking Agent',
      description: 'Aggregates multi-carrier tracking into one timeline, detects delays proactively, and answers status questions conversationally.',
      benefits: [
        'Real-time tracking across all carriers',
        'Automatic delay detection and alerts',
        'ETA drift detection and notifications',
        'Customer status queries via chat/voice',
      ],
    },
    {
      icon: Package,
      title: 'Inventory Management Agent',
      description: 'Monitors stock across warehouses, predicts depletion, generates replenishment recommendations, and reconciles discrepancies.',
      benefits: [
        'Real-time inventory tracking',
        'Automated replenishment recommendations',
        'Stock discrepancy detection',
        'Multi-warehouse support',
      ],
    },
    {
      icon: Route,
      title: 'Route Optimization Agent',
      description: 'Generates and dynamically re-optimizes multi-stop routes against vehicle capacity, time windows, and driver hours.',
      benefits: [
        'Optimal route planning',
        'Dynamic re-optimization',
        'Vehicle capacity constraints',
        'Driver hours compliance',
      ],
    },
    {
      icon: Warehouse,
      title: 'Warehouse Operations Agent',
      description: 'Optimizes pick/pack sequencing, assigns tasks, manages dock scheduling, and forecasts labor needs.',
      benefits: [
        'Smart task sequencing',
        'Dock schedule management',
        'Labor demand forecasting',
        'Automated task assignment',
      ],
    },
    {
      icon: Users,
      title: 'Fleet & Driver Management Agent',
      description: 'Tracks vehicle maintenance windows and driver HOS compliance, matches drivers to routes, and flags compliance risk.',
      benefits: [
        'HOS compliance monitoring',
        'Vehicle maintenance tracking',
        'Driver-route matching',
        'Compliance risk alerts',
      ],
    },
    {
      icon: BarChart3,
      title: 'Demand Forecasting Agent',
      description: 'Forecasts demand by SKU/region/season and feeds signals to Inventory and Fleet agents for proactive planning.',
      benefits: [
        'Accurate demand predictions',
        'Seasonal trend analysis',
        'SKU-level forecasting',
        'Automated inventory signals',
      ],
    },
    {
      icon: Voice,
      title: 'Voice Agent',
      description: 'Answers inbound calls, routes requests to the right agent, and enables hands-free operations for drivers.',
      benefits: [
        'Hands-free driver check-ins',
        'Customer status queries by phone',
        'Issue reporting via voice',
        'Seamless human transfer',
      ],
    },
  ]

  const platformFeatures = [
    {
      icon: Zap,
      title: 'Autonomous Operations',
      description: 'Agents make low-risk decisions autonomously, escalating only when needed.',
    },
    {
      icon: Shield,
      title: 'Human-in-the-Loop',
      description: 'Every action is either auto-executed or proposed for approval based on configurable trust levels.',
    },
    {
      icon: Clock,
      title: '24/7 Monitoring',
      description: 'Agents work continuously, even when your team is offline.',
    },
    {
      icon: Users,
      title: 'Multi-Tenant',
      description: 'Complete data isolation between organizations with row-level security.',
    },
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
            Powerful Features for Modern Logistics
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-xl text-gray-600 max-w-2xl mx-auto"
          >
            Our 9 specialized AI agents work together to automate your entire logistics operation
          </motion.p>
        </div>
      </section>

      {/* Agent Features */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              Meet Our AI Agents
            </h2>
            <p className="text-lg text-gray-600">
              Each agent specializes in a specific logistics domain
            </p>
          </motion.div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {agentFeatures.map((agent, index) => (
              <motion.div
                key={agent.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.05 }}
              >
                <Card className="h-full hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                        <agent.icon className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <CardTitle>{agent.title}</CardTitle>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="mb-4">{agent.description}</CardDescription>
                    <ul className="space-y-2 text-sm">
                      {agent.benefits.map((benefit, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-green-500 mr-2 mt-0.5">●</span>
                          <span>{benefit}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Platform Features */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              Platform Features
            </h2>
            <p className="text-lg text-gray-600">
              Built for security, reliability, and scalability
            </p>
          </motion.div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {platformFeatures.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
              >
                <Card className="h-full text-center">
                  <CardHeader>
                    <div className="flex items-center justify-center w-12 h-12 bg-blue-100 rounded-lg mx-auto mb-4">
                      <feature.icon className="h-6 w-6 text-blue-600" />
                    </div>
                    <CardTitle>{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription>{feature.description}</CardDescription>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Trust Section */}
      <section className="py-16 bg-gradient-to-br from-blue-600 to-indigo-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl font-bold text-white mb-4"
          >
            Trusted by Logistics Companies Worldwide
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-xl text-blue-100 max-w-2xl mx-auto mb-8"
          >
            From small dispatch operations to large fleet managers, Lanework scales with your business.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <Button size="lg" variant="outline" className="text-white border-white hover:bg-white/10" asChild>
              <Link to="http://localhost:3000/onboarding">
                Start Your Free Trial
              </Link>
            </Button>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
