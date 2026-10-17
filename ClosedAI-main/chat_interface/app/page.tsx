import { AppShell } from "@/components/app-shell"
import { AppProviders } from "@/components/providers"

export default function Home() {
  return (
    <AppProviders>
      <AppShell />
    </AppProviders>
  )
}
