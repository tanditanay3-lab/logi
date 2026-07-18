import React, { useState } from 'react'
import { Settings as SettingsIcon, Save, X, Shield, Bell, Database, Users, Key } from 'lucide-react'

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState('general')
  const [settings, setSettings] = useState({
    companyName: 'Acme Logistics',
    defaultTenant: 'default',
    apiKey: '',
    trustLevel: 'propose_only',
    notificationsEnabled: true,
    emailNotifications: true,
    smsNotifications: false,
    voiceNotifications: false,
  })
  const [isSaving, setIsSaving] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    // Simulate saving
    await new Promise(resolve => setTimeout(resolve, 1000))
    setIsSaving(false)
    alert('Settings saved successfully!')
  }

  const handleCancel = () => {
    // Reset to default values
    setSettings({
      companyName: 'Acme Logistics',
      defaultTenant: 'default',
      apiKey: '',
      trustLevel: 'propose_only',
      notificationsEnabled: true,
      emailNotifications: true,
      smsNotifications: false,
      voiceNotifications: false,
    })
  }

  const tabs = [
    { id: 'general', label: 'General', icon: SettingsIcon },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'integrations', label: 'Integrations', icon: Database },
    { id: 'users', label: 'Users', icon: Users },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-secondary-900">Settings</h1>
        <p className="text-secondary-600 mt-1">Configure your Lanework instance</p>
      </div>

      {/* Tabs */}
      <div className="card">
        <div className="flex border-b border-secondary-200 mb-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-secondary-500 hover:text-secondary-700'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="space-y-6">
          {activeTab === 'general' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold text-secondary-900 mb-2">Company Information</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-secondary-700 mb-1">
                      Company Name
                    </label>
                    <input
                      type="text"
                      value={settings.companyName}
                      onChange={(e) => setSettings({...settings, companyName: e.target.value})}
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-secondary-700 mb-1">
                      Default Tenant
                    </label>
                    <select
                      value={settings.defaultTenant}
                      onChange={(e) => setSettings({...settings, defaultTenant: e.target.value})}
                      className="select"
                    >
                      <option value="default">Default</option>
                      <option value="tenant_001">Tenant 1</option>
                      <option value="tenant_002">Tenant 2</option>
                    </select>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-secondary-900 mb-2">Default Trust Level</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <label className="flex items-center gap-2 p-4 border border-secondary-200 rounded-lg cursor-pointer hover:bg-secondary-50">
                    <input
                      type="radio"
                      name="trustLevel"
                      value="propose_only"
                      checked={settings.trustLevel === 'propose_only'}
                      onChange={(e) => setSettings({...settings, trustLevel: e.target.value})}
                      className="sr-only"
                    />
                    <div className={`w-4 h-4 rounded-full border-2 ${settings.trustLevel === 'propose_only' ? 'border-primary-500 bg-primary-500' : 'border-secondary-300'}`} />
                    <div>
                      <p className="font-medium">Propose Only</p>
                      <p className="text-sm text-secondary-500">All actions require approval</p>
                    </div>
                  </label>
                  <label className="flex items-center gap-2 p-4 border border-secondary-200 rounded-lg cursor-pointer hover:bg-secondary-50">
                    <input
                      type="radio"
                      name="trustLevel"
                      value="auto_execute_low_risk"
                      checked={settings.trustLevel === 'auto_execute_low_risk'}
                      onChange={(e) => setSettings({...settings, trustLevel: e.target.value})}
                      className="sr-only"
                    />
                    <div className={`w-4 h-4 rounded-full border-2 ${settings.trustLevel === 'auto_execute_low_risk' ? 'border-primary-500 bg-primary-500' : 'border-secondary-300'}`} />
                    <div>
                      <p className="font-medium">Auto-Execute Low Risk</p>
                      <p className="text-sm text-secondary-500">Low-risk actions auto-execute</p>
                    </div>
                  </label>
                  <label className="flex items-center gap-2 p-4 border border-secondary-200 rounded-lg cursor-pointer hover:bg-secondary-50">
                    <input
                      type="radio"
                      name="trustLevel"
                      value="fully_autonomous"
                      checked={settings.trustLevel === 'fully_autonomous'}
                      onChange={(e) => setSettings({...settings, trustLevel: e.target.value})}
                      className="sr-only"
                    />
                    <div className={`w-4 h-4 rounded-full border-2 ${settings.trustLevel === 'fully_autonomous' ? 'border-primary-500 bg-primary-500' : 'border-secondary-300'}`} />
                    <div>
                      <p className="font-medium">Fully Autonomous</p>
                      <p className="text-sm text-secondary-500">All actions auto-execute</p>
                    </div>
                  </label>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold text-secondary-900 mb-2">API Key</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-secondary-700 mb-1">
                      Current API Key
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="password"
                        value={settings.apiKey}
                        onChange={(e) => setSettings({...settings, apiKey: e.target.value})}
                        className="flex-1 input"
                        placeholder="Enter API key"
                      />
                      <button className="btn btn-secondary px-4">Generate New</button>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-secondary-900 mb-2">Session Settings</h2>
                <div className="space-y-4">
                  <label className="flex items-center justify-between cursor-pointer">
                    <div>
                      <p className="font-medium">Require Authentication</p>
                      <p className="text-sm text-secondary-500">Require API key for all requests</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={true}
                      className="w-5 h-5 rounded-lg"
                      disabled
                    />
                  </label>
                  <label className="flex items-center justify-between cursor-pointer">
                    <div>
                      <p className="font-medium">Session Timeout</p>
                      <p className="text-sm text-secondary-500">Automatically log out after inactivity</p>
                    </div>
                    <select className="select w-32">
                      <option value="30">30 minutes</option>
                      <option value="60">1 hour</option>
                      <option value="1440">24 hours</option>
                    </select>
                  </label>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold text-secondary-900 mb-2">Notification Preferences</h2>
                <div className="space-y-4">
                  <label className="flex items-center justify-between cursor-pointer">
                    <div>
                      <p className="font-medium">Enable Notifications</p>
                      <p className="text-sm text-secondary-500">Receive notifications for important events</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={settings.notificationsEnabled}
                      onChange={(e) => setSettings({...settings, notificationsEnabled: e.target.checked})}
                      className="w-5 h-5 rounded-lg"
                    />
                  </label>
                  
                  {settings.notificationsEnabled && (
                    <div className="space-y-4 pl-6">
                      <label className="flex items-center justify-between cursor-pointer">
                        <div>
                          <p className="font-medium">Email Notifications</p>
                          <p className="text-sm text-secondary-500">Send notifications via email</p>
                        </div>
                        <input
                          type="checkbox"
                          checked={settings.emailNotifications}
                          onChange={(e) => setSettings({...settings, emailNotifications: e.target.checked})}
                          className="w-5 h-5 rounded-lg"
                        />
                      </label>
                      <label className="flex items-center justify-between cursor-pointer">
                        <div>
                          <p className="font-medium">SMS Notifications</p>
                          <p className="text-sm text-secondary-500">Send notifications via SMS</p>
                        </div>
                        <input
                          type="checkbox"
                          checked={settings.smsNotifications}
                          onChange={(e) => setSettings({...settings, smsNotifications: e.target.checked})}
                          className="w-5 h-5 rounded-lg"
                        />
                      </label>
                      <label className="flex items-center justify-between cursor-pointer">
                        <div>
                          <p className="font-medium">Voice Notifications</p>
                          <p className="text-sm text-secondary-500">Send notifications via voice call</p>
                        </div>
                        <input
                          type="checkbox"
                          checked={settings.voiceNotifications}
                          onChange={(e) => setSettings({...settings, voiceNotifications: e.target.checked})}
                          className="w-5 h-5 rounded-lg"
                        />
                      </label>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold text-secondary-900 mb-2">Third-Party Integrations</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 border border-secondary-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">Carrier APIs</h3>
                      <span className="badge badge-success">Connected</span>
                    </div>
                    <p className="text-sm text-secondary-500">FedEx, UPS, USPS, DHL</p>
                  </div>
                  <div className="p-4 border border-secondary-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">Maps API</h3>
                      <span className="badge badge-success">Connected</span>
                    </div>
                    <p className="text-sm text-secondary-500">Google Maps</p>
                  </div>
                  <div className="p-4 border border-secondary-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">SIP Trunk</h3>
                      <span className="badge badge-warning">Not Configured</span>
                    </div>
                    <p className="text-sm text-secondary-500">Twilio, Vonage, Telnyx</p>
                  </div>
                  <div className="p-4 border border-secondary-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">Database</h3>
                      <span className="badge badge-success">Connected</span>
                    </div>
                    <p className="text-sm text-secondary-500">PostgreSQL</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'users' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold text-secondary-900 mb-2">User Management</h2>
                <div className="bg-secondary-50 rounded-lg p-4">
                  <p className="text-secondary-500">User management is coming soon.</p>
                  <p className="text-sm text-secondary-400 mt-1">Manage users and permissions in Phase 2</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-6 border-t border-secondary-200">
          <button
            onClick={handleCancel}
            className="btn btn-secondary gap-2"
            disabled={isSaving}
          >
            <X className="w-4 h-4" />
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="btn btn-primary gap-2"
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Settings
