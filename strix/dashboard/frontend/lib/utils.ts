import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Merge class names with Tailwind CSS support
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format duration in minutes to a human-readable string
 * @param minutes - Duration in minutes
 * @returns Formatted string (e.g., "1h 30m", "45m", "2h")
 */
export function formatDuration(minutes: number | null | undefined): string {
  if (minutes == null || isNaN(minutes) || minutes < 0) return '0m'
  
  const hours = Math.floor(minutes / 60)
  const mins = Math.round(minutes % 60)
  
  if (hours === 0) {
    return `${mins}m`
  }
  
  if (mins === 0) {
    return `${hours}h`
  }
  
  return `${hours}h ${mins}m`
}

/**
 * Format a timestamp or Date to a localized time string
 * @param date - Date object, timestamp string, or number, or null/undefined
 * @returns Formatted time string (e.g., "2:30:45 PM") or "--" if invalid
 */
export function formatTime(date: Date | string | number | null | undefined): string {
  if (!date) return '--'
  
  try {
    const d = typeof date === 'string' || typeof date === 'number' 
      ? new Date(date) 
      : date
    
    if (isNaN(d.getTime())) {
      return '--'
    }
    
    return d.toLocaleTimeString()
  } catch {
    return '--'
  }
}

/**
 * Format a timestamp to a relative time string
 * @param timestamp - ISO timestamp string or Date, or null/undefined
 * @returns Relative time string (e.g., "2 minutes ago", "just now")
 */
export function formatRelativeTime(timestamp: string | Date | null | undefined): string {
  if (!timestamp) return '--'
  
  try {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
    if (isNaN(date.getTime())) return '--'
    
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    const diffHours = Math.floor(diffMins / 60)
    
    if (diffSecs < 10) return 'just now'
    if (diffSecs < 60) return `${diffSecs}s ago`
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    
    return date.toLocaleDateString()
  } catch {
    return '--'
  }
}

/**
 * Truncate a string to a maximum length with ellipsis
 * @param str - String to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated string with ellipsis if needed
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return str.slice(0, maxLength - 3) + '...'
}
