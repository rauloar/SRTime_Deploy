export interface OperationJob {
  id: string
  state: "queued" | "running" | "completed" | "failed"
  current: number
  total: number
  percent: number
  message: string
  error?: string | null
  result?: { processed_days?: number; total?: number; nuevos?: number; duplicados?: number; logs?: string[] } | null
}

export default function OperationProgress({ job }: { job: OperationJob | null }) {
  if (!job) return null
  const indeterminate = job.state !== "completed" && job.total === 0
  return (
    <div className="operation-progress" role="status" aria-live="polite">
      <div className="operation-progress-label"><span>{job.message}</span><strong>{indeterminate ? "En curso" : `${job.percent}%`}</strong></div>
      <div className="operation-progress-track"><div className={`operation-progress-bar${indeterminate ? " indeterminate" : ""}`} style={indeterminate ? undefined : { width: `${job.percent}%` }} /></div>
      {job.total > 0 && <small>{job.current} de {job.total}</small>}
    </div>
  )
}
