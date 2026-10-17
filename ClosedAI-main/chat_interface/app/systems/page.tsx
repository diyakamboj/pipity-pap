"use client"

import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"
import { useNavigation } from "@/lib/navigation"
import { useEffect } from "react"

function RouteInitializer() {
  const nav = useNavigation()
  useEffect(() => {
    nav.setView("systems")
  }, [])
  return <AppShell />
}

export default function SystemsRoute() {
  return (
    <AppProviders>
      <RouteInitializer />
    </AppProviders>
  )
}
