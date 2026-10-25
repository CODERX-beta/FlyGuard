import React from "react";
import { AlertTriangle, ShieldAlert, Activity, CheckCircle2 } from "lucide-react";

interface RiskBadgeProps {
  category: string;
  score?: number;
  size?: "sm" | "md" | "lg";
}

/**
 * Accessible risk indicator that pairs distinct iconography, explicit text label,
 * numerical score, and high-contrast border/color styling so users never rely on color alone.
 */
export const RiskBadge: React.FC<RiskBadgeProps> = ({
  category,
  score,
  size = "sm",
}) => {
  const cat = (category || "Low") as string;

  let classes =
    "bg-emerald-500/15 text-emerald-300 border-emerald-500/40";
  let Icon = CheckCircle2;

  if (cat === "Critical") {
    classes = "bg-red-500/20 text-red-300 border-red-500/50";
    Icon = AlertTriangle;
  } else if (cat === "High") {
    classes = "bg-orange-500/20 text-orange-300 border-orange-500/50";
    Icon = ShieldAlert;
  } else if (cat === "Moderate" || cat === "Medium") {
    classes = "bg-amber-500/20 text-amber-300 border-amber-500/50";
    Icon = Activity;
  }

  const sizeClasses =
    size === "lg"
      ? "px-3 py-1 text-xs font-semibold gap-1.5"
      : size === "md"
      ? "px-2.5 py-0.5 text-xs font-medium gap-1.5"
      : "px-2 py-0.5 text-[11px] font-medium gap-1";

  return (
    <span
      className={`inline-flex items-center rounded-md border ${classes} ${sizeClasses}`}
      title={`Risk Category: ${cat}${score !== undefined ? ` (Triage Score: ${score.toFixed(1)}/100)` : ""}`}
    >
      <Icon className={size === "lg" ? "w-3.5 h-3.5" : "w-3 h-3"} />
      <span>{cat}</span>
      {score !== undefined && (
        <span className="font-mono opacity-90">({Math.round(score)})</span>
      )}
    </span>
  );
};

