import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Infinity, Bot, Code, GitBranch } from 'lucide-react';
import { useAgentSettings } from '../stores/settingsStore';

interface SupervisorAgent {
  id: string;
  name: string;
  description: string;
  icon: React.ElementType;
}

const SUPERVISOR_AGENTS: SupervisorAgent[] = [
  { id: 'bio_chat', name: 'BioChat', description: 'Protein Q&A, structure analysis, computational tools', icon: Bot },
  { id: 'code_builder', name: 'Code Builder', description: 'MolStar visualization, 3D structure code', icon: Code },
  { id: 'pipeline', name: 'Pipeline', description: 'Workflow composition, multi-step pipelines', icon: GitBranch },
];

interface AgentSelectorProps {
  onAgentChange?: (agentId: string | null) => void;
}

export const AgentSelector: React.FC<AgentSelectorProps> = ({ onAgentChange }) => {
  const { settings, updateSettings } = useAgentSettings();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedAgentId = settings.selectedAgentId;
  const selectedAgent = SUPERVISOR_AGENTS.find(a => a.id === selectedAgentId);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleSelect = (agentId: string | null) => {
    updateSettings({ selectedAgentId: agentId });
    onAgentChange?.(agentId);
    setIsOpen(false);
  };

  const displayText = selectedAgent ? selectedAgent.name : 'Auto';

  return (
    <div className="relative min-w-0 flex-shrink" ref={dropdownRef} style={{ maxWidth: '140px', flexShrink: 1 }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 w-full min-w-0"
        title={displayText}
      >
        <Infinity className="w-3 h-3 shrink-0" />
        <span className="truncate min-w-0 flex-1 text-left overflow-hidden text-ellipsis whitespace-nowrap">{displayText}</span>
        <ChevronDown className={`w-2.5 h-2.5 transition-transform shrink-0 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-[100] overflow-hidden flex flex-col">
          <div className="p-2">
            {/* Auto option */}
            <button
              onClick={() => handleSelect(null)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                selectedAgentId === null
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2">
                <Infinity className="w-4 h-4" />
                <div>
                  <div className="font-medium">Auto</div>
                  <div className="text-xs text-gray-500">Supervisor routes automatically</div>
                </div>
              </div>
            </button>

            <div className="border-t border-gray-200 my-2" />

            {/* 3 supervisor agents */}
            {SUPERVISOR_AGENTS.map(agent => {
              const Icon = agent.icon;
              return (
                <button
                  key={agent.id}
                  onClick={() => handleSelect(agent.id)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                    selectedAgentId === agent.id
                      ? 'bg-blue-50 text-blue-700 font-medium'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 shrink-0" />
                    <div>
                      <div className="font-medium">{agent.name}</div>
                      <div className="text-xs text-gray-500 line-clamp-1">{agent.description}</div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
