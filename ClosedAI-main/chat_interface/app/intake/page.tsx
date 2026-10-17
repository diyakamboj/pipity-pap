"use client"

import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"
import { useNavigation } from "@/lib/navigation"
import { useEffect } from "react"

function RouteInitializer({ view }: { view: "intake" | "work" | "automations" | "systems" }) {
  const nav = useNavigation()
  useEffect(() => {
    nav.setView(view)
  }, [view])
  return <AppShell />
}

export default function IntakeRoute() {
  return (
    <AppProviders>
      <RouteInitializer view="intake" />
    </AppProviders>
  )
}
