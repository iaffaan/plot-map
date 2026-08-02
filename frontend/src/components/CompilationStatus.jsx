import { motion } from 'framer-motion'
import { CheckCircle2, Circle, AlertCircle, Loader2 } from 'lucide-react'

const statusColors = {
  pending: 'text-muted-foreground',
  running: 'text-accent animate-pulse',
  complete: 'text-accent',
  error: 'text-destructive',
}

export function CompilationStatus({ stages, currentStage, isVisible }) {
  if (!isVisible) return null

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="bg-card border border-border p-6 rounded-sm space-y-4"
    >
      <div className="border-b border-border pb-4">
        <h3 className="text-sm uppercase tracking-widest text-foreground font-mono">
          Compilation Pipeline
        </h3>
      </div>

      <div className="space-y-3">
        {stages.map((stage, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
            className="space-y-1"
          >
            <div className="flex items-center gap-3">
              {stage.status === 'pending' && (
                <Circle className={`w-4 h-4 ${statusColors.pending}`} />
              )}
              {stage.status === 'running' && (
                <Loader2 className={`w-4 h-4 ${statusColors.running}`} />
              )}
              {stage.status === 'complete' && (
                <CheckCircle2 className={`w-4 h-4 ${statusColors.complete}`} />
              )}
              {stage.status === 'error' && (
                <AlertCircle className={`w-4 h-4 ${statusColors.error}`} />
              )}

              <div className="flex-1">
                <p className="text-sm text-foreground font-mono">{stage.name}</p>
              </div>

              {stage.duration && stage.status === 'complete' && (
                <span className="text-xs text-muted-foreground font-mono">
                  {stage.duration.toFixed(2)}s
                </span>
              )}
            </div>

            <p className="text-xs text-muted-foreground ml-7 font-mono">{stage.description}</p>
          </motion.div>
        ))}
      </div>

      {currentStage !== undefined && currentStage < stages.length && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="pt-4 border-t border-border"
        >
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
            <span className="text-xs text-muted-foreground font-mono">
              Processing: {stages[currentStage].name}
            </span>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
