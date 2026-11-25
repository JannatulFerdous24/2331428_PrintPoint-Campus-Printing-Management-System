interface Props {
  skip: number
  limit: number
  total: number
  onChange: (skip: number) => void
}

export function Pagination({ skip, limit, total, onChange }: Props) {
  if (total <= limit) return total > 0 ? <p className="muted">{total} result{total === 1 ? "" : "s"}</p> : null
  const page = Math.floor(skip / limit) + 1
  const pages = Math.ceil(total / limit)
  return (
    <div className="pagination">
      <button className="btn btn-sm btn-secondary" disabled={skip === 0} onClick={() => onChange(Math.max(0, skip - limit))}>
        ← Previous
      </button>
      <span className="muted">Page {page} of {pages} · {total} results</span>
      <button className="btn btn-sm btn-secondary" disabled={page >= pages} onClick={() => onChange(skip + limit)}>
        Next →
      </button>
    </div>
  )
}
