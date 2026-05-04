import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  note?: string;
  icon: LucideIcon;
  tone?: "blue" | "green" | "amber" | "red" | "violet";
}

export function MetricCard({ label, value, note, icon: Icon, tone = "blue" }: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__icon" aria-hidden="true">
        <Icon size={18} />
      </div>
      <div>
        <p className="metric-card__label">{label}</p>
        <strong>{value}</strong>
        {note ? <span>{note}</span> : null}
      </div>
    </article>
  );
}
