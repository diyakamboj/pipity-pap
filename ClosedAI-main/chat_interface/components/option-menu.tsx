"use client"

import type { ReactNode } from "react"
import { Check } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

interface OptionMenuProps {
  trigger: ReactNode
  label?: string
  options: string[]
  value: string
  onChange: (value: string) => void
  align?: "start" | "center" | "end"
  side?: "top" | "bottom"
}

export function OptionMenu({
  trigger,
  label,
  options,
  value,
  onChange,
  align = "start",
  side = "bottom",
}: OptionMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        side={side}
        className="min-w-[200px] border-white/10 bg-[#111111] text-neutral-200 duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
      >
        {label && <DropdownMenuLabel className="text-xs text-neutral-500">{label}</DropdownMenuLabel>}
        {label && <DropdownMenuSeparator className="bg-white/10" />}
        {options.map((option) => (
          <DropdownMenuItem
            key={option}
            onSelect={() => onChange(option)}
            className={cn(
              "flex items-center justify-between gap-2 text-[13px] focus:bg-white/[0.06] focus:text-white",
              value === option && "text-white",
            )}
          >
            {option}
            {value === option && <Check className="h-3.5 w-3.5" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
