import { useState, useEffect } from "react"

import { LoginForm } from "@/components/ui/login-form"
import { Dashboard } from "@/components/ui/dashboard"
import { verify, clearToken } from "@/lib/api"
import "./App.css"

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    verify().then((ok) => {
      setIsAuthenticated(ok)
      setLoading(false)
    })
  }, [])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <span className="text-foreground">Cargando…</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <LoginForm onSuccess={() => setIsAuthenticated(true)} />
  }

  return (
    <Dashboard
      userEmail="user@genbi.com"
      onLogout={() => {
        clearToken()
        setIsAuthenticated(false)
      }}
    />
  )
}

export default App
