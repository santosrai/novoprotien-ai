import React from 'react';
import { MessageSquare, Box, Workflow, FolderOpen } from 'lucide-react';

export type MobileTab = 'chat' | 'viewer' | 'pipeline' | 'files';

interface MobileSegmentedControlProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
}

const tabs: { id: MobileTab; label: string; icon: React.ElementType }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'viewer', label: '3D View', icon: Box },
  { id: 'pipeline', label: 'Pipeline', icon: Workflow },
  { id: 'files', label: 'Files', icon: FolderOpen },
];

export const MobileSegmentedControl: React.FC<MobileSegmentedControlProps> = ({
  activeTab,
  onTabChange,
}) => {
  return (
    <div className="sticky top-0 z-30 px-3 py-2 bg-white border-b border-gray-200 md:hidden">
      <div className="flex items-center bg-gray-100 rounded-full p-1">
        {tabs.map(({ id, label, icon: Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              onClick={() => onTabChange(id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-full text-xs font-medium transition-all ${
                isActive
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
