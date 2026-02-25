export function PageRefreshSkeleton() {
  return (
    <div className="relative flex-1 flex flex-col bg-white">
      <div className="px-3 py-1.5 border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center space-x-2">
          <div className="h-3.5 w-3.5 rounded-full bg-blue-200 animate-pulse" />
          <div className="space-y-1">
            <div className="h-2.5 w-20 rounded bg-gray-200 animate-pulse" />
            <div className="h-2 w-28 rounded bg-gray-100 animate-pulse" />
          </div>
        </div>
      </div>

      <div className="flex-1 p-4 space-y-4 overflow-hidden">
        <div className="space-y-2">
          <div className="h-3 w-32 rounded bg-gray-100 shimmer" />
          <div className="h-10 rounded-lg bg-gray-100 shimmer" />
        </div>
        <div className="space-y-2">
          <div className="h-3 w-40 rounded bg-gray-100 shimmer" />
          <div className="h-14 rounded-lg bg-gray-100 shimmer" />
        </div>
        <div className="space-y-2">
          <div className="h-3 w-24 rounded bg-gray-100 shimmer" />
          <div className="h-12 rounded-lg bg-gray-100 shimmer" />
        </div>
      </div>

      <div className="border-t border-gray-200 p-3 space-y-2">
        <div className="h-3 w-20 rounded bg-gray-100 shimmer" />
        <div className="h-12 rounded-xl bg-gray-100 shimmer" />
      </div>

      <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
        <div className="inline-flex items-center gap-2 rounded-md bg-white/80 px-3 py-1 text-sm text-gray-500 backdrop-blur-[1px]">
          <span className="inline-block h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
          Restoring your workspace...
        </div>
      </div>

      <style>{`
        .shimmer {
          position: relative;
          overflow: hidden;
        }
        .shimmer::after {
          content: '';
          position: absolute;
          inset: 0;
          transform: translateX(-100%);
          background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.55) 50%, transparent 100%);
          animation: refresh-shimmer 1.8s ease-in-out infinite;
        }
        @keyframes refresh-shimmer {
          100% { transform: translateX(100%); }
        }
        @media (prefers-reduced-motion: reduce) {
          .shimmer::after {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}
