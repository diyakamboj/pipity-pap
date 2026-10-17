"use client"

import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"
import { useNavigation } from "@/lib/navigation"
import { useEffect } from "react"

function RouteInitializer() {
  const nav = useNavigation()
  useEffect(() => {
    nav.setView("work")
  }, [])
  return <AppShell />
}

export default function WorkRoute() {
  return (
    <AppProviders>
      <RouteInitializer />
    </AppProviders>
  )
}
