import React from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  defaultExpanded?: boolean;
  className?: string;
  children: React.ReactNode;
}

export const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  title,
  defaultExpanded = false,
  className = '',
  children,
}) => {
  const [isOpen, setIsOpen] = React.useState(defaultExpanded);
  const contentId = React.useId();

  const handleToggle = () => {
    setIsOpen((prev) => !prev);
  };

  return (
    <div className={`text-xs ${className}`}>
      <button
        type="button"
        onClick={handleToggle}
        className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-700 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-sm"
        aria-expanded={isOpen}
        aria-controls={contentId}
      >
        {isOpen ? (
          <ChevronDown className="w-3 h-3 shrink-0" aria-hidden="true" />
        ) : (
          <ChevronRight className="w-3 h-3 shrink-0" aria-hidden="true" />
        )}
        <span>{title}</span>
      </button>
      {isOpen && (
        <div
          id={contentId}
          className="mt-1.5 rounded-md border border-gray-200 bg-white/80 max-h-72 overflow-auto text-[11px] leading-relaxed"
        >
          {children}
        </div>
      )}
    </div>
  );
};

