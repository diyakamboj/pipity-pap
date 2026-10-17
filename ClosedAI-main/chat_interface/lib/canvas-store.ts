"use client"

import { create } from 'zustand'

interface CanvasState {
  open: boolean
  serverBlockCount: number
  setOpen: (open: boolean) => void
  toggle: () => void
  setServerBlockCount: (count: number) => void
}

export const useCanvas = create<CanvasState>((set) => ({
  open: false,
  serverBlockCount: 0,
  setOpen: (open) => set({ open }),
  toggle: () => set((state) => ({ open: !state.open })),
  setServerBlockCount: (serverBlockCount) => set({ serverBlockCount }),
}))
