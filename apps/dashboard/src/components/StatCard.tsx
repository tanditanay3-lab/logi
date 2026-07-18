import React from 'react'
import { ArrowUp, ArrowDown, TrendingUp, TrendingDown } from 'lucide-react'
import { clsx } from 'clsx'

interface StatCardProps {
  title: string
  value: number
  icon: React.ReactNode
  color: 'primary' | 'green' | 'blue' | 'purple' | 'red' | 'yellow'
  trend?: number
  trendDirection?: 'up' | 'down'
  children?: React.ReactNode
}

const colorClasses = {
  primary: {
    bg: 'bg-primary-50',
    text: 'text-primary-700',
    border: 'border-primary-200',
    trendUp: 'text-primary-600',
    trendDown: 'text-primary-600',
  },
  green: {
    bg: 'bg-green-50',
    text: 'text-green-700',
    border: 'border-green-200',
    trendUp: 'text-green-600',
    trendDown: 'text-green-600',
  },
  blue: {
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
    trendUp: 'text-blue-600',
    trendDown: 'text-blue-600',
  },
  purple: {
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    border: 'border-purple-200',
    trendUp: 'text-purple-600',
    trendDown: 'text-purple-600',
  },
  red: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
    trendUp: 'text-red-600',
    trendDown: 'text-red-600',
  },
  yellow: {
    bg: 'bg-yellow-50',
    text: 'text-yellow-700',
    border: 'border-yellow-200',
    trendUp: 'text-yellow-600',
    trendDown: 'text-yellow-600',
  },
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  color,
  trend,
  trendDirection,
  children,
}) => {
  const classes = colorClasses[color]

  const formatValue = (val: number): string => {
    if (val >= 1000) {
      return (val / 1000).toFixed(1) + 'K'
    }
    return val.toString()
  }

  const formatTrend = (trendVal: number | undefined, direction: 'up' | 'down' | undefined): string => {
    if (trendVal === undefined || direction === undefined) return ''
    const sign = direction === 'up' ? '+' : ''
    return `${sign}${trendVal}`
  }

  return (
    <div className="card">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-secondary-600">{title}</p>
          <p className="text-3xl font-bold text-secondary-900 mt-1">
            {formatValue(value)}
          </p>
        </div>
        <div className={clsx('p-2 rounded-lg', classes.bg)}>
          {icon}
        </div>
      </div>
      
      {trend !== undefined && trendDirection && (
        <div className="flex items-center gap-1 mt-4">
          {trendDirection === 'up' ? (
            <ArrowUp className={clsx('w-4 h-4', classes.trendUp)} />
          ) : (
            <ArrowDown className={clsx('w-4 h-4', classes.trendDown)} />
          )}
          <span className={clsx('text-sm font-medium', 
            trendDirection === 'up' ? classes.trendUp : classes.trendDown
          )}>
            {formatTrend(trend, trendDirection)}
          </span>
        </div>
      )}
      
      {children && (
        <div className="mt-4 pt-4 border-t border-secondary-200">
          {children}
        </div>
      )}
    </div>
  )
}

export default StatCard
