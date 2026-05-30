import { Component } from 'react'
import Button from './ui/Button'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4">
          <div className="rounded-full bg-red-500/10 p-4">
            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-zinc-200">Something went wrong</h2>
          <p className="text-sm text-zinc-400 text-center max-w-md">
            {(this.props.fallbackMessage || 'This page encountered an unexpected error.')}
          </p>
          {this.props.showError && (
            <pre className="text-xs text-red-400 bg-red-950/30 px-4 py-2 rounded-lg max-w-lg overflow-auto">
              {this.state.error?.message || 'Unknown error'}
            </pre>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              this.setState({ hasError: false, error: null })
              if (this.props.onReset) this.props.onReset()
            }}
          >
            Try again
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}
