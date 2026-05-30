import Link from "next/link";

export function Logo({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      className={`flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg ${className ?? ""}`}
      aria-label="sVault home"
    >
      {/* Shield SVG — brand icon */}
      <svg
        width="32"
        height="32"
        viewBox="0 0 512 512"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
      >
        <rect width="512" height="512" rx="116" fill="url(#logo-g)" />
        <path
          d="M256 92 L388 142 V262 C388 344 324 404 256 424 C188 404 124 344 124 262 V142 Z"
          fill="white"
          fillOpacity="0.96"
        />
        <path
          d="M210 262 l32 32 l62 -74"
          stroke="#2746c9"
          strokeWidth="30"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <defs>
          <linearGradient
            id="logo-g"
            x1="0"
            y1="0"
            x2="512"
            y2="512"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#4b7bf5" />
            <stop offset="1" stopColor="#2746c9" />
          </linearGradient>
        </defs>
      </svg>
      <span className="text-lg font-bold tracking-tight text-zinc-900 dark:text-white">
        sVault
      </span>
    </Link>
  );
}
