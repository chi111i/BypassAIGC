import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { Activity, RefreshCw, Clock, User, FileText, TrendingUp, BarChart3, Zap, History, Square } from 'lucide-react';
import { adminAPI } from '../api';

const SessionMonitor = ({ adminToken }) => {
  const [activeSessions, setActiveSessions] = useState([]);
  const [historySessions, setHistorySessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userSessions, setUserSessions] = useState([]);
  const [viewMode, setViewMode] = useState('active'); // 'active' or 'history'

  useEffect(() => {
    if (viewMode === 'active') {
      fetchActiveSessions();
      
      if (autoRefresh) {
        const interval = setInterval(fetchActiveSessions, 5000); // 每5秒刷新
        return () => clearInterval(interval);
      }
    } else if (viewMode === 'history') {
      fetchHistorySessions();
    }
  }, [autoRefresh, viewMode]);

  const handleStopSession = async (sessionId) => {
    if (!window.confirm('确定要强制停止该会话吗？')) {
      return;
    }
    const password = prompt("请输入管理员密码以确认停止操作:");
    if (!password) return;

    try {
      await adminAPI.stopSession(sessionId, password);
      toast.success('会话已停止');
      fetchActiveSessions();
    } catch (error) {
      toast.error('停止失败: ' + (error.response?.data?.detail || '未知错误'));
    }
  };

  const fetchActiveSessions = async () => {
    try {
      const response = await axios.get('/api/admin/sessions/active', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setActiveSessions(response.data);
    } catch (error) {
      if (error.response?.status !== 401) {
        console.error('获取活跃会话失败:', error);
      }
    }
  };

  const fetchHistorySessions = async () => {
    // 如果已经有数据，不显示全屏loading，提升体验
    if (historySessions.length === 0) {
      setLoading(true);
    }
    try {
      const response = await axios.get('/api/admin/sessions', {
        headers: { Authorization: `Bearer ${adminToken}` },
        params: { limit: 100 } // 获取最近100条
      });
      setHistorySessions(response.data);
    } catch (error) {
      if (error.response?.status !== 401) {
        toast.error('获取历史会话失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchUserSessions = async (userId, cardKey) => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/admin/users/${userId}/sessions`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setUserSessions(response.data);
      setSelectedUser({ id: userId, card_key: cardKey });
    } catch (error) {
      toast.error('获取用户会话历史失败');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'processing':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'queued':
        return 'bg-yellow-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'processing':
        return '处理中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      case 'queued':
        return '排队中';
      default:
        return status;
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}分${secs}秒`;
  };

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-purple-600" />
          <h3 className="text-xl font-semibold text-gray-800">会话监控</h3>
        </div>
        <div className="flex items-center gap-3">
          {/* 视图切换按钮 */}
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setViewMode('active')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'active' 
                  ? 'bg-white text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Activity className="w-4 h-4 inline mr-1" />
              实时会话
            </button>
            <button
              onClick={() => setViewMode('history')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'history' 
                  ? 'bg-white text-purple-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <History className="w-4 h-4 inline mr-1" />
              历史会话
            </button>
          </div>
          
          {viewMode === 'active' && (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              自动刷新
            </label>
          )}
          <button
            onClick={() => viewMode === 'active' ? fetchActiveSessions() : fetchHistorySessions()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <RefreshCw className="w-5 h-5" />
            刷新
          </button>
        </div>
      </div>

      {/* 统计卡片 */}
      {viewMode === 'active' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-2xl shadow-ios p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 mb-1">活跃会话</p>
                <p className="text-3xl font-bold text-gray-900 tracking-tight">{activeSessions.length}</p>
              </div>
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center">
                <Activity className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-ios p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 mb-1">处理中</p>
                <p className="text-3xl font-bold text-gray-900 tracking-tight">
                  {activeSessions.filter(s => s.status === 'processing').length}
                </p>
              </div>
              <div className="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-ios p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 mb-1">排队中</p>
                <p className="text-3xl font-bold text-gray-900 tracking-tight">
                  {activeSessions.filter(s => s.status === 'queued').length}
                </p>
              </div>
              <div className="w-12 h-12 bg-yellow-50 rounded-xl flex items-center justify-center">
                <Clock className="w-6 h-6 text-yellow-600" />
              </div>
            </div>
          </div>
        </div>
      )}
      
      {viewMode === 'history' && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-2xl shadow-ios p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 mb-1">已完成</p>
                <p className="text-3xl font-bold text-gray-900 tracking-tight">
                  {historySessions.filter(s => s.status === 'completed').length}
                </p>
              </div>
              <div className="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center">
                <Activity className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-ios p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 mb-1">处理中</p>
                <p className="text-3xl font-bold text-gray-900 tracking-tight">
                  {historySessions.filter(s => s.status === 'processing').length}
                </p>
              </div>
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-ios p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 mb-1">失败</p>
                <p className="text-3xl font-bold text-gray-900 tracking-tight">
                  {historySessions.filter(s => s.status === 'failed').length}
                </p>
              </div>
              <div className="w-12 h-12 bg-red-50 rounded-xl flex items-center justify-center">
                <Activity className="w-6 h-6 text-red-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-ios p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 mb-1">总会话数</p>
                <p className="text-3xl font-bold text-gray-900 tracking-tight">{historySessions.length}</p>
              </div>
              <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center">
                <BarChart3 className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 会话列表 */}
      <div className="bg-white rounded-2xl shadow-ios p-6">
        <h4 className="text-lg font-bold text-gray-900 mb-6">
          {viewMode === 'active' ? '实时会话' : '历史会话'}
        </h4>
        
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (viewMode === 'active' ? activeSessions : historySessions).length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <Activity className="w-8 h-8 text-gray-300" />
            </div>
            <p className="text-gray-500 font-medium">
              {viewMode === 'active' ? '当前没有活跃会话' : '暂无历史会话'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {(viewMode === 'active' ? activeSessions : historySessions).map((session) => (
              <div
                key={session.id || session.session_id}
                className="bg-white border border-gray-100 rounded-xl p-5 hover:shadow-md transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <button
                        onClick={() => fetchUserSessions(session.user_id, session.card_key)}
                        className="flex items-center gap-2 px-3 py-1 bg-purple-100 hover:bg-purple-200 text-purple-800 rounded-lg transition-colors text-sm font-medium"
                      >
                        <User className="w-4 h-4" />
                        {session.card_key}
                      </button>
                      <span className={`px-2 py-1 text-xs font-medium rounded ${
                        session.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                        session.status === 'queued' ? 'bg-yellow-100 text-yellow-800' :
                        session.status === 'completed' ? 'bg-green-100 text-green-800' :
                        session.status === 'failed' ? 'bg-red-100 text-red-800' :
                        session.status === 'stopped' ? 'bg-orange-100 text-orange-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {session.status === 'stopped' ? '已停止' : getStatusText(session.status)}
                      </span>
                      {(session.status === 'processing' || session.status === 'queued') && (
                        <button
                          onClick={() => handleStopSession(session.session_id || session.id)}
                          className="p-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="强制停止"
                        >
                          <Square className="w-4 h-4 fill-current" />
                        </button>
                      )}
                      {session.processing_mode && (
                        <span className="px-2 py-1 text-xs font-medium rounded bg-indigo-100 text-indigo-800">
                          {session.processing_mode === 'paper_polish' ? '论文润色' :
                           session.processing_mode === 'paper_polish_enhance' ? '论文润色+增强' :
                           session.processing_mode === 'emotion_polish' ? '感情文章润色' :
                           session.processing_mode}
                        </span>
                      )}
                      {session.original_char_count != null && (
                        <span className="px-2 py-1 text-xs font-medium rounded bg-gray-100 text-gray-700">
                          {session.original_char_count.toLocaleString()} 字符
                        </span>
                      )}
                      {viewMode === 'history' && session.polished_char_count != null && (
                        <span className="px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-700">
                          润色后 {session.polished_char_count.toLocaleString()} 字符
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* 进度条 */}
                {session.total_segments > 0 && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                      <span>处理进度</span>
                      <span>
                        {session.completed_segments || session.processed_segments || 0}/{session.total_segments} 段
                        {session.progress && ` (${session.progress}%)`}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-300 ${getStatusColor(session.status)}`}
                        style={{
                          width: `${session.progress || ((session.completed_segments || session.processed_segments || 0) / session.total_segments) * 100}%`
                        }}
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(session.created_at).toLocaleString('zh-CN')}
                  </span>
                  {session.processing_time && (
                    <span className="flex items-center gap-1">
                      <Zap className="w-3 h-3" />
                      耗时: {formatDuration(session.processing_time)}
                    </span>
                  )}
                  {session.completed_at && (
                    <span>完成: {new Date(session.completed_at).toLocaleString('zh-CN')}</span>
                  )}
                  {session.error_message && (
                    <span className="text-red-600">错误: {session.error_message}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 用户会话历史模态框 */}
      {selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <User className="w-6 h-6 text-purple-600" />
                <h3 className="text-xl font-bold text-gray-800">
                  用户会话历史: {selectedUser.card_key}
                </h3>
              </div>
              <button
                onClick={() => setSelectedUser(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <span className="text-2xl">&times;</span>
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : userSessions.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                该用户暂无会话记录
              </div>
            ) : (
              <div className="space-y-4">
                {userSessions.map((session) => (
                  <div key={session.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded ${
                          session.status === 'completed' ? 'bg-green-100 text-green-800' :
                          session.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                          session.status === 'failed' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {getStatusText(session.status)}
                        </span>
                        {session.processing_mode && (
                          <span className="px-2 py-1 text-xs font-medium rounded bg-indigo-100 text-indigo-800">
                            {session.processing_mode === 'paper_polish' ? '论文润色' :
                             session.processing_mode === 'paper_polish_enhance' ? '论文润色+增强' :
                             session.processing_mode === 'emotion_polish' ? '感情文章润色' :
                             session.processing_mode}
                          </span>
                        )}
                        <span className="text-xs text-gray-500">
                          ID: {session.session_id || session.id}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(session.created_at).toLocaleString('zh-CN')}
                      </div>
                    </div>

                    {/* 字符统计信息 */}
                    <div className="grid grid-cols-3 gap-3 mb-3">
                      {session.original_char_count != null && (
                        <div className="bg-blue-50 rounded-lg p-2">
                          <p className="text-xs text-blue-600 mb-1">原文字符</p>
                          <p className="text-lg font-bold text-blue-700">{session.original_char_count.toLocaleString()}</p>
                        </div>
                      )}
                      {session.polished_char_count != null && (
                        <div className="bg-green-50 rounded-lg p-2">
                          <p className="text-xs text-green-600 mb-1">润色字符</p>
                          <p className="text-lg font-bold text-green-700">{session.polished_char_count.toLocaleString()}</p>
                        </div>
                      )}
                      {session.enhanced_char_count != null && (
                        <div className="bg-purple-50 rounded-lg p-2">
                          <p className="text-xs text-purple-600 mb-1">增强字符</p>
                          <p className="text-lg font-bold text-purple-700">{session.enhanced_char_count.toLocaleString()}</p>
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-3">
                      <div className="bg-gray-50 rounded-lg p-3">
                        <p className="text-xs text-gray-500 mb-1">原文</p>
                        <p className="text-sm text-gray-700 line-clamp-3">
                          {session.original_text?.substring(0, 100)}
                          {session.original_text?.length > 100 ? '...' : ''}
                        </p>
                      </div>
                      {session.optimized_text && (
                        <div className="bg-gray-50 rounded-lg p-3">
                          <p className="text-xs text-gray-500 mb-1">优化后</p>
                          <p className="text-sm text-gray-700 line-clamp-3">
                            {session.optimized_text.substring(0, 100)}
                            {session.optimized_text.length > 100 ? '...' : ''}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* 进度统计 */}
                    {session.total_segments > 0 && (
                      <div className="mb-3">
                        <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                          <span>完成进度</span>
                          <span>{session.completed_segments || 0}/{session.total_segments} 段 ({session.progress || 0}%)</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full transition-all ${
                              session.status === 'completed' ? 'bg-green-500' : 'bg-blue-500'
                            }`}
                            style={{ width: `${session.progress || 0}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-6 text-xs text-gray-600">
                      <span className="flex items-center gap-1">
                        <FileText className="w-3 h-3" />
                        分段: {session.completed_segments || 0}/{session.total_segments || 0}
                      </span>
                      {session.processing_time && (
                        <span className="flex items-center gap-1">
                          <Zap className="w-3 h-3" />
                          耗时: {formatDuration(session.processing_time)}
                        </span>
                      )}
                      {session.completed_at && (
                        <span>完成: {new Date(session.completed_at).toLocaleString('zh-CN')}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionMonitor;
