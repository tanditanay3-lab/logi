import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, ArrowRight, User, Building2, Key } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'

export function OnboardingPage({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({
    orgName: '',
    email: '',
    name: '',
    password: '',
  })
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleNext = () => {
    if (step === 1 && !formData.orgName.trim()) {
      toast.error('Please enter your organization name')
      return
    }
    if (step === 2) {
      if (!formData.email.trim() || !formData.email.includes('@')) {
        toast.error('Please enter a valid email')
        return
      }
      if (!formData.password || formData.password.length < 8) {
        toast.error('Password must be at least 8 characters')
        return
      }
    }
    setStep(step + 1)
  }

  const handleBack = () => {
    if (step > 1) setStep(step - 1)
  }

  const handleSubmit = async () => {
    setIsLoading(true)
    
    try {
      // Register user (which creates org and user)
      const response = await authApi.register(
        formData.email,
        formData.password,
        formData.name || formData.email
      )
      
      const { access_token, user } = response.data
      
      // Store token
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('user', JSON.stringify(user))
      
      // Notify parent
      onComplete()
      
      // Redirect to dashboard
      navigate('/')
      
      toast.success('Account created successfully!')
    } catch (error: any) {
      const message = error.response?.data?.error?.message || 
                     error.response?.data?.detail ||
                     'Registration failed'
      toast.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  const steps = [
    {
      title: 'Organization',
      description: 'Tell us about your organization',
      icon: <Building2 className="h-8 w-8 text-indigo-600" />,
      content: (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Organization Name
            </label>
            <input
              type="text"
              value={formData.orgName}
              onChange={(e) => handleInputChange('orgName', e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Your Company Name"
            />
          </div>
        </div>
      ),
    },
    {
      title: 'Account',
      description: 'Create your admin account',
      icon: <User className="h-8 w-8 text-indigo-600" />,
      content: (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Your Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Your Name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Create a password"
            />
          </div>
        </div>
      ),
    },
    {
      title: 'Complete',
      description: 'Ready to get started',
      icon: <Key className="h-8 w-8 text-indigo-600" />,
      content: (
        <div className="text-center space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <h3 className="text-lg font-semibold text-green-800">All set!</h3>
            <p className="text-sm text-green-600 mt-1">
              Your organization and account have been created.
            </p>
          </div>
        </div>
      ),
    },
  ]

  const currentStep = steps[step - 1]

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="w-full max-w-2xl p-8 bg-white rounded-lg shadow-xl">
        {/* Progress Steps */}
        <div className="flex justify-between items-center mb-8">
          {steps.map((s, index) => (
            <div key={index} className="flex items-center">
              <div className="flex flex-col items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center border-2 ${
                    step > index + 1
                      ? 'bg-indigo-600 border-indigo-600 text-white'
                      : step === index + 1
                      ? 'bg-indigo-600 border-indigo-600 text-white'
                      : 'bg-white border-gray-300 text-gray-400'
                  }`}
                >
                  {step > index + 1 ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </div>
                <p className={`text-sm mt-2 ${step >= index + 1 ? 'text-indigo-600 font-medium' : 'text-gray-400'}`}>
                  {s.title}
                </p>
              </div>
              {index < steps.length - 1 && (
                <div className={`w-full h-1 mx-2 rounded ${step > index + 1 ? 'bg-indigo-600' : 'bg-gray-200'}`} style={{ minWidth: '60px' }} />
              )}
            </div>
          ))}
        </div>

        {/* Step Content */}
        <div className="mb-8">
          <div className="flex items-center justify-center mb-4">
            {currentStep.icon}
          </div>
          <h2 className="text-2xl font-bold text-center text-gray-900 mb-2">
            {currentStep.title}
          </h2>
          <p className="text-center text-gray-600 mb-6">
            {currentStep.description}
          </p>
          
          {currentStep.content}
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between">
          {step > 1 ? (
            <button
              onClick={handleBack}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              Back
            </button>
          ) : (
            <div />
          )}
          
          {step < steps.length ? (
            <button
              onClick={handleNext}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-indigo-600 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 flex items-center"
            >
              Continue
              <ArrowRight className="ml-1 h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-green-600 border border-green-600 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 flex items-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating Account...
                </>
              ) : (
                <>
                  Complete Setup
                  <ArrowRight className="ml-1 h-4 w-4" />
                </>
              )}
            </button>
          )}
        </div>

        <div className="text-center text-sm text-gray-500 mt-4">
          <p>
            Already have an account?{' '}
            <button
              onClick={() => navigate('/login')}
              className="font-medium text-indigo-600 hover:text-indigo-500"
            >
              Log in
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
