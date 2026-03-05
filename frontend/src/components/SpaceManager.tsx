/** Placeholder — full implementation in next commit. */
interface Props { onClose: () => void; }
export function SpaceManager({ onClose }: Props) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={onClose}>
      <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: '8px', minWidth: 300 }} onClick={e => e.stopPropagation()}>
        <p>Space Manager — coming in next commit</p>
        <button onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
