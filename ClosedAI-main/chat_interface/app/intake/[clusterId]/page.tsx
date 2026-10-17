"use client"

import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"
import { useNavigation } from "@/lib/navigation"
import { useParams } from "next/navigation"
import { useEffect } from "react"

function RouteInitializer() {
  const nav = useNavigation()
  const params = useParams<{ clusterId: string }>()
  useEffect(() => {
    if (params?.clusterId) {
      nav.navigateToClusterDetail(params.clusterId)
    } else {
      nav.setView("intake")
    }
  }, [params?.clusterId])
  return <AppShell />
}

export default function IntakeClusterRoute() {
  return (
    <AppProviders>
      <RouteInitializer />
    </AppProviders>
  )
}
