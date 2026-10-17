"use client"

import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"
import { useNavigation } from "@/lib/navigation"
import { useParams } from "next/navigation"
import { useEffect } from "react"

function RouteInitializer() {
  const nav = useNavigation()
  const params = useParams<{ workId: string }>()
  useEffect(() => {
    if (params?.workId) {
      nav.navigateToWorkDetail(params.workId)
    } else {
      nav.setView("work")
    }
  }, [params?.workId])
  return <AppShell />
}

export default function WorkDetailRoute() {
  return (
    <AppProviders>
      <RouteInitializer />
    </AppProviders>
  )
}
