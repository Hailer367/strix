// Simplified toast implementation - can be enhanced with proper toast library
export interface ToastOptions {
  title: string
  description?: string
  variant?: 'default' | 'destructive'
}

let toastHandler: ((options: ToastOptions) => void) | null = null

export function setToastHandler(handler: (options: ToastOptions) => void) {
  toastHandler = handler
}

export function toast(options: ToastOptions) {
  if (toastHandler) {
    toastHandler(options)
  } else {
    // Fallback to console
    console.log(`[Toast] ${options.title}: ${options.description || ''}`)
  }
}