import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Atom } from 'lucide-react';

export const LandingHeader: React.FC = () => {
  const navigate = useNavigate();

  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200/50 px-6 py-4 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center space-x-2">
        <Atom className="w-8 h-8 text-blue-600" />
        <h1 className="text-xl font-bold text-gray-900">NovoProtein AI</h1>
      </div>
      
      <nav className="flex items-center space-x-6">
        <Link 
          to="/pricing" 
          className="text-gray-700 hover:text-gray-900 transition-colors text-sm font-medium"
        >
          Pricing
        </Link>
        <Link 
          to="/signin" 
          className="text-gray-700 hover:text-gray-900 transition-colors text-sm font-medium"
        >
          Sign in
        </Link>
        <button
          onClick={() => navigate('/signup')}
          className="bg-black text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
        >
          Get started
        </button>
      </nav>
    </header>
  );
};

