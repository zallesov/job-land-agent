export function Logo({ iconSize = 22 }: { iconSize?: number }) {
  return (
    <div className="flex items-center gap-2 select-none">
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <rect width="32" height="32" rx="7" fill="#030712" />
        <circle
          cx="16" cy="16" r="11"
          stroke="#22c55e" strokeWidth="2" strokeLinecap="round"
          strokeDasharray="51.8 17.3"
          transform="rotate(-135 16 16)"
        />
        <circle cx="16" cy="16" r="6.5" stroke="#22c55e" strokeWidth="1.2" opacity="0.4" />
        <circle cx="16" cy="16" r="2.5" fill="#22c55e" />
      </svg>
      <span className="logo-text text-lg font-black tracking-tight">
        JobLand<span style={{ letterSpacing: "-0.02em" }}>Agent</span>
      </span>
    </div>
  );
}
