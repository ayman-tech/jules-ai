"use client"

import {
  createUserWithEmailAndPassword,
  onIdTokenChanged,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  updateProfile,
  type User as FirebaseUser,
} from "firebase/auth"
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { AUTH_MODE, julesApi, setAuthTokenProvider } from "@/lib/api"
import { firebaseAuth } from "@/lib/firebase"
import type { AuthBootstrap } from "@/lib/types"

interface AuthContextValue {
  mode: "development" | "firebase"
  loading: boolean
  firebaseUser: FirebaseUser | null
  bootstrap: AuthBootstrap | null
  error: string | null
  refreshBootstrap: (displayName?: string) => Promise<AuthBootstrap | null>
  signIn: (email: string, password: string) => Promise<void>
  signUp: (displayName: string, email: string, password: string, continuePath?: string) => Promise<void>
  signOut: () => Promise<void>
  sendVerification: (continuePath?: string) => Promise<void>
  refreshVerification: () => Promise<boolean>
  resetPassword: (email: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function messageFor(error: unknown) {
  const message = error instanceof Error ? error.message : "Authentication could not be completed."
  return message
    .replace("Firebase: Error (auth/", "")
    .replace(").", "")
    .replaceAll("-", " ")
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const mode = AUTH_MODE === "firebase" ? "firebase" : "development"
  const [loading, setLoading] = useState(true)
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null)
  const [bootstrap, setBootstrap] = useState<AuthBootstrap | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshBootstrap = useCallback(async (displayName?: string) => {
    try {
      const next = await julesApi.bootstrap(displayName)
      setBootstrap(next)
      setError(null)
      return next
    } catch (cause) {
      setBootstrap(null)
      setError(messageFor(cause))
      return null
    }
  }, [])

  useEffect(() => {
    if (mode === "development") {
      setAuthTokenProvider(null)
      queueMicrotask(() => void refreshBootstrap().finally(() => setLoading(false)))
      return
    }
    let unsubscribe: () => void = () => {}
    try {
      const auth = firebaseAuth()
      setAuthTokenProvider(async () => auth.currentUser?.getIdToken() ?? null)
      unsubscribe = onIdTokenChanged(auth, async (user) => {
        setFirebaseUser(user)
        if (user) await refreshBootstrap()
        else setBootstrap(null)
        setLoading(false)
      })
    } catch (cause) {
      queueMicrotask(() => {
        setError(messageFor(cause))
        setLoading(false)
      })
    }
    return () => {
      unsubscribe()
      setAuthTokenProvider(null)
    }
  }, [mode, refreshBootstrap])

  useEffect(() => {
    const refreshMemberships = () => void refreshBootstrap()
    window.addEventListener("jules:membership-invalid", refreshMemberships)
    return () => window.removeEventListener("jules:membership-invalid", refreshMemberships)
  }, [refreshBootstrap])

  const value = useMemo<AuthContextValue>(() => ({
    mode,
    loading,
    firebaseUser,
    bootstrap,
    error,
    refreshBootstrap,
    async signIn(email, password) {
      setError(null)
      try {
        await signInWithEmailAndPassword(firebaseAuth(), email.trim(), password)
      } catch (cause) {
        const message = messageFor(cause)
        setError(message)
        throw new Error(message)
      }
    },
    async signUp(displayName, email, password, continuePath) {
      setError(null)
      try {
        const credential = await createUserWithEmailAndPassword(firebaseAuth(), email.trim(), password)
        await updateProfile(credential.user, { displayName: displayName.trim() })
        await credential.user.getIdToken(true)
        await refreshBootstrap(displayName)
        const url = new URL("/verify-email", window.location.origin)
        if (continuePath) url.searchParams.set("next", continuePath)
        await sendEmailVerification(credential.user, { url: url.toString() })
      } catch (cause) {
        const message = messageFor(cause)
        setError(message)
        throw new Error(message)
      }
    },
    async signOut() {
      setBootstrap(null)
      if (mode === "firebase") await firebaseSignOut(firebaseAuth())
    },
    async sendVerification(continuePath) {
      const user = firebaseAuth().currentUser
      if (!user) throw new Error("Sign in before requesting a verification email.")
      const url = new URL("/verify-email", window.location.origin)
      if (continuePath) url.searchParams.set("next", continuePath)
      await sendEmailVerification(user, { url: url.toString() })
    },
    async refreshVerification() {
      const user = firebaseAuth().currentUser
      if (!user) return false
      await reload(user)
      await user.getIdToken(true)
      setFirebaseUser(firebaseAuth().currentUser)
      await refreshBootstrap()
      return Boolean(firebaseAuth().currentUser?.emailVerified)
    },
    async resetPassword(email) {
      await sendPasswordResetEmail(firebaseAuth(), email.trim())
    },
  }), [bootstrap, error, firebaseUser, loading, mode, refreshBootstrap])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside AuthProvider")
  return value
}
