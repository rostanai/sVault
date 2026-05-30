// Route group (app) has been moved to the real /app path segment.
// This layout is now a plain passthrough.
export default function LegacyLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
