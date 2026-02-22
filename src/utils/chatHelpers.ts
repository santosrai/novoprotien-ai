import type { ErrorDetails } from './errorHandler';
import { ErrorCategory, ErrorSeverity } from './errorHandler';

export type ThinkingStep = {
  id: string;
  title: string;
  content: string;
  status: 'pending' | 'processing' | 'completed';
  timestamp?: Date;
};

export type ConvertThinkingDataResult = {
  steps: ThinkingStep[];
  isComplete: boolean;
  totalSteps: number;
};

export function convertThinkingData(
  thinkingProcess: any
): ConvertThinkingDataResult | undefined {
  if (!thinkingProcess) return undefined;

  if (thinkingProcess.steps && Array.isArray(thinkingProcess.steps)) {
    return {
      steps: thinkingProcess.steps.map((step: any) => ({
        id: step.id || `step_${Math.random()}`,
        title: step.title || 'Thinking Step',
        content: step.content || '',
        status: step.status || 'completed',
        timestamp: step.timestamp ? new Date(step.timestamp) : undefined
      })),
      isComplete: thinkingProcess.isComplete !== false,
      totalSteps: thinkingProcess.totalSteps || thinkingProcess.steps.length
    };
  }

  return undefined;
}

export function getExecutionMessage(userRequest: string): string {
  const request = userRequest.toLowerCase().trim();

  const subjectMatch = request.match(/(?:show|display|visualize|view|load|open|see)\s+(.+?)(?:\s|$)/i);
  const subject = subjectMatch ? subjectMatch[1].trim() : request;

  const cleanSubject = subject.replace(/\s+(structure|protein|molecule|chain|helix)$/i, '').trim();

  if (cleanSubject && cleanSubject.length < 40 && cleanSubject.length > 0) {
    const capitalized = cleanSubject.charAt(0).toUpperCase() + cleanSubject.slice(1);
    return `Loading ${capitalized}...`;
  }

  return 'Loading structure...';
}

export function extractProteinMPNNSequences(payload: any): string[] {
  if (!payload) return [];

  const search = (data: any): string[] => {
    if (!data) return [];
    const candidates: string[] = [];
    const possibleFields = ['designed_sequences', 'designed_seqs', 'sequences', 'output_sequences'];

    for (const field of possibleFields) {
      if (Array.isArray(data?.[field])) {
        return data[field].filter((item: unknown) => typeof item === 'string');
      }
    }

    if (Array.isArray(data)) {
      return data.filter((item) => typeof item === 'string');
    }

    if (typeof data === 'object') {
      const inner = data?.result || data?.data;
      if (inner) {
        const nested = search(inner);
        if (nested.length > 0) {
          return nested;
        }
      }
    }

    return candidates;
  };

  return search(payload);
}

export function createProteinMPNNError(
  code: string,
  userMessage: string,
  technicalMessage: string,
  context: Record<string, any>
): ErrorDetails {
  return {
    code,
    category: ErrorCategory.PROCESSING,
    severity: ErrorSeverity.HIGH,
    userMessage,
    technicalMessage,
    context,
    suggestions: [
      {
        action: 'Retry sequence design',
        description: 'Try submitting the ProteinMPNN job again or adjust the parameters.',
        type: 'retry',
        priority: 1,
      },
      {
        action: 'Verify backbone structure',
        description: 'Ensure the selected PDB backbone is valid and contains the intended chains.',
        type: 'fix',
        priority: 2,
      },
    ],
    timestamp: new Date(),
  };
}

export function isLikelyVisualization(text: string): boolean {
  const p = String(text || '').toLowerCase();
  const keywords = [
    'show ', 'display ', 'visualize', 'render', 'color', 'colour', 'cartoon', 'surface', 'ball-and-stick', 'water', 'ligand', 'focus', 'zoom', 'load', 'pdb', 'highlight', 'chain', 'view', 'representation'
  ];
  return keywords.some(k => p.includes(k));
}
