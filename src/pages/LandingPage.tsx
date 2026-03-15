import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { LandingHeader } from '../components/LandingHeader';
import { Send, Mic } from 'lucide-react';

const quickPrompts = [
  'Show insulin',
  'Display hemoglobin',
  'Visualize DNA double helix',
  'Show antibody structure',
];

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const [input, setInput] = useState('');

  // Authenticated users go to the full app with chat history
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate('/app', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  if (isAuthenticated) {
    return null;
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    navigate('/signin');
  };

  const handleQuickPrompt = (_prompt: string) => {
    navigate('/signin');
  };

  return (
    <div className="min-h-screen flex flex-col bg-white">
      {/* Header */}
      <LandingHeader />

      {/* Main content — centered vertically */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6">
        {/* Title */}
        <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-12 text-center">
          What can I do for you?
        </h2>

        {/* Chat input */}
        <div className="w-full max-w-2xl">
          <form onSubmit={handleSubmit} className="relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="Chat, visualize, or build..."
              rows={3}
              className="w-full px-4 py-3 pr-24 border border-gray-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder-gray-400 text-base"
            />
            <div className="absolute bottom-3 right-3 flex items-center space-x-2">
              <button
                type="button"
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Voice input"
                onClick={() => navigate('/signin')}
              >
                <Mic className="w-5 h-5" />
              </button>
              <button
                type="submit"
                className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                aria-label="Send message"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </form>

          {/* Suggestion chips */}
          <div className="flex flex-wrap gap-2 justify-center mt-6">
            {quickPrompts.map((prompt, index) => (
              <button
                key={index}
                onClick={() => handleQuickPrompt(prompt)}
                className="px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 rounded-lg border border-gray-200 text-sm font-medium transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 text-center text-sm text-gray-400 border-t border-gray-100">
        <p>NovoProtein AI — Molecular Visualization Platform</p>
      </footer>
    </div>
  );
};
