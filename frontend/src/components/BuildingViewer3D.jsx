import React, { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Html } from '@react-three/drei'
import { Maximize2, Minimize2 } from 'lucide-react'

const roomColors = {
  "Entrance": "#a6adc8",       // Cool Slate
  "Living Room": "#b4befe",     // Soft Indigo
  "Kitchen": "#ffe082",         // Warm Gold
  "Bedroom": "#a6e3a1",         // Soft Leaf Green
  "Bathroom": "#f2cdcd",        // Soft Coral Pink
  "Corridor": "#94e2d5",        // Soft Teal
  "OTS": "#74c7ec",             // Sky Blue (open shafts)
  "Staircase": "#f38ba8",       // Soft Rose
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

// 3D Door Model
function ProceduralDoor3D({ position, direction, width, height = 7.0 }) {
  const angle = direction === "vertical" ? Math.PI / 2 : 0

  return (
    <group position={position} rotation={[0, angle, 0]}>
      {/* Wooden Door Frame */}
      {/* Left Frame */}
      <mesh position={[-width / 2 + 0.05, height / 2, 0]}>
        <boxGeometry args={[0.1, height, 0.15]} />
        <meshStandardMaterial color="#4e3629" roughness={0.7} />
      </mesh>
      {/* Right Frame */}
      <mesh position={[width / 2 - 0.05, height / 2, 0]}>
        <boxGeometry args={[0.1, height, 0.15]} />
        <meshStandardMaterial color="#4e3629" roughness={0.7} />
      </mesh>
      {/* Top Header Frame */}
      <mesh position={[0, height - 0.05, 0]}>
        <boxGeometry args={[width, 0.1, 0.15]} />
        <meshStandardMaterial color="#4e3629" roughness={0.7} />
      </mesh>

      {/* Door Leaf (Hinged at left side, rotated open 35 degrees) */}
      <group position={[-width / 2 + 0.1, 0, 0]} rotation={[0, -Math.PI / 5, 0]}>
        <mesh position={[(width - 0.2) / 2, height / 2, 0]}>
          <boxGeometry args={[width - 0.2, height - 0.15, 0.05]} />
          <meshStandardMaterial color="#a0522d" roughness={0.5} metalness={0.1} />
        </mesh>
        {/* Doorknob */}
        <mesh position={[width - 0.35, height / 2, 0.05]}>
          <sphereGeometry args={[0.04, 8, 8]} />
          <meshStandardMaterial color="#ffd700" metalness={0.8} roughness={0.2} />
        </mesh>
      </group>
    </group>
  )
}

// 3D Window Model
function ProceduralWindow3D({ position, direction, width, height = 4.0, sillHeight = 3.0 }) {
  const angle = direction === "vertical" ? Math.PI / 2 : 0

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

// Dog-legged staircase builder (U-shape concrete/wood stairs with landing)
function ProceduralStairs3D({ rect, floorHeight, baseZ }) {
  const { x, y, w, h } = rect

  // Design details
  const stepsPerFloor = 16
  const stepsPerFlight = stepsPerFloor / 2
  const stepHeight = floorHeight / stepsPerFloor
  const landingHeight = stepHeight * stepsPerFlight

  // Dimensions of stairs flights
  const flightWidth = w / 2 - 0.1
  const landingDepth = Math.min(3.5, h / 3)
  const flightDepth = h - landingDepth

  const stepsList = []

  // Flight 1: Rising from 0 to landingHeight along the left side
  for (let i = 0; i < stepsPerFlight; i++) {
    const stepDepthVal = flightDepth / stepsPerFlight
    const stepZ = y + i * stepDepthVal + stepDepthVal / 2
    const stepX = x + flightWidth / 2
    const stepY = baseZ + i * stepHeight + stepHeight / 2

    stepsList.push(
      <mesh key={`flight1-step-${i}`} position={[stepX, stepY, stepZ]}>
        <boxGeometry args={[flightWidth, stepHeight, stepDepthVal]} />
        <meshStandardMaterial color="#e2e8f0" roughness={0.8} />
      </mesh>
    )
  }

  // Mid Landing: Flat slab at landingHeight at the back of the core
  const landingX = x + w / 2
  const landingY = baseZ + landingHeight - stepHeight / 2
  const landingZ = y + h - landingDepth / 2

  stepsList.push(
    <mesh key="mid-landing" position={[landingX, landingY, landingZ]}>
      <boxGeometry args={[w, stepHeight, landingDepth]} />
      <meshStandardMaterial color="#cbd5e1" roughness={0.7} />
    </mesh>
  )

  // Flight 2: Rising from landingHeight to floorHeight along the right side (reverse direction)
  for (let i = 0; i < stepsPerFlight; i++) {
    const stepDepthVal = flightDepth / stepsPerFlight
    const stepZ = y + h - landingDepth - i * stepDepthVal - stepDepthVal / 2
    const stepX = x + w - flightWidth / 2
    const stepY = baseZ + landingHeight + i * stepHeight + stepHeight / 2

    stepsList.push(
      <mesh key={`flight2-step-${i}`} position={[stepX, stepY, stepZ]}>
        <boxGeometry args={[flightWidth, stepHeight, stepDepthVal]} />
        <meshStandardMaterial color="#e2e8f0" roughness={0.8} />
      </mesh>
    )
  }

  return <group>{stepsList}</group>
}

// Extrudes wall panels constructively, splitting them dynamically around door/window spans
function ProceduralWall3D({ wall, openings, floorHeight, baseZ, plotWidth, plotDepth }) {
  const [x1, y1] = wall.start
  const [x2, y2] = wall.end
  const dx = x2 - x1
  const dy = y2 - y1
  const length = Math.sqrt(dx * dx + dy * dy)
  if (length < 0.1) return null

  const ux = dx / length
  const uy = dy / length
  const angle = Math.atan2(dy, dx)

  const thickness = wall.thickness || 0.5
  const wallTypeColor = wall.type === "exterior" ? "#d1d5db" : "#f3f4f6"

  // Query opening list lying on this wall line
  const hostedOpenings = getOpeningsOnWall(wall, openings)

  // Build panels
  const panels = []
  let currentD = 0

  hostedOpenings.forEach((op, opIdx) => {
    const opW = op.width
    const opStart = op.distAlongWall - opW / 2
    const opEnd = op.distAlongWall + opW / 2

    // 1. Solid wall panel before the opening
    if (opStart > currentD + 0.05) {
      const panelL = opStart - currentD
      const midD = currentD + panelL / 2
      const cx = x1 + midD * ux
      const cy = baseZ + floorHeight / 2
      const cz = y1 + midD * uy

      panels.push(
        <mesh
          key={`wall-${wall.id}-panel-pre-${opIdx}`}
          position={[cx - plotWidth / 2, cy, cz - plotDepth / 2]}
          rotation={[0, -angle, 0]}
        >
          <boxGeometry args={[panelL, floorHeight, thickness]} />
          <meshStandardMaterial color={wallTypeColor} roughness={0.8} />
        </mesh>
      )
    }

    // 2. Transverse segments (Header / Sill) over the opening span
    const midOpD = op.distAlongWall
    const cx = x1 + midOpD * ux
    const cz = y1 + midOpD * uy

    if (op.type === "door") {
      // Header panel above door
      const headerHeight = floorHeight - 7.0
      if (headerHeight > 0.05) {
        const cy = baseZ + 7.0 + headerHeight / 2
        panels.push(
          <mesh
            key={`wall-${wall.id}-door-header-${opIdx}`}
            position={[cx - plotWidth / 2, cy, cz - plotDepth / 2]}
            rotation={[0, -angle, 0]}
          >
            <boxGeometry args={[opW, headerHeight, thickness]} />
            <meshStandardMaterial color={wallTypeColor} roughness={0.8} />
          </mesh>
        )
      }
    } else {
      // Window Sill (0 to 3 ft)
      const sillH = 3.0
      const cySill = baseZ + sillH / 2
      panels.push(
        <mesh
          key={`wall-${wall.id}-win-sill-${opIdx}`}
          position={[cx - plotWidth / 2, cySill, cz - plotDepth / 2]}
          rotation={[0, -angle, 0]}
        >
          <boxGeometry args={[opW, sillH, thickness]} />
          <meshStandardMaterial color={wallTypeColor} roughness={0.8} />
        </mesh>
      )
      // Window Header (7 to floorHeight)
      const headerHeight = floorHeight - 7.0
      if (headerHeight > 0.05) {
        const cyHeader = baseZ + 7.0 + headerHeight / 2
        panels.push(
          <mesh
            key={`wall-${wall.id}-win-header-${opIdx}`}
            position={[cx - plotWidth / 2, cyHeader, cz - plotDepth / 2]}
            rotation={[0, -angle, 0]}
          >
            <boxGeometry args={[opW, headerHeight, thickness]} />
            <meshStandardMaterial color={wallTypeColor} roughness={0.8} />
          </mesh>
        )
      }
    }

    currentD = opEnd
  })

  // 3. Final solid panel after all openings
  if (currentD + 0.05 < length) {
    const panelL = length - currentD
    const midD = currentD + panelL / 2
    const cx = x1 + midD * ux
    const cy = baseZ + floorHeight / 2
    const cz = y1 + midD * uy

    panels.push(
      <mesh
        key={`wall-${wall.id}-panel-post`}
        position={[cx - plotWidth / 2, cy, cz - plotDepth / 2]}
        rotation={[0, -angle, 0]}
      >
        <boxGeometry args={[panelL, floorHeight, thickness]} />
        <meshStandardMaterial color={wallTypeColor} roughness={0.8} />
      </mesh>
    )
  }

  return <group>{panels}</group>
}

function BuildingModel({ buildingData, activeFloorFilter }) {
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
        <meshStandardMaterial color="#11111b" roughness={0.9} />
      </mesh>

      {/* Plot Boundary Border */}
      <mesh position={[0, -0.05, 0]}>
        <boxGeometry args={[plotWidth + 4.1, 0.12, plotDepth + 4.1]} />
        <meshBasicMaterial color="#313244" wireframe />
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
            {/* Floor Slab Plate */}
            <mesh position={[0, baseZ - 0.05, 0]}>
              <boxGeometry args={[plotWidth - 0.1, 0.1, plotDepth - 0.1]} />
              <meshStandardMaterial color="#2d3748" roughness={0.65} />
            </mesh>

            {/* Room Boxes (semi-transparent color volumes) */}
            {Object.entries(layout).map(([roomName, room]) => {
              const rx = room.x + room.width / 2 - plotWidth / 2
              const rz = room.y + room.height / 2 - plotDepth / 2
              const ry = baseZ + floorHeight / 2
              const color = roomColors[room.type] || "#ffffff"
              const isOts = room.type === "OTS"

              if (isOts) return null // Shaft is open space

              return (
                <group key={`volume-${roomName}`}>
                  <mesh position={[rx, ry, rz]}>
                    <boxGeometry args={[room.width - 0.1, floorHeight - 0.1, room.height - 0.1]} />
                    <meshStandardMaterial
                      color={color}
                      transparent
                      opacity={0.06}
                      roughness={0.9}
                    />
                  </mesh>
                  {/* Floating HTML Label */}
                  <Html position={[rx, baseZ + floorHeight / 2 + 1, rz]} center distanceFactor={15}>
                    <div className="bg-[#11111b]/95 border border-border p-2 rounded text-[10px] font-mono pointer-events-none select-none text-center shadow-lg min-w-[70px]">
                      <span className="font-bold uppercase" style={{ color: color }}>{roomName}</span>
                      <div className="text-[8px] text-muted-foreground mt-0.5">{room.width}′ × {room.height}′</div>
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

            {/* 3D Doors */}
            {doors.map(d => {
              const px = d.position[0] - plotWidth / 2
              const pz = d.position[1] - plotDepth / 2
              return (
                <ProceduralDoor3D
                  key={d.id}
                  position={[px, baseZ, pz]}
                  direction={d.direction}
                  width={d.width}
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

            {/* 3D Stairs Core Steps (if hosted in core boundaries) */}
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

  return (
    <div className="relative w-full h-full bg-[#0a0a0f] flex flex-col">
      {/* Floors selection controls */}
      {buildingData && (
        <div className="absolute top-4 left-4 z-10 flex gap-1 bg-[#0d0e15]/90 border border-border p-1 rounded-sm shadow-md font-mono text-[10px]">
          <button
            onClick={() => setActiveFloorFilter('all')}
            className={`px-3 py-1.5 uppercase transition-colors cursor-pointer rounded-xs ${activeFloorFilter === 'all' ? 'bg-primary/20 text-primary font-bold' : 'text-muted-foreground hover:text-foreground'}`}
          >
            Show All Floors
          </button>
          {Array.from({ length: buildingData.floors || 1 }).map((_, idx) => (
            <button
              key={idx}
              onClick={() => setActiveFloorFilter(idx + 1)}
              className={`px-3 py-1.5 uppercase transition-colors cursor-pointer rounded-xs ${activeFloorFilter === idx + 1 ? 'bg-primary/20 text-primary font-bold' : 'text-muted-foreground hover:text-foreground'}`}
            >
              Floor {idx + 1}
            </button>
          ))}
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

          {/* Lighting systems */}
          <ambientLight intensity={0.6} color="#ffffff" />
          <directionalLight position={[30, 45, 20]} intensity={1.2} color="#ffffff" castShadow />
          <directionalLight position={[-20, 20, -25]} intensity={0.5} color="#818cf8" />
          <pointLight position={[0, 15, 0]} intensity={0.3} color="#38bdf8" />

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
            <BuildingModel buildingData={buildingData} activeFloorFilter={activeFloorFilter} />
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
