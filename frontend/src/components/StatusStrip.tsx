import type { HealthInfo } from '../lib/api';
import { GitBranch, Database, Clock } from 'lucide-react';

type Props = {
  health?: HealthInfo;
};

export function StatusStrip({ health }: Props) {
  return (
    <div className="card" style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
      <StatusTile icon={<GitBranch size={18} />} label="Repo" value={health?.repo || 'unknown'} />
      <StatusTile icon={<Database size={18} />} label="Units indexed" value={String(health?.units ?? 0)} />
      <StatusTile icon={<Clock size={18} />} label="Last indexed" value={health?.last_indexed_at || 'pending'} />
    </div>
  );
}

function StatusTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      <span style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', color: '#475569' }}>
        {icon}
        {label}
      </span>
      <strong style={{ fontSize: '1.1rem' }}>{value}</strong>
    </div>
  );
}
