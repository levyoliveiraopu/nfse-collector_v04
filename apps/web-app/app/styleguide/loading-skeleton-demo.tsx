import { LoadingSkeleton } from "@/components/ui/loading-skeleton";

export function LoadingSkeletonDemo() {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Variante lines (4)
        </p>
        <LoadingSkeleton lines={4} />
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Variante rows (3 x 5)
        </p>
        <LoadingSkeleton rows={3} columns={5} />
      </div>
    </div>
  );
}
