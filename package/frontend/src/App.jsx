import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import WelcomePage from './pages/WelcomePage';
import WorkspacePage from './pages/WorkspacePage';
import SessionDetailPage from './pages/SessionDetailPage';
import AdminDashboard from './pages/AdminDashboard';
import WordFormatterPage from './pages/WordFormatterPage';
import SpecGeneratorPage from './pages/SpecGeneratorPage';
import ArticlePreprocessorPage from './pages/ArticlePreprocessorPage';
import FormatCheckerPage from './pages/FormatCheckerPage';
import './index.css';

const ProtectedRoute = ({ children }) => {
  const token = sessionStorage.getItem('authToken');
  
  if (!token) {
    return <Navigate to="/" replace />;
  }
  
  return children;
};

function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            duration: 3000,
            iconTheme: {
              primary: '#10B981',
              secondary: '#fff',
            },
          },
          error: {
            duration: 4000,
            iconTheme: {
              primary: '#EF4444',
              secondary: '#fff',
            },
          },
        }}
      />
      
      <Routes>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/admin" element={<AdminDashboard />} />
        
        <Route
          path="/workspace"
          element={
            <ProtectedRoute>
              <WorkspacePage />
            </ProtectedRoute>
          }
        />
        
        <Route
          path="/session/:sessionId"
          element={
            <ProtectedRoute>
              <SessionDetailPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/word-formatter"
          element={
            <ProtectedRoute>
              <WordFormatterPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/spec-generator"
          element={
            <ProtectedRoute>
              <SpecGeneratorPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/article-preprocessor"
          element={
            <ProtectedRoute>
              <ArticlePreprocessorPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/format-checker"
          element={
            <ProtectedRoute>
              <FormatCheckerPage />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
