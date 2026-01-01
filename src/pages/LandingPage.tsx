import React from 'react';
import { LandingHeader } from '../components/LandingHeader';
import { ChatPanel } from '../components/ChatPanel';

export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-blue-50 via-purple-50 to-pink-50">
      <LandingHeader />
      
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-8">
        {/* Hero Section */}
        <div className="text-center mb-12 max-w-3xl">
          <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-4">
            Build something powerful
          </h1>
          <p className="text-xl text-gray-600">
            Create protein designs and visualizations by chatting with AI
          </p>
        </div>

        {/* Chat Interface - Centered and Prominent */}
        <div className="w-full max-w-4xl">
          <ChatPanel />
        </div>
      </div>
    </div>
  );
};

