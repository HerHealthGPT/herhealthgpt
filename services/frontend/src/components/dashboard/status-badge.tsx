import { cn } from "@/lib/utils";

type StatusBadgeProps = {
  children: React.ReactNode;
  variant?: "soon" | "ready";
};

export function StatusBadge({ children, variant = "soon" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variant === "ready"
          ? "bg-primary/10 text-primary"
          : "bg-muted text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}
