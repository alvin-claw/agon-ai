"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="text-center py-20">
      <h2 className="text-xl font-bold text-red-400 mb-2">Something went wrong</h2>
      <p className="text-muted text-sm mb-6">
        {error.message || "An unexpected error occurred."}
      </p>
      <button
        onClick={reset}
        className="rounded-lg bg-accent px-6 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
      >
        Try Again
      </button>
    </div>
  );
}
