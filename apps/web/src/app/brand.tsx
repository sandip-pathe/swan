export default function Brand({ markOnly = false }: { markOnly?: boolean }) {
  return (
    <span className="swan-brand">
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <path d="M7 22 15 9l3 8 7-5-9 13-3-8Z" fill="currentColor" />
      </svg>
      {!markOnly && (
        <span>
          swan<span className="brand-period">.</span>
        </span>
      )}
    </span>
  );
}
