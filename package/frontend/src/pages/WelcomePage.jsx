import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Shield, ArrowRight } from 'lucide-react';
import { authAPI, healthAPI } from '../api';

const WelcomePage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    healthAPI.checkModels().catch(() => {});
  }, []);

  const handleLogin = async () => {
    if (!username.trim() || !password.trim()) {
      toast.error('请输入用户名和密码');
      return;
    }

    setLoading(true);
    try {
      const response = await authAPI.login(username, password);
      const { access_token, display_name } = response.data;
      sessionStorage.setItem('authToken', access_token);
      sessionStorage.setItem('username', username);
      if (display_name) sessionStorage.setItem('displayName', display_name);
      toast.success('登录成功');
      navigate('/workspace');
    } catch (error) {
      toast.error(error.response?.data?.detail || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-blue-50 flex flex-col items-center justify-center p-4 sm:p-6 relative">
      <button
        onClick={() => navigate('/admin')}
        className="fixed top-6 left-6 px-4 py-2.5 bg-white/70 backdrop-blur-xl border border-white/20 shadow-lg hover:bg-white/80 text-gray-800 rounded-2xl transition-all active:scale-95 flex items-center gap-2 text-sm font-medium z-10"
      >
        <Shield className="w-4 h-4 text-blue-600" />
        管理后台
      </button>

      <div className="max-w-md w-full space-y-8">
        <div className="bg-white/80 backdrop-blur-2xl rounded-3xl shadow-2xl border border-white/20 p-8 space-y-8">
          <div className="text-center space-y-4">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-blue-600 rounded-[22px] shadow-lg mb-2">
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-black tracking-tight">
                AI 学术写作助手
              </h1>
              <p className="text-gray-500 text-sm mt-1">
                专业论文润色 · 智能语言优化
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-500 ml-1">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && password.trim() && handleLogin()}
                placeholder="请输入用户名"
                autoComplete="username"
                className="w-full px-4 py-3.5 bg-white/50 backdrop-blur-sm rounded-xl border border-gray-200/50 focus:bg-white/70 focus:ring-2 focus:ring-blue-600/30 focus:border-blue-600/50 transition-all text-black placeholder-gray-400 outline-none text-[17px]"
              />
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-500 ml-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                placeholder="请输入密码"
                autoComplete="current-password"
                className="w-full px-4 py-3.5 bg-white/50 backdrop-blur-sm rounded-xl border border-gray-200/50 focus:bg-white/70 focus:ring-2 focus:ring-blue-600/30 focus:border-blue-600/50 transition-all text-black placeholder-gray-400 outline-none text-[17px]"
              />
            </div>

            <button
              onClick={handleLogin}
              disabled={loading || !username.trim() || !password.trim()}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3.5 px-6 rounded-xl transition-all active:scale-95 flex items-center justify-center gap-2 text-[17px] shadow-lg hover:shadow-xl"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  登录中...
                </>
              ) : (
                <>
                  登录
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </div>

          <div className="text-center pt-2">
            <p className="text-xs text-gray-500">
              使用本系统即表示您同意遵守学术诚信规范
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WelcomePage;
