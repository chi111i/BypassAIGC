import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Shield, ArrowRight, AlertCircle } from 'lucide-react';
import axios from 'axios';
import { healthAPI } from '../api';

const WelcomePage = () => {
  const [cardKey, setCardKey] = useState('');
  const [showWarning, setShowWarning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState(null);
  const navigate = useNavigate();

  // 检查 API 可用性 - 改为静默检查，避免启动时报错
  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        const response = await healthAPI.checkModels();
        const data = response.data;
        setApiStatus(data);
        
        // 只在所有模型都不可用时才显示警告
        if (data.overall_status === 'degraded') {
          const unavailableModels = Object.entries(data.models)
            .filter(([_, model]) => model.status === 'unavailable')
            .map(([name, _]) => name);
          
          // 只在所有模型都不可用时才显示错误
          const allUnavailable = unavailableModels.length === Object.keys(data.models).length;
          if (allUnavailable) {
            console.warn('所有 AI 模型配置检查未通过，请联系管理员检查配置。');
          }
        }
      } catch (error) {
        // 静默处理错误，避免影响用户体验
        console.error('API health check failed:', error);
      }
    };

    checkApiHealth();
  }, []);

  const handleContinue = async () => {
    if (!cardKey.trim()) {
      toast.error('请输入卡密');
      return;
    }

    // 检查 API 状态
    if (apiStatus && apiStatus.overall_status === 'degraded') {
      const allUnavailable = Object.values(apiStatus.models).every(
        model => model.status === 'unavailable'
      );
      
      if (allUnavailable) {
        toast.error('所有 AI 模型当前不可用，无法使用系统。请联系管理员。');
        return;
      } else {
        toast.warning('部分 AI 模型不可用，系统功能可能受限。');
      }
    }
    
    // 验证卡密
    setLoading(true);
    try {
      const response = await axios.post('/api/admin/verify-card-key', {
        card_key: cardKey
      });
      
      if (response.data.valid) {
        setShowWarning(true);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || '卡密验证失败，请检查卡密是否正确');
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = () => {
    localStorage.setItem('cardKey', cardKey);
    navigate('/workspace');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex flex-col items-center justify-center p-4 sm:p-6 relative">
      {/* Admin button in top-left with Apple frosted glass style */}
      <button
        onClick={() => navigate('/admin')}
        className="fixed top-6 left-6 px-4 py-2.5 bg-white/70 backdrop-blur-xl border border-white/20 shadow-lg hover:bg-white/80 text-gray-800 rounded-2xl transition-all active:scale-95 flex items-center gap-2 text-sm font-medium z-10"
      >
        <Shield className="w-4 h-4 text-blue-600" />
        管理后台
      </button>

      <div className="max-w-md w-full space-y-8">
        {!showWarning ? (
          <div className="bg-white/80 backdrop-blur-2xl rounded-3xl shadow-2xl border border-white/20 p-8 space-y-8">
            {/* Logo/标题区域 */}
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-ios-blue rounded-[22px] shadow-lg mb-2">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-black tracking-tight">
                  AI 学术写作助手
                </h1>
                <p className="text-ios-gray text-sm mt-1">
                  专业论文润色 · 智能语言优化
                </p>
              </div>
            </div>

            {/* 输入区域 */}
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-ios-gray ml-1">
                  访问卡密
                </label>
                <input
                  type="text"
                  value={cardKey}
                  onChange={(e) => setCardKey(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !loading && cardKey.trim() && handleContinue()}
                  placeholder="请输入卡密"
                  className="w-full px-4 py-3.5 bg-white/50 backdrop-blur-sm rounded-xl border border-gray-200/50 focus:bg-white/70 focus:ring-2 focus:ring-ios-blue/30 focus:border-ios-blue/50 transition-all text-black placeholder-gray-400 outline-none text-[17px]"
                />
              </div>

              <button
                onClick={handleContinue}
                disabled={loading || !cardKey.trim()}
                className="w-full bg-ios-blue hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3.5 px-6 rounded-xl transition-all active:scale-95 flex items-center justify-center gap-2 text-[17px] shadow-lg hover:shadow-xl"
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    验证中...
                  </>
                ) : (
                  <>
                    开始使用
                  </>
                )}
              </button>
            </div>

            {/* 底部提示 */}
            <div className="text-center pt-2">
              <p className="text-xs text-ios-gray">
                使用本系统即表示您同意遵守学术诚信规范
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-white/80 backdrop-blur-2xl rounded-3xl shadow-2xl border border-white/20 p-8 space-y-6">
            {/* 图标和标题 */}
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-ios-orange rounded-[18px] shadow-md mb-4">
                <Shield className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-xl font-bold text-black tracking-tight mb-1">
                学术诚信承诺
              </h2>
              <p className="text-sm text-ios-gray">请仔细阅读以下条款</p>
            </div>

            {/* 条款内容 */}
            <div className="bg-gray-50 rounded-xl p-5 space-y-4">
              <div className="space-y-3 text-black text-[15px] leading-relaxed">
                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-5 h-5 bg-ios-orange text-white rounded-full flex items-center justify-center text-xs font-bold mt-0.5">1</span>
                  <p>本系统仅作为语言润色工具，不应替代原创研究与学术思考</p>
                </div>
                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-5 h-5 bg-ios-orange text-white rounded-full flex items-center justify-center text-xs font-bold mt-0.5">2</span>
                  <p>论文的核心观点、研究方法、数据分析必须为您的原创工作</p>
                </div>
                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-5 h-5 bg-ios-orange text-white rounded-full flex items-center justify-center text-xs font-bold mt-0.5">3</span>
                  <p>您需审核所有优化内容，并对最终提交的论文负全部责任</p>
                </div>
                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-5 h-5 bg-ios-orange text-white rounded-full flex items-center justify-center text-xs font-bold mt-0.5">4</span>
                  <p>根据机构规定，您可能需要声明使用了 AI 辅助工具</p>
                </div>
              </div>
            </div>

            {/* 警告提示 */}
            <div className="bg-red-50 rounded-xl p-4">
              <div className="flex gap-3 items-start">
                <AlertCircle className="w-5 h-5 text-ios-red flex-shrink-0 mt-0.5" />
                <p className="text-ios-red text-sm font-medium">
                  学术不端行为可能导致严重后果，包括论文撤稿、学位取消等
                </p>
              </div>
            </div>

            {/* 按钮组 */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <button
                onClick={() => setShowWarning(false)}
                className="bg-gray-100 hover:bg-gray-200 text-black font-medium py-3.5 px-6 rounded-xl transition-all active:scale-[0.98] text-[17px]"
              >
                返回
              </button>
              <button
                onClick={handleAccept}
                className="bg-ios-green hover:bg-green-600 text-white font-semibold py-3.5 px-6 rounded-xl transition-all active:scale-[0.98] text-[17px]"
              >
                同意并继续
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WelcomePage;
