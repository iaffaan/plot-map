import React, { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Html } from '@react-three/drei'
import { Maximize2, Minimize2, Eye, EyeOff } from 'lucide-react'

// Beautiful, curated modern architectural color palettes
const roomColors = {
  "Entrance": "#f97316",        // Warm Terracotta / Coral
  "Entrance Lobby": "#f97316",  // Warm Terracotta
  "Living Room": "#6366f1",     // Modern Indigo / Slate
  "Living": "#6366f1",          // Modern Indigo
  "Kitchen": "#10b981",         // Fresh Sage / Emerald
  "Bedroom": "#3b82f6",         // Calm Sky Blue
  "Master Bedroom": "#2563eb",  // Royal Mist Blue
  "Bedroom 2": "#38bdf8",       // Bright Azure
  "Bedroom 3": "#0284c7",       // Cerulean Blue
  "Bathroom": "#f59e0b",        // Warm Amber / Travertine
  "Bathroom 1": "#f59e0b",
  "Bathroom 2": "#d97706",
  "Corridor": "#14b8a6",        // Soft Teal
  "OTS": "#0ea5e9",             // Sky Blue (open shafts)
  "Staircase": "#8b5cf6",       // Architectural Violet
  "Balcony": "#06b6d4",         // Cyan
  "Dining Room": "#ec4899",     // Soft Rose
  "Pooja": "#eab308",           // Sacred Gold
}

const roomFloorPastels = {
  "Entrance": "#fed7aa",        // Warm Travertine Coral Pastel
  "Entrance Lobby": "#fed7aa",  // Warm Travertine Coral Pastel
  "Living Room": "#fed7aa",     // Warm Linen / Light Amber Pastel
  "Living": "#fed7aa",
  "Kitchen": "#bbf7d0",         // Fresh Sage Mint Pastel
  "Bedroom": "#bae6fd",         // Serene Ocean Sky Pastel
  "Master Bedroom": "#93c5fd",  // Royal Mist Pastel
  "Bedroom 2": "#bae6fd",
  "Bedroom 3": "#bae6fd",
  "Bathroom": "#fef08a",        // Warm Travertine Gold Pastel
  "Bathroom 1": "#fef08a",
  "Bathroom 2": "#fef08a",
  "Corridor": "#e2e8f0",        // Light Architectural Stone
  "OTS": "#0f172a",             // Open void
  "Staircase": "#ddd6fe",       // Soft Lavender Slate
  "Balcony": "#a5f3fc",         // Light Aqua
  "Dining Room": "#fbcfe8",     // Soft Rose Pastel
  "Pooja": "#fef08a",           // Warm Sacred Gold
}

// Helper to determine if an opening is hosted by a wall segment
function getOpeningsOnWall(wall, openings, tolerance = 0.5) {
  const [x1, y1] = wall.start
  const [x2, y2] = wall.end
  const dx = x2 - x1
  const dy = y2 - y1
  const wallLength = Math.sqrt(dx * dx + dy * dy)
  if (wallLength < 0.1) return []

  const ux = dx / wallLength
  const uy = dy / wallLength

  const hosted = []
  openings.forEach(op => {
    const [ox, oy] = op.position

    // Project opening point onto wall line
    const tx = ox - x1
    const ty = oy - y1
    const projDist = tx * ux + ty * uy

    if (projDist >= -tolerance && projDist <= wallLength + tolerance) {
      // Calculate perpendicular distance to wall
      const perpDist = Math.abs(tx * (-uy) + ty * ux)
      if (perpDist <= tolerance) {
        hosted.push({
          ...op,
          distAlongWall: Math.max(0, Math.min(projDist, wallLength))
        })
      }
    }
  })

  // Sort openings along the wall from start to end
  return hosted.sort((a, b) => a.distAlongWall - b.distAlongWall)
}

// 3D Door Model (Supports Interior Doors & Grand Exterior Main Entrance Door)
function ProceduralDoor3D({ position, direction, width, height = 7.0, type = "interior" }) {
  const isMainEntrance = type === "main_entrance" || type === "entrance"
  const angle = direction === "vertical" ? -Math.PI / 2 : 0
  const actualWidth = isMainEntrance ? Math.max(3.5, width) : width
  const actualHeight = isMainEntrance ? 7.5 : height
  const frameColor = isMainEntrance ? "#1c120c" : "#4e3629"
  const leafColor = isMainEntrance ? "#502817" : "#a0522d"

  return (
    <group position={position} rotation={[0, angle, 0]}>
      {/* Wooden / Metal Door Frame */}
      {/* Left Frame */}
      <mesh position={[-actualWidth / 2 + 0.06, actualHeight / 2, 0]}>
        <boxGeometry args={[0.12, actualHeight, isMainEntrance ? 0.22 : 0.15]} />
        <meshStandardMaterial color={frameColor} roughness={0.6} />
      </mesh>
      {/* Right Frame */}
      <mesh position={[actualWidth / 2 - 0.06, actualHeight / 2, 0]}>
        <boxGeometry args={[0.12, actualHeight, isMainEntrance ? 0.22 : 0.15]} />
        <meshStandardMaterial color={frameColor} roughness={0.6} />
      </mesh>
      {/* Top Header Frame */}
      <mesh position={[0, actualHeight - 0.06, 0]}>
        <boxGeometry args={[actualWidth, 0.12, isMainEntrance ? 0.22 : 0.15]} />
        <meshStandardMaterial color={frameColor} roughness={0.6} />
      </mesh>

      {/* Main Entrance Welcome Porch Step / Threshold */}
      {isMainEntrance && (
        <mesh position={[0, 0.04, 0.3]}>
          <boxGeometry args={[actualWidth + 0.8, 0.08, 0.6]} />
          <meshStandardMaterial color="#475569" roughness={0.8} />
        </mesh>
      )}

      {/* Door Leaf (Hinged at left side, rotated open) */}
      <group position={[-actualWidth / 2 + 0.12, 0, 0]} rotation={[0, isMainEntrance ? -Math.PI / 4 : -Math.PI / 5, 0]}>
        <mesh position={[(actualWidth - 0.24) / 2, actualHeight / 2, 0]}>
          <boxGeometry args={[actualWidth - 0.24, actualHeight - 0.16, isMainEntrance ? 0.08 : 0.05]} />
          <meshStandardMaterial color={leafColor} roughness={0.4} metalness={0.15} />
        </mesh>

        {/* Main Entrance Modern Architectural Inlay & Handle */}
        {isMainEntrance ? (
          <>
            {/* Frosted Glass Inlay Strip */}
            <mesh position={[(actualWidth - 0.24) / 2 - 0.35, actualHeight / 2, 0]}>
              <boxGeometry args={[0.15, actualHeight * 0.7, 0.09]} />
              <meshPhysicalMaterial color="#bae6fd" opacity={0.65} transparent roughness={0.1} transmission={0.7} />
            </mesh>
            {/* Modern Golden Brass Pull Bar Handle */}
            <mesh position={[actualWidth - 0.45, actualHeight / 2, 0.08]}>
              <cylinderGeometry args={[0.02, 0.02, 2.2, 12]} />
              <meshStandardMaterial color="#fbbf24" metalness={0.9} roughness={0.2} />
            </mesh>
          </>
        ) : (
          /* Interior Standard Brass Doorknob */
          <mesh position={[actualWidth - 0.38, actualHeight / 2, 0.05]}>
            <sphereGeometry args={[0.04, 8, 8]} />
            <meshStandardMaterial color="#ffd700" metalness={0.8} roughness={0.2} />
          </mesh>
        )}
      </group>
    </group>
  )
}

// 3D Window Model
function ProceduralWindow3D({ position, direction, width, height = 4.0, sillHeight = 3.0 }) {
  const angle = direction === "vertical" ? -Math.PI / 2 : 0

  return (
    <group position={[position[0], position[1] + sillHeight + height / 2, position[2]]} rotation={[0, angle, 0]}>
      {/* Aluminium Outer Frame */}
      <mesh>
        <boxGeometry args={[width, height, 0.16]} />
        <meshStandardMaterial color="#2d3748" metalness={0.6} roughness={0.3} wireframe />
      </mesh>
      {/* Solid Outer Frame Bounds */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[width, 0.08, 0.15]} />
        <meshStandardMaterial color="#2d3748" metalness={0.6} roughness={0.3} />
      </mesh>
      <mesh position={[-width / 2 + 0.04, 0, 0]}>
        <boxGeometry args={[0.08, height, 0.15]} />
        <meshStandardMaterial color="#2d3748" metalness={0.6} roughness={0.3} />
      </mesh>
      <mesh position={[width / 2 - 0.04, 0, 0]}>
        <boxGeometry args={[0.08, height, 0.15]} />
        <meshStandardMaterial color="#2d3748" metalness={0.6} roughness={0.3} />
      </mesh>

      {/* Glass Pane */}
      <mesh>
        <boxGeometry args={[width - 0.1, height - 0.1, 0.02]} />
        <meshPhysicalMaterial
          color="#a9efefff"
          transparent
          opacity={0.45}
          roughness={0.1}
          metalness={0.9}
          transmission={0.6}
          ior={1.5}
        />
      </mesh>
    </group>
  )
}

// Dog-legged staircase builder (U-shape concrete stairs with landing strictly enclosed inside the core)
function ProceduralStairs3D({ rect, floorHeight, baseZ }) {
  const { x, y, w, h } = rect

  // Design details
  const stepsPerFloor = 16
  const stepsPerFlight = stepsPerFloor / 2
  const stepHeight = floorHeight / stepsPerFloor
  const landingHeight = stepHeight * stepsPerFlight

  // Dimensions of stairs flights
  const flightWidth = w / 2 - 0.15
  const landingDepth = Math.min(3.5, h / 3)
  const flightDepth = h - landingDepth

  const stepsList = []

  // Flight 1: Ascends from Y=0 (front) towards landing (back) on the left half
  for (let i = 0; i < stepsPerFlight; i++) {
    const stepDepth = flightDepth / stepsPerFlight
    const stepY = baseZ + i * stepHeight + stepHeight / 2
    const stepPosZ = y + (i + 0.5) * stepDepth
    const stepPosX = x + flightWidth / 2 + 0.05

    stepsList.push(
      <mesh key={`f1-step-${i}`} position={[stepPosX, stepY, stepPosZ]}>
        <boxGeometry args={[flightWidth, stepHeight, stepDepth]} />
        <meshStandardMaterial color="#cbd5e1" roughness={0.6} />
      </mesh>
    )
  }

  // Mid-landing Platform (Concrete slab at back of core)
  const landingPosZ = y + h - landingDepth / 2
  const landingPosX = x + w / 2
  stepsList.push(
    <mesh key="mid-landing" position={[landingPosX, baseZ + landingHeight - 0.08, landingPosZ]}>
      <boxGeometry args={[w - 0.1, 0.16, landingDepth - 0.05]} />
      <meshStandardMaterial color="#94a3b8" roughness={0.6} />
    </mesh>
  )

  // Flight 2: Ascends from landing (back) to next floor (front) on the right half
  for (let i = 0; i < stepsPerFlight; i++) {
    const stepDepth = flightDepth / stepsPerFlight
    const stepY = baseZ + landingHeight + i * stepHeight + stepHeight / 2
    const stepPosZ = y + h - landingDepth - (i + 0.5) * stepDepth
    const stepPosX = x + w - flightWidth / 2 - 0.05

    stepsList.push(
      <mesh key={`f2-step-${i}`} position={[stepPosX, stepY, stepPosZ]}>
        <boxGeometry args={[flightWidth, stepHeight, stepDepth]} />
        <meshStandardMaterial color="#cbd5e1" roughness={0.6} />
      </mesh>
    )
  }

  // Center divider Handrail / Balustrade
  const railPosX = x + w / 2
  const railPosZ = y + flightDepth / 2
  stepsList.push(
    <mesh key="stair-divider-rail" position={[railPosX, baseZ + floorHeight / 2, railPosZ]}>
      <boxGeometry args={[0.04, floorHeight, flightDepth]} />
      <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.2} />
    </mesh>
  )

  return <group>{stepsList}</group>
}

// Procedural Wall with Boolean Subtractions for Doors and Windows
function ProceduralWall3D({ wall, openings, floorHeight, baseZ, plotWidth, plotDepth }) {
  const [x1, y1] = wall.start
  const [x2, y2] = wall.end

  const dx = x2 - x1
  const dy = y2 - y1
  const wallLength = Math.sqrt(dx * dx + dy * dy)
  if (wallLength < 0.1) return null

  const thickness = wall.type === "exterior" ? 0.75 : 0.4
  const ux = dx / wallLength
  const uy = dy / wallLength
  const wallAngle = Math.atan2(dy, dx)

  const hostedOpenings = getOpeningsOnWall(wall, openings)

  if (hostedOpenings.length === 0) {
    const midX = (x1 + x2) / 2 - plotWidth / 2
    const midZ = (y1 + y2) / 2 - plotDepth / 2
    const midY = baseZ + floorHeight / 2

    return (
      <group position={[midX, midY, midZ]} rotation={[0, -wallAngle, 0]}>
        <mesh>
          <boxGeometry args={[wallLength, floorHeight, thickness]} />
          <meshStandardMaterial
            color={wall.type === "exterior" ? "#f8fafc" : "#f1f5f9"}
            roughness={0.6}
          />
        </mesh>
      </group>
    )
  }

  const panels = []
  let currentDist = 0

  hostedOpenings.forEach((op, idx) => {
    const opWidth = op.width || 3.0
    const opStart = Math.max(0, op.distAlongWall - opWidth / 2)
    const opEnd = Math.min(wallLength, op.distAlongWall + opWidth / 2)

    if (opStart > currentDist + 0.05) {
      const segLen = opStart - currentDist
      const segMidDist = currentDist + segLen / 2
      const segWorldX = x1 + ux * segMidDist - plotWidth / 2
      const segWorldZ = y1 + uy * segMidDist - plotDepth / 2

      panels.push(
        <mesh
          key={`wall-${wall.id}-seg-${idx}`}
          position={[segWorldX, baseZ + floorHeight / 2, segWorldZ]}
          rotation={[0, -wallAngle, 0]}
        >
          <boxGeometry args={[segLen, floorHeight, thickness]} />
          <meshStandardMaterial color={wall.type === "exterior" ? "#f8fafc" : "#f1f5f9"} roughness={0.6} />
        </mesh>
      )
    }

    const holeLen = opEnd - opStart
    const holeMidDist = opStart + holeLen / 2
    const holeWorldX = x1 + ux * holeMidDist - plotWidth / 2
    const holeWorldZ = y1 + uy * holeMidDist - plotDepth / 2

    const isDoor = op.id.startsWith("door")
    const isWindow = op.id.startsWith("window")

    if (isDoor) {
      const doorHeight = 7.0
      const lintelHeight = floorHeight - doorHeight
      if (lintelHeight > 0.1) {
        panels.push(
          <mesh
            key={`wall-${wall.id}-lintel-${idx}`}
            position={[holeWorldX, baseZ + doorHeight + lintelHeight / 2, holeWorldZ]}
            rotation={[0, -wallAngle, 0]}
          >
            <boxGeometry args={[holeLen, lintelHeight, thickness]} />
            <meshStandardMaterial color={wall.type === "exterior" ? "#f8fafc" : "#f1f5f9"} roughness={0.6} />
          </mesh>
        )
      }
    } else if (isWindow) {
      const sillHeight = 3.0
      const winHeight = 4.0
      const lintelHeight = floorHeight - (sillHeight + winHeight)

      if (sillHeight > 0.1) {
        panels.push(
          <mesh
            key={`wall-${wall.id}-sill-${idx}`}
            position={[holeWorldX, baseZ + sillHeight / 2, holeWorldZ]}
            rotation={[0, -wallAngle, 0]}
          >
            <boxGeometry args={[holeLen, sillHeight, thickness]} />
            <meshStandardMaterial color={wall.type === "exterior" ? "#f8fafc" : "#f1f5f9"} roughness={0.6} />
          </mesh>
        )
      }

      if (lintelHeight > 0.1) {
        panels.push(
          <mesh
            key={`wall-${wall.id}-win-lintel-${idx}`}
            position={[holeWorldX, baseZ + sillHeight + winHeight + lintelHeight / 2, holeWorldZ]}
            rotation={[0, -wallAngle, 0]}
          >
            <boxGeometry args={[holeLen, lintelHeight, thickness]} />
            <meshStandardMaterial color={wall.type === "exterior" ? "#f8fafc" : "#f1f5f9"} roughness={0.6} />
          </mesh>
        )
      }
    }

    currentDist = opEnd
  })

  if (currentDist < wallLength - 0.05) {
    const segLen = wallLength - currentDist
    const segMidDist = currentDist + segLen / 2
    const segWorldX = x1 + ux * segMidDist - plotWidth / 2
    const segWorldZ = y1 + uy * segMidDist - plotDepth / 2

    panels.push(
      <mesh
        key={`wall-${wall.id}-seg-end`}
        position={[segWorldX, baseZ + floorHeight / 2, segWorldZ]}
        rotation={[0, -wallAngle, 0]}
      >
        <boxGeometry args={[segLen, floorHeight, thickness]} />
        <meshStandardMaterial color={wall.type === "exterior" ? "#f8fafc" : "#f1f5f9"} roughness={0.6} />
      </mesh>
    )
  }

  return <group>{panels}</group>
}

// Architectural Roof Slab, Terrace Parapet & Staircase Mumty
function ProceduralRoof3D({ buildingData, floorHeight, totalFloors, showRoof }) {
  if (!showRoof || !buildingData) return null

  const { width: plotWidth, depth: plotDepth, floors_data, boundaries } = buildingData
  const topZ = totalFloors * floorHeight

  // Find topmost occupied footprint
  const topFloorData = floors_data ? floors_data[String(totalFloors)] : null
  const layout = topFloorData?.layout || {}
  const rooms = Object.values(layout)

  if (rooms.length === 0) return null

  const minX = Math.min(...rooms.map(r => r.x))
  const maxX = Math.max(...rooms.map(r => r.x + r.width))
  const minY = Math.min(...rooms.map(r => r.y))
  const maxY = Math.max(...rooms.map(r => r.y + r.height))

  const roofW = maxX - minX
  const roofH = maxY - minY
  const roofCenterX = (minX + maxX) / 2 - plotWidth / 2
  const roofCenterZ = (minY + maxY) / 2 - plotDepth / 2

  // Stair core mumty headroom
  const stairCore = boundaries?.stair_core
  let stairMumty = null
  if (stairCore && stairCore.length >= 4) {
    const xs = stairCore.map(c => c[0])
    const ys = stairCore.map(c => c[1])
    const sMinX = Math.min(...xs)
    const sMaxX = Math.max(...xs)
    const sMinY = Math.min(...ys)
    const sMaxY = Math.max(...ys)
    stairMumty = {
      x: (sMinX + sMaxX) / 2 - plotWidth / 2,
      z: (sMinY + sMaxY) / 2 - plotDepth / 2,
      w: sMaxX - sMinX,
      h: sMaxY - sMinY,
      height: 7.5
    }
  }

  return (
    <group position={[0, topZ, 0]}>
      {/* 1. Main Roof Terrace Slab (Cast-in-place concrete) */}
      <mesh position={[roofCenterX, 0.15, roofCenterZ]}>
        <boxGeometry args={[roofW + 0.6, 0.3, roofH + 0.6]} />
        <meshStandardMaterial color="#cbd5e1" roughness={0.5} metalness={0.1} />
      </mesh>

      {/* Terrace Floor Waterproofing Tiling */}
      <mesh position={[roofCenterX, 0.32, roofCenterZ]}>
        <boxGeometry args={[roofW + 0.4, 0.05, roofH + 0.4]} />
        <meshStandardMaterial color="#94a3b8" roughness={0.4} />
      </mesh>

      {/* 2. Perimeter Parapet Wall (3.0ft high) with Coping */}
      {/* South Parapet */}
      <mesh position={[roofCenterX, 1.5 + 0.3, roofCenterZ - roofH / 2]}>
        <boxGeometry args={[roofW + 0.6, 3.0, 0.3]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.6} />
      </mesh>
      {/* North Parapet */}
      <mesh position={[roofCenterX, 1.5 + 0.3, roofCenterZ + roofH / 2]}>
        <boxGeometry args={[roofW + 0.6, 3.0, 0.3]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.6} />
      </mesh>
      {/* West Parapet */}
      <mesh position={[roofCenterX - roofW / 2, 1.5 + 0.3, roofCenterZ]}>
        <boxGeometry args={[0.3, 3.0, roofH + 0.6]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.6} />
      </mesh>
      {/* East Parapet */}
      <mesh position={[roofCenterX + roofW / 2, 1.5 + 0.3, roofCenterZ]}>
        <boxGeometry args={[0.3, 3.0, roofH + 0.6]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.6} />
      </mesh>

      {/* Modern Parapet Coping Slab (Dark Slate Coping) */}
      <mesh position={[roofCenterX, 3.05 + 0.3, roofCenterZ]}>
        <boxGeometry args={[roofW + 0.8, 0.1, roofH + 0.8]} />
        <meshStandardMaterial color="#1e293b" roughness={0.4} />
      </mesh>

      {/* 3. Staircase Headroom (Mumty Room) on Terrace */}
      {stairMumty && (
        <group position={[stairMumty.x, 0.3, stairMumty.z]}>
          <mesh position={[0, stairMumty.height / 2, 0]}>
            <boxGeometry args={[stairMumty.w, stairMumty.height, stairMumty.h]} />
            <meshStandardMaterial color="#f8fafc" roughness={0.7} />
          </mesh>
          {/* Mumty Roof Cap */}
          <mesh position={[0, stairMumty.height + 0.15, 0]}>
            <boxGeometry args={[stairMumty.w + 0.6, 0.3, stairMumty.h + 0.6]} />
            <meshStandardMaterial color="#334155" roughness={0.5} />
          </mesh>
          {/* Mumty Terrace Access Door */}
          <mesh position={[0, 3.5, stairMumty.h / 2 + 0.05]}>
            <boxGeometry args={[2.8, 6.8, 0.1]} />
            <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
          </mesh>
        </group>
      )}
    </group>
  )
}

function BuildingModel({ buildingData, activeFloorFilter, showRoof }) {
  if (!buildingData) return null

  const { width: plotWidth, depth: plotDepth, floors, boundaries } = buildingData
  const floorHeight = 10.0

  // Bounding boxes calculations
  let stairCoreRect = null
  if (boundaries?.stair_core && boundaries.stair_core.length > 0) {
    const xs = boundaries.stair_core.map(c => c[0])
    const ys = boundaries.stair_core.map(c => c[1])
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)

    stairCoreRect = {
      x: minX,
      y: minY,
      w: maxX - minX,
      h: maxY - minY
    }
  }

  return (
    <group>
      {/* 1. Ground Plot Concrete Slab */}
      <mesh position={[0, -0.1, 0]}>
        <boxGeometry args={[plotWidth + 4, 0.2, plotDepth + 4]} />
        <meshStandardMaterial color="#0f172a" roughness={0.9} />
      </mesh>

      {/* Plot Boundary Border */}
      <mesh position={[0, -0.05, 0]}>
        <boxGeometry args={[plotWidth + 4.1, 0.12, plotDepth + 4.1]} />
        <meshBasicMaterial color="#334155" wireframe />
      </mesh>

      {/* 2. Floors Iterative Renders */}
      {buildingData.floors_data && Object.entries(buildingData.floors_data).map(([floorIdxStr, floorData]) => {
        const fLevel = parseInt(floorIdxStr)
        const fIdx = fLevel - 1
        const baseZ = fIdx * floorHeight

        // Filter out if not in the active view selection
        if (activeFloorFilter !== 'all' && activeFloorFilter !== fLevel) return null

        const geometry = floorData.geometry || {}
        const walls = geometry.walls || []
        const doors = geometry.doors || []
        const windows = geometry.windows || []
        const layout = floorData.layout || {}

        return (
          <group key={`floor-group-${fLevel}`}>
            {/* Base Structural Floor Slab */}
            <mesh position={[0, baseZ - 0.2, 0]}>
              <boxGeometry args={[plotWidth + 0.2, 0.4, plotDepth + 0.2]} />
              <meshStandardMaterial color="#1e293b" roughness={0.7} />
            </mesh>

            {/* Individual Room Finished Floor Tiles & Aesthetic Volume */}
            {Object.entries(layout).map(([roomName, room]) => {
              const rx = room.x + room.width / 2 - plotWidth / 2
              const rz = room.y + room.height / 2 - plotDepth / 2
              const ry = baseZ + floorHeight / 2
              const color = roomColors[room.type] || roomColors[roomName] || "#ffffff"
              const floorColor = roomFloorPastels[room.type] || roomFloorPastels[roomName] || "#f8fafc"
              const isOts = room.type === "OTS"

              if (isOts) return null // Shaft is open void space

              return (
                <group key={`volume-${roomName}`}>
                  {/* Elegant Pastel Floor Tile Finish */}
                  <mesh position={[rx, baseZ + 0.06, rz]}>
                    <boxGeometry args={[room.width - 0.15, 0.12, room.height - 0.15]} />
                    <meshStandardMaterial
                      color={floorColor}
                      roughness={0.4}
                      metalness={0.05}
                    />
                  </mesh>

                  {/* Subtle Baseboard Accent Border */}
                  <mesh position={[rx, baseZ + 0.12, rz]}>
                    <boxGeometry args={[room.width - 0.05, 0.18, room.height - 0.05]} />
                    <meshBasicMaterial color={color} wireframe opacity={0.4} transparent />
                  </mesh>

                  {/* Volumetric Tint (Soft architectural glow) */}
                  <mesh position={[rx, ry, rz]}>
                    <boxGeometry args={[room.width - 0.1, floorHeight - 0.1, room.height - 0.1]} />
                    <meshStandardMaterial
                      color={color}
                      transparent
                      opacity={0.05}
                      roughness={0.95}
                    />
                  </mesh>

                  {/* Floating Architectural Badge Label */}
                  <Html position={[rx, baseZ + floorHeight / 2 + 1, rz]} center distanceFactor={15}>
                    <div className="bg-[#0f172a]/95 border border-slate-700/80 p-2 rounded text-[10px] font-mono pointer-events-none select-none text-center shadow-2xl min-w-[75px] backdrop-blur-xs">
                      <span className="font-bold uppercase tracking-wider" style={{ color: color }}>{roomName}</span>
                      <div className="text-[8px] text-slate-400 mt-0.5">{room.width}′ × {room.height}′</div>
                    </div>
                  </Html>
                </group>
              )
            })}

            {/* 3D Constructive Walls */}
            {walls.map(w => (
              <ProceduralWall3D
                key={w.id}
                wall={w}
                openings={[...doors, ...windows]}
                floorHeight={floorHeight}
                baseZ={baseZ}
                plotWidth={plotWidth}
                plotDepth={plotDepth}
              />
            ))}

            {/* 3D Doors (Including Main Entrance Door) */}
            {doors.map(d => {
              const px = d.position[0] - plotWidth / 2
              const pz = d.position[1] - plotDepth / 2
              return (
                <ProceduralDoor3D
                  key={d.id}
                  position={[px, baseZ, pz]}
                  direction={d.direction}
                  width={d.width}
                  type={d.type}
                />
              )
            })}

            {/* 3D Windows */}
            {windows.map(win => {
              const px = win.position[0] - plotWidth / 2
              const pz = win.position[1] - plotDepth / 2
              return (
                <ProceduralWindow3D
                  key={win.id}
                  position={[px, baseZ, pz]}
                  direction={win.direction}
                  width={win.width}
                />
              )
            })}

            {/* 3D Stairs Core Steps */}
            {stairCoreRect && (
              <ProceduralStairs3D
                rect={{
                  x: stairCoreRect.x - plotWidth / 2,
                  y: stairCoreRect.y - plotDepth / 2,
                  w: stairCoreRect.w,
                  h: stairCoreRect.h
                }}
                floorHeight={floorHeight}
                baseZ={baseZ}
              />
            )}
          </group>
        )
      })}

      {/* 3. Columns pillars rising all floors */}
      {stairCoreRect && (
        <>
          {[
            [-plotWidth / 2 + 0.2, -plotDepth / 2 + 0.2],
            [plotWidth / 2 - 0.2, -plotDepth / 2 + 0.2],
            [-plotWidth / 2 + 0.2, plotDepth / 2 - 0.2],
            [plotWidth / 2 - 0.2, plotDepth / 2 - 0.2],
          ].map(([colX, colZ], idx) => (
            <mesh key={`pillar-${idx}`} position={[colX, (floors * floorHeight) / 2, colZ]}>
              <boxGeometry args={[0.5, floors * floorHeight, 0.5]} />
              <meshStandardMaterial color="#475569" roughness={0.7} />
            </mesh>
          ))}
        </>
      )}

      {/* 4. Architectural Roof & Parapet Terrace */}
      <ProceduralRoof3D
        buildingData={buildingData}
        floorHeight={floorHeight}
        totalFloors={floors || 1}
        showRoof={showRoof && activeFloorFilter === 'all'}
      />
    </group>
  )
}

function MockupWireframeMesh() {
  return (
    <group position={[0, 6, 0]}>
      <mesh>
        <boxGeometry args={[10, 14, 10]} />
        <meshBasicMaterial color="#252527ff" wireframe />
      </mesh>
    </group>
  )
}

export function BuildingViewer3D({ buildingData, isLoading, isFullscreen, onToggleFullscreen }) {
  const [activeFloorFilter, setActiveFloorFilter] = useState('all')
  const [showRoof, setShowRoof] = useState(false)

  return (
    <div className="relative w-full h-full bg-[#0a0a0f] flex flex-col">
      {/* Floors selection controls and Roof Toggle */}
      {buildingData && (
        <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
          <div className="flex gap-1 bg-[#0d0e15]/90 border border-border p-1 rounded-sm shadow-md font-mono text-[10px]">
            <button
              onClick={() => setActiveFloorFilter('all')}
              className={`px-3 py-1.5 uppercase transition-colors cursor-pointer rounded-xs ${activeFloorFilter === 'all' ? 'bg-primary/20 text-primary font-bold' : 'text-muted-foreground hover:text-foreground'}`}
            >
              Show All Floors
            </button>
            {Array.from({ length: buildingData.floors || 1 }).map((_, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setActiveFloorFilter(idx + 1)
                  setShowRoof(false)
                }}
                className={`px-3 py-1.5 uppercase transition-colors cursor-pointer rounded-xs ${activeFloorFilter === idx + 1 ? 'bg-primary/20 text-primary font-bold' : 'text-muted-foreground hover:text-foreground'}`}
              >
                Floor {idx + 1}
              </button>
            ))}
          </div>

          {/* Roof Toggle Button (Visible in 'Show All Floors' mode) */}
          {activeFloorFilter === 'all' && (
            <button
              onClick={() => setShowRoof(!showRoof)}
              className={`flex items-center gap-1.5 px-3 py-1.5 uppercase font-mono text-[10px] transition-colors cursor-pointer rounded-xs border shadow-md ${showRoof ? 'bg-amber-500/20 text-amber-400 border-amber-500/40 font-bold' : 'bg-[#0d0e15]/90 border-border text-muted-foreground hover:text-foreground'}`}
              title="Toggle architectural roof slab and terrace parapet"
            >
              {showRoof ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
              {showRoof ? 'Roof: Shown' : 'Roof: Hidden'}
            </button>
          )}
        </div>
      )}

      {/* Fullscreen Overlay Button for 3D View */}
      {onToggleFullscreen && (
        <button
          onClick={onToggleFullscreen}
          className="absolute top-4 right-4 z-10 bg-[#0d0e15]/80 hover:bg-card text-muted-foreground hover:text-foreground border border-border p-2 rounded-sm shadow-md transition-colors cursor-pointer flex items-center justify-center"
          title={isFullscreen ? "Exit Fullscreen (Esc)" : "Fullscreen Mode"}
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      )}

      {/* ThreeJS R3F Canvas */}
      <div className="flex-1 w-full h-full relative">
        <Canvas
          camera={{
            position: [40, 35, 40],
            fov: 40,
            near: 0.1,
            far: 1000,
          }}
          dpr={[1, 2]}
        >
          <color attach="background" args={['#07070a']} />

          {/* Lighting systems with enhanced warmth and ambient reflection */}
          <ambientLight intensity={0.7} color="#ffffff" />
          <directionalLight position={[35, 50, 25]} intensity={1.3} color="#fffbeb" castShadow />
          <directionalLight position={[-25, 25, -30]} intensity={0.6} color="#818cf8" />
          <pointLight position={[0, 18, 0]} intensity={0.4} color="#38bdf8" />

          {/* Grid base */}
          <Grid
            args={[100, 100]}
            cellSize={1}
            cellColor="#555555"
            sectionSize={5}
            sectionColor="#777777"
            fadeStrength={0.7}
            fadeDistance={75}
            infiniteGrid
          />

          {/* Procedural 3D model generator or Mockup Wireframe Mesh */}
          {buildingData ? (
            <BuildingModel
              buildingData={buildingData}
              activeFloorFilter={activeFloorFilter}
              showRoof={showRoof}
            />
          ) : (
            <MockupWireframeMesh />
          )}

          {/* Orbit navigation controls */}
          <OrbitControls
            autoRotate={!buildingData}
            autoRotateSpeed={0.4}
            minDistance={10}
            maxDistance={150}
            enableDamping
            dampingFactor={0.05}
          />
        </Canvas>
      </div>

      {/* Overlay Status */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/75 backdrop-blur-sm z-35">
          <div className="flex flex-col items-center gap-4 bg-card border border-border p-6 rounded-md shadow-2xl">
            <div className="w-10 h-10 border-4 border-accent/20 border-t-accent rounded-full animate-spin" />
            <div className="text-center">
              <h4 className="text-sm font-semibold text-foreground uppercase tracking-wider font-mono">Building Geometry</h4>
              <p className="text-xs text-muted-foreground font-mono mt-1">Executing constructive extrusions and placing models...</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
