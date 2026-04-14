import {
  STATUS_BADGE_VARIANTS,
  StatusBadge,
} from "@/components/ui/status-badge";

export function StatusBadgeDemo() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-muted-foreground">
          Tamanho md
        </h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {STATUS_BADGE_VARIANTS.map((variant) => (
            <StatusBadge key={variant} variant={variant} size="md" />
          ))}
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium text-muted-foreground">
          Tamanho sm
        </h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {STATUS_BADGE_VARIANTS.map((variant) => (
            <StatusBadge key={variant} variant={variant} size="sm" />
          ))}
        </div>
      </div>
    </div>
  );
}
