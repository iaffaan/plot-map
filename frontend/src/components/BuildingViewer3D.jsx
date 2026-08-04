import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Html } from '@react-three/drei'
import { useEffect, useRef } from 'react'

const roomColors = {
  "Entrance": "#89b4fa",       // Pastel Blue
  "Living Room": "#cba6f7",     // Pastel Purple
  "Kitchen": "#f9e2af",         // Pastel Yellow
  "Bedroom": "#a6e3a1",         // Pastel Green
  "Bathroom": "#f2cdcd",        // Pastel Pink
  "Corridor": "#94e2d5",        // Pastel Teal
  "OTS": "#74c7ec",             // Sky Blue (shafts)
  "Staircase": "#f38ba8",       // Soft Red
}

function BuildingModel({ buildingData }) {
  const meshRef = useRef(null)

  useEffect(() => {
    if (meshRef.current) {
      // Subtle rotation animation
      const animation = setInterval(() => {
        if (meshRef.current) {
          meshRef.current.rotation.y += 0.0005
        }
      }, 30)
      return () => clearInterval(animation)
    }
  }, [])

  if (!buildingData) {
    return (
      <group ref={meshRef}>
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[2, 3, 2]} />
          <meshPhongMaterial color="#ffffff" wireframe />
        </mesh>
      </group>
    )
  }

  const { width: plotWidth, depth: plotDepth, floors, layout, boundaries } = buildingData
  const height = floors * 10
  const floorHeight = height / Math.max(floors, 1)

  // Parse stair core bounding box
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

  // Parse buildable envelope bounding box
  let envelopeRect = null
  if (boundaries?.envelope && boundaries.envelope.length > 0) {
    const xs = boundaries.envelope.map(c => c[0])
    const ys = boundaries.envelope.map(c => c[1])
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    
    envelopeRect = {
      x: minX,
      y: minY,
      w: maxX - minX,
      h: maxY - minY
    }
  }

  return (
    <group ref={meshRef}>
      {/* 1. Plot Base Slab */}
      <mesh position={[0, -0.1, 0]}>
        <boxGeometry args={[plotWidth, 0.2, plotDepth]} />
        <meshPhongMaterial color="#181825" shininess={10} />
      </mesh>
      {/* Plot Base Slab Outline */}
      <mesh position={[0, -0.1, 0]}>
        <boxGeometry args={[plotWidth + 0.1, 0.21, plotDepth + 0.1]} />
        <meshBasicMaterial color="#313244" wireframe />
      </mesh>

      {/* 2. Buildable Envelope outline on ground */}
      {envelopeRect && (
        <mesh position={[
          envelopeRect.x + envelopeRect.w / 2 - plotWidth / 2,
          0.02,
          envelopeRect.y + envelopeRect.h / 2 - plotDepth / 2
        ]}>
          <boxGeometry args={[envelopeRect.w, 0.01, envelopeRect.h]} />
          <meshBasicMaterial color="#a6e3a1" wireframe opacity={0.6} transparent />
        </mesh>
      )}

      {/* 3. Stair Core Tower (vertical circulation through all floors) */}
      {stairCoreRect && stairCoreRect.w > 0 && (
        <group position={[
          stairCoreRect.x + stairCoreRect.w / 2 - plotWidth / 2,
          height / 2,
          stairCoreRect.y + stairCoreRect.h / 2 - plotDepth / 2
        ]}>
          {/* Stair Core Solid Box */}
          <mesh>
            <boxGeometry args={[stairCoreRect.w, height, stairCoreRect.h]} />
            <meshPhongMaterial color={roomColors["Staircase"]} opacity={0.3} transparent />
          </mesh>
          {/* Stair Core Wireframe */}
          <mesh>
            <boxGeometry args={[stairCoreRect.w + 0.05, height + 0.05, stairCoreRect.h + 0.05]} />
            <meshBasicMaterial color={roomColors["Staircase"]} wireframe opacity={0.7} transparent />
          </mesh>
          {/* Stair Core Label (centered) */}
          <Html position={[0, height / 2 - 2, 0]} center distanceFactor={15}>
            <div className="bg-rose-950/90 border border-rose-500/30 px-2 py-1 rounded text-[10px] font-mono font-bold text-rose-300 pointer-events-none select-none">
              STAIR CORE
            </div>
          </Html>
        </group>
      )}

      {/* 4. Building Floor Slabs */}
      {Array.from({ length: floors }).map((_, f) => (
        <mesh key={`floor-slab-${f}`} position={[0, (f + 1) * floorHeight, 0]}>
          <boxGeometry args={[plotWidth - 0.2, 0.1, plotDepth - 0.2]} />
          <meshPhongMaterial color="#1e1e2e" opacity={0.5} transparent />
        </mesh>
      ))}

      {/* 5. Structural Columns (four corners of plot) */}
      {[
        [-plotWidth / 2, height / 2, -plotDepth / 2],
        [plotWidth / 2, height / 2, -plotDepth / 2],
        [-plotWidth / 2, height / 2, plotDepth / 2],
        [plotWidth / 2, height / 2, plotDepth / 2],
      ].map((pos, i) => (
        <mesh key={`column-${i}`} position={[pos[0], pos[1], pos[2]]}>
          <boxGeometry args={[0.4, height, 0.4]} />
          <meshPhongMaterial color="#45475a" />
        </mesh>
      ))}

      {/* 6. Layout Rooms Rendered Floor-by-Floor */}
      {buildingData.floors_data ? (
        Object.entries(buildingData.floors_data).flatMap(([floorIdxStr, floorData]) => {
          const f = parseInt(floorIdxStr) - 1
          const ry = f * floorHeight + (floorHeight - 0.1) / 2
          
          return Object.entries(floorData.layout || {}).map(([roomName, room]) => {
            const rx = room.x + room.width / 2 - plotWidth / 2
            const rz = room.y + room.height / 2 - plotDepth / 2
            const color = roomColors[room.type] || "#cdd6f4"
            const isOts = room.type === "OTS"
            
            return (
              <group key={`room-${roomName}-floor-${f}`}>
                {/* Room volume block */}
                <mesh position={[rx, ry, rz]}>
                  <boxGeometry args={[room.width, floorHeight - 0.15, room.height]} />
                  <meshPhongMaterial 
                    color={color} 
                    opacity={isOts ? 0.15 : 0.45} 
                    transparent 
                    shininess={isOts ? 0 : 30}
                  />
                </mesh>
                
                {/* Room wireframe wall outlines */}
                <mesh position={[rx, ry, rz]}>
                  <boxGeometry args={[room.width + 0.02, floorHeight - 0.14, room.height + 0.02]} />
                  <meshBasicMaterial 
                    color={color} 
                    wireframe 
                    opacity={isOts ? 0.3 : 0.8} 
                    transparent 
                  />
                </mesh>

                {/* Room Tag Label */}
                <Html position={[rx, ry + 1.2, rz]} center distanceFactor={12}>
                  <div style={{
                    color: '#ffffff',
                    background: 'rgba(17, 17, 27, 0.9)',
                    border: `1px solid ${color}40`,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    pointerEvents: 'none',
                    textAlign: 'center',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
                  }}>
                    <span style={{ fontWeight: 'bold', color: color }}>{roomName}</span>
                    <div style={{ fontSize: '8px', opacity: 0.65, marginTop: '1px' }}>
                      {room.width}x{room.height} ft
                    </div>
                  </div>
                </Html>
              </group>
            )
          })
        })
      ) : (
        layout && Object.values(layout).map((room) => {
          // Compute horizontal positions relative to centered plot coordinates
          const rx = room.x + room.width / 2 - plotWidth / 2
          const rz = room.y + room.height / 2 - plotDepth / 2
          const color = roomColors[room.type] || "#cdd6f4"
          const isOts = room.type === "OTS"

          return Array.from({ length: floors }).map((_, f) => {
            const ry = f * floorHeight + (floorHeight - 0.1) / 2
            
            return (
              <group key={`room-${room.name}-floor-${f}`}>
                {/* Room volume block */}
                <mesh position={[rx, ry, rz]}>
                  <boxGeometry args={[room.width, floorHeight - 0.15, room.height]} />
                  <meshPhongMaterial 
                    color={color} 
                    opacity={isOts ? 0.15 : 0.45} 
                    transparent 
                    shininess={isOts ? 0 : 30}
                  />
                </mesh>
                
                {/* Room wireframe wall outlines */}
                <mesh position={[rx, ry, rz]}>
                  <boxGeometry args={[room.width + 0.02, floorHeight - 0.14, room.height + 0.02]} />
                  <meshBasicMaterial 
                    color={color} 
                    wireframe 
                    opacity={isOts ? 0.3 : 0.8} 
                    transparent 
                  />
                </mesh>

                {/* Room Tag Label */}
                {f === floors - 1 && (
                  <Html position={[rx, ry + 1.2, rz]} center distanceFactor={12}>
                    <div style={{
                      color: '#ffffff',
                      background: 'rgba(17, 17, 27, 0.9)',
                      border: `1px solid ${color}40`,
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '10px',
                      fontFamily: 'monospace',
                      pointerEvents: 'none',
                      textAlign: 'center',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
                    }}>
                      <span style={{ fontWeight: 'bold', color: color }}>{room.name}</span>
                      <div style={{ fontSize: '8px', opacity: 0.65, marginTop: '1px' }}>
                        {room.width}x{room.height} ft
                      </div>
                    </div>
                  </Html>
                )}
              </group>
            )
          })
        })
      )}
    </group>
  )
}

export function BuildingViewer3D({ buildingData, isLoading }) {
  return (
    <div className="relative w-full h-full bg-[#0a0a0a]">
      <Canvas
        camera={{
          position: [35, 30, 35],
          fov: 45,
          near: 0.1,
          far: 2000,
        }}
        dpr={[1, 2]}
      >
        <color attach="background" args={['#0c0c0e']} />

        {/* Lighting */}
        <ambientLight intensity={0.7} color="#ffffff" />
        <directionalLight position={[20, 30, 20]} intensity={1.0} color="#ffffff" />
        <directionalLight position={[-20, 15, -20]} intensity={0.5} color="#89b4fa" />
        <pointLight position={[0, 20, 0]} intensity={0.4} color="#94e2d5" />

        {/* Dynamic Spatial Grid */}
        <Grid
          args={[80, 80]}
          cellSize={1}
          cellColor="#181825"
          sectionSize={5}
          sectionColor="#313244"
          fadeStrength={0.65}
          fadeDistance={60}
          infiniteGrid
        />

        {/* Building 3D geometry compiler */}
        <BuildingModel buildingData={buildingData} />

        {/* Controls */}
        <OrbitControls
          autoRotate={!buildingData}
          autoRotateSpeed={0.5}
          minDistance={10}
          maxDistance={120}
          enableDamping
          dampingFactor={0.05}
        />
      </Canvas>

      {/* Overlay status for compilation */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/65 backdrop-blur-sm z-35">
          <div className="flex flex-col items-center gap-4 bg-card border border-border p-6 rounded-md shadow-2xl">
            <div className="w-10 h-10 border-4 border-accent/20 border-t-accent rounded-full animate-spin" />
            <div className="text-center">
              <h4 className="text-sm font-semibold text-foreground uppercase tracking-wider font-mono">Running Compiler</h4>
              <p className="text-xs text-muted-foreground font-mono mt-1">Executing mathematical packing model...</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
