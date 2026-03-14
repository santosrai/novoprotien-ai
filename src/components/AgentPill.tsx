import React from 'react';
import { Bot, Code, GitBranch } from 'lucide-react';

const AGENT_CONFIG: Record<string, { bg: string; text: string; label: string; icon: React.ElementType }> = {
  bio_chat: { bg: 'bg-green-100', text: 'text-green-700', label: 'BioChat', icon: Bot },
  code_builder: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Code Builder', icon: Code },
  pipeline: { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Pipeline', icon: GitBranch },
};

interface AgentPillProps {
  agentId: string;
  className?: string;
}

export const AgentPill: React.FC<AgentPillProps> = ({ agentId, className = '' }) => {
  const config = AGENT_CONFIG[agentId];
  if (!config) return null;

  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text} ${className}`}
    >
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
};
