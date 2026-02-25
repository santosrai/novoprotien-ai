import React from 'react';

interface MolstarSkeletonProps {
  message?: string;
  className?: string;
}

export const MolstarSkeleton: React.FC<MolstarSkeletonProps> = ({
  message = 'Loading molecular viewer...',
  className = '',
}) => {
  return (
    <div className={`h-full w-full bg-gray-900 text-gray-300 ${className}`}>
      <div className="h-full w-full flex flex-col">
        <div className="h-11 border-b border-gray-800 px-4 flex items-center gap-3">
          <div className="h-6 w-14 rounded bg-gray-800 animate-pulse" />
          <div className="h-6 w-16 rounded bg-gray-800 animate-pulse" />
          <div className="h-6 w-12 rounded bg-gray-800 animate-pulse" />
          <div className="ml-auto h-6 w-40 rounded bg-gray-800 animate-pulse" />
        </div>

        <div className="flex-1 relative p-4">
          <div className="absolute inset-4 rounded-md border border-gray-800 bg-gray-900/60 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-[shimmer_1.6s_infinite]" />
          </div>

          <div className="absolute top-8 right-8 flex flex-col gap-2">
            <div className="h-8 w-8 rounded bg-gray-800 animate-pulse" />
            <div className="h-8 w-8 rounded bg-gray-800 animate-pulse" />
            <div className="h-8 w-8 rounded bg-gray-800 animate-pulse" />
          </div>

          <div className="absolute bottom-10 left-10 h-12 w-12 rounded bg-gray-800 animate-pulse" />
        </div>

        <div className="pb-5 text-center text-sm text-gray-400">
          {message}
        </div>
      </div>

      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
};
