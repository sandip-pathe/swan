export default function DashboardSkeleton({
  shell = false,
}: {
  shell?: boolean;
}) {
  const content = (
    <div
      className="dashboard-skeleton"
      role="status"
      aria-label="Loading your workspace"
      aria-busy="true"
    >
      <span className="sr-only">Loading your workspace</span>
      <div className="skeleton-line skeleton-title" />
      <div className="skeleton-line skeleton-subtitle" />
      <div className="skeleton-card">
        <div className="skeleton-line skeleton-label" />
        <div className="skeleton-metrics">
          {[0, 1, 2].map((i) => (
            <div key={i}>
              <div className="skeleton-line skeleton-label" />
              <div className="skeleton-line skeleton-value" />
            </div>
          ))}
        </div>
        <div className="skeleton-line skeleton-bar" />
      </div>
      <div className="skeleton-card">
        <div className="skeleton-line skeleton-title" />
        <div className="skeleton-line" />
        <div className="skeleton-line skeleton-subtitle" />
      </div>
    </div>
  );
  return shell ? <main className="skeleton-shell">{content}</main> : content;
}
