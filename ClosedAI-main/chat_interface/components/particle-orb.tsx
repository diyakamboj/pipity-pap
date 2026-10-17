"use client"

import { useRef, useMemo } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import type * as THREE from "three"

function DottedSphere({ radius = 1.2, dotCount = 800, dotSize = 0.035 }) {
  const groupRef = useRef<THREE.Group>(null)

  const dots = useMemo(() => {
    const positions: [number, number, number][] = []
    const phi = Math.PI * (3 - Math.sqrt(5)) // golden angle for even distribution

    for (let i = 0; i < dotCount; i++) {
      const y = 1 - (i / (dotCount - 1)) * 2
      const radiusAtY = Math.sqrt(1 - y * y)
      const theta = phi * i

      const x = Math.cos(theta) * radiusAtY * radius
      const z = Math.sin(theta) * radiusAtY * radius
      positions.push([x, y * radius, z])
    }
    return positions
  }, [radius, dotCount])

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.08
      groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.05) * 0.1
    }
  })

  return (
    <group ref={groupRef}>
      {dots.map((pos, i) => (
        <mesh key={i} position={pos}>
          <sphereGeometry args={[dotSize, 8, 8]} />
          <meshStandardMaterial
            color="#ffffff"
            emissive="#ffffff"
            emissiveIntensity={0.8}
            metalness={0.9}
            roughness={0.1}
          />
        </mesh>
      ))}
    </group>
  )
}

function GlowingCore() {
  const meshRef = useRef<THREE.Mesh>(null)

  useFrame((state) => {
    if (meshRef.current) {
      const scale = 1 + Math.sin(state.clock.elapsedTime * 1.5) * 0.02
      meshRef.current.scale.set(scale, scale, scale)
    }
  })

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.15, 32, 32]} />
      <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={2} metalness={0.5} roughness={0.1} />
    </mesh>
  )
}

function Scene() {
  return (
    <>
      <ambientLight intensity={0.6} />
      <pointLight position={[5, 5, 5]} intensity={2} color="#ffffff" />
      <pointLight position={[-5, -5, -5]} intensity={1} color="#cccccc" />
      <pointLight position={[0, 0, 5]} intensity={1.5} color="#ffffff" />

      <GlowingCore />
      <DottedSphere radius={1.2} dotCount={800} dotSize={0.035} />
    </>
  )
}

export function ParticleOrb() {
  return (
    <div className="relative h-48 w-48">
      {/* Outer glow effect */}
      <div className="absolute inset-[-30%] rounded-full bg-gradient-radial from-white/20 via-white/5 to-transparent blur-3xl" />
      <Canvas
        camera={{ position: [0, 0, 4], fov: 45 }}
        style={{ background: "transparent" }}
        gl={{ alpha: true, antialias: true }}
      >
        <Scene />
      </Canvas>
    </div>
  )
}
