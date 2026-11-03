interface Props {
  message: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({ message, onConfirm, onCancel }: Props) {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: "8px",
          padding: "24px",
          maxWidth: "400px",
          width: "90%",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
      >
        <p style={{ margin: "0 0 20px", fontSize: "16px" }}>{message}</p>
        <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm}>
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}
