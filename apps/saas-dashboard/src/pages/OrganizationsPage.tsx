import { useState, useEffect } from 'react'
import { Building2, Plus, Loader2, MoreVertical, Pencil, Trash2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { orgApi } from '../lib/api'
import toast from 'react-hot-toast'

interface Organization {
  id: string
  name: string
  slug: string
  status: string
  created_at: string
  updated_at: string
}

export function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [newOrgName, setNewOrgName] = useState('')

  useEffect(() => {
    fetchOrganizations()
  }, [])

  const fetchOrganizations = async () => {
    try {
      setIsLoading(true)
      const response = await orgApi.list()
      setOrganizations(response.data.organizations || [])
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to fetch organizations')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!newOrgName.trim()) {
      toast.error('Please enter an organization name')
      return
    }

    try {
      setIsCreating(true)
      const response = await orgApi.create({ name: newOrgName })
      setOrganizations([...organizations, response.data])
      setNewOrgName('')
      setIsCreating(false)
      toast.success('Organization created successfully!')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to create organization')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Organizations</h1>
          <p className="text-muted-foreground mt-1">
            Manage your organizations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newOrgName}
            onChange={(e) => setNewOrgName(e.target.value)}
            placeholder="Organization name"
            className="px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <Button onClick={handleCreate} disabled={isCreating || !newOrgName.trim()}>
            {isCreating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Plus className="h-4 w-4 mr-2" />
                Create
              </>
            )}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : organizations.length === 0 ? (
        <Card>
          <CardContent className="pt-8 text-center">
            <Building2 className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No organizations yet</h3>
            <p className="text-muted-foreground mb-4">
              Create your first organization to get started
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {organizations.map((org) => (
            <Card key={org.id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Building2 className="h-5 w-5" />
                      {org.name}
                    </CardTitle>
                  </div>
                  <Button variant="ghost" size="icon">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    ID: {org.id}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Slug: {org.slug}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Status: {org.status}
                  </p>
                </div>
                <div className="flex gap-2 mt-4">
                  <Button variant="outline" size="sm">
                    <Pencil className="h-3 w-3 mr-1" />
                    Edit
                  </Button>
                  <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                    <Trash2 className="h-3 w-3 mr-1" />
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
