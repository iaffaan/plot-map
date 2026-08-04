import { motion } from 'framer-motion'
import { Download, Share2, Maximize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ResultsPanel({ metrics, projectId, isVisible, explanation }) {
  if (!isVisible || !metrics) return null

  const metricGroups = [
    {
      label: 'AREA METRICS',
      items: [
        { label: 'Total Built Area', value: `${metrics.totalArea.toFixed(1)} sq ft` },
        { label: 'Usable Area', value: `${metrics.usableArea.toFixed(1)} sq ft` },
        { label: 'Plot Coverage', value: `${metrics.plotCoverage.toFixed(1)}%` },
        { label: 'FSI/FAR', value: metrics.fsi.toFixed(2) },
      ],
    },
    {
      label: 'ENVIRONMENTAL SCORES',
      items: [
        { label: 'Cross-Ventilation', value: `${metrics.ventilationScore.toFixed(0)}%` },
        { label: 'Daylighting', value: `${metrics.daylightScore.toFixed(0)}%` },
      ],
    },
    {
      label: 'COMPLIANCE & FEASIBILITY',
      items: [
        { label: 'Municipal Setbacks', value: `${metrics.structuralCompliance.toFixed(0)}%` },
        { label: 'Est. Construction Cost', value: metrics.estimatedCost },
        { label: 'Timeline', value: metrics.constructionTime },
      ],
    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="border-b border-border pb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-2xl font-light tracking-wide text-foreground">BLUEPRINT GENERATED</h2>
            <p className="text-sm text-muted-foreground font-mono mt-2">
              {projectId ? `Project ID: ${projectId}` : 'Ready for download'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="border-border hover:bg-card"
              onClick={() => alert('Export feature coming soon')}
            >
              <Download className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-border hover:bg-card"
              onClick={() => alert('Share feature coming soon')}
            >
              <Share2 className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-border hover:bg-card"
              onClick={() => alert('Fullscreen mode coming soon')}
            >
              <Maximize2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      {metricGroups.map((group, idx) => (
        <motion.div
          key={idx}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: idx * 0.1 }}
          className="space-y-3"
        >
          <h3 className="text-xs uppercase tracking-widest text-muted-foreground font-mono border-b border-border pb-3">
            {group.label}
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {group.items.map((item, itemIdx) => (
              <div key={itemIdx} className="space-y-1">
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-wide">
                  {item.label}
                </p>
                <p className="text-lg font-light text-foreground tracking-tight">
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        </motion.div>
      ))}

      {/* AI Design Explanation */}
      {explanation && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="space-y-4 bg-[#11111b]/40 border border-border p-5 rounded-sm"
        >
          <h3 className="text-xs uppercase tracking-widest text-primary font-mono border-b border-border/80 pb-3">
            AI ARCHITECTURAL ANALYSIS
          </h3>
          
          <div className="space-y-4 font-mono text-xs leading-relaxed">
            <div className="space-y-1">
              <span className="text-muted-foreground uppercase tracking-wider block font-bold">Concept & Zoning</span>
              <span className="text-foreground/95">{explanation.overall_concept}</span>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground uppercase tracking-wider block font-bold">Kitchen Placement</span>
              <span className="text-foreground/95">{explanation.kitchen_placement}</span>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground uppercase tracking-wider block font-bold">Plumbing Stacking</span>
              <span className="text-foreground/95">{explanation.plumbing_efficiency}</span>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground uppercase tracking-wider block font-bold">Vastu Compliance</span>
              <span className="text-foreground/95">{explanation.vastu_compliance}</span>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground uppercase tracking-wider block font-bold">Circulation Flow</span>
              <span className="text-foreground/95">{explanation.circulation_efficiency}</span>
            </div>
          </div>
        </motion.div>
      )}

      {/* Action Footer */}
      <div className="border-t border-border pt-6 flex gap-4">
        <Button className="flex-1 bg-foreground text-background hover:bg-foreground/90 font-mono text-sm uppercase h-10">
          Download DWG
        </Button>
        <Button
          variant="outline"
          className="flex-1 border-border text-foreground hover:bg-card font-mono text-sm uppercase h-10"
        >
          View 3D Model
        </Button>
      </div>

      {/* Disclaimer */}
      <div className="bg-card border border-border p-4 rounded-sm">
        <p className="text-xs text-muted-foreground font-mono">
          ⚠ This blueprint is AI-generated and optimized. Always verify with local authorities and
          structural engineers before construction. Compliance guaranteed within municipal parameters.
        </p>
      </div>
    </motion.div>
  )
}
