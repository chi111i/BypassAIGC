import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { 
  FileText, History, LogOut, Play, 
  Users, Clock, AlertCircle, CheckCircle, Trash2, Info 
} from 'lucide-react';
import { optimizationAPI } from '../api';

const WorkspacePage = () => {
  const [text, setText] = useState('');
  const [processingMode, setProcessingMode] = useState('paper_polish_enhance');
  const [sessions, setSessions] = useState([]);
  const [queueStatus, setQueueStatus] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadSessions();
    loadQueueStatus();
    
    // 降低队列状态更新频率到10秒，减少服务器负载
    const interval = setInterval(loadQueueStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // 如果有活跃会话,每3秒更新进度（从2秒增加到3秒，减少请求频率）
    if (activeSession) {
      const interval = setInterval(() => {
        updateSessionProgress(activeSession);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [activeSession]);

  const loadSessions = async () => {
    try {
      setIsLoadingSessions(true);
      const response = await optimizationAPI.listSessions();
      setSessions(response.data);
      
      // 查找正在处理的会话
      const processing = response.data.find(
        s => s.status === 'processing' || s.status === 'queued'
      );
      if (processing) {
        setActiveSession(processing.session_id);
      }
    } catch (error) {
      console.error('加载会话失败:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  };

  const loadQueueStatus = async () => {
    try {
      const response = await optimizationAPI.getQueueStatus(activeSession);
      setQueueStatus(response.data);
    } catch (error) {
      console.error('加载队列状态失败:', error);
    }
  };

  const updateSessionProgress = async (sessionId) => {
    try {
      const response = await optimizationAPI.getSessionProgress(sessionId);
      const progress = response.data;
      
      // 更新会话列表中的进度
      setSessions(prev =>
        prev.map(s =>
          s.session_id === sessionId
            ? { ...s, ...progress }
            : s
        )
      );
      
      // 如果会话完成,刷新列表
      if (progress.status === 'completed' || progress.status === 'failed') {
        setActiveSession(null);
        loadSessions();
        
        if (progress.status === 'completed') {
          toast.success('优化完成!');
        } else {
          toast.error(`优化失败: ${progress.error_message}`);
        }
      }
    } catch (error) {
      console.error('更新进度失败:', error);
    }
  };

  const handleStartOptimization = async () => {
    if (!text.trim()) {
      toast.error('请输入要优化的文本');
      return;
    }

    if (isSubmitting) {
      return;
    }

    try {
      setIsSubmitting(true);
      const response = await optimizationAPI.startOptimization({
        original_text: text,
        processing_mode: processingMode,
      });
      
      setActiveSession(response.data.session_id);
      toast.success('优化任务已启动');
      setText('');
      loadSessions();
    } catch (error) {
      toast.error('启动优化失败: ' + error.response?.data?.detail);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('cardKey');
    navigate('/');
  };

  const handleDeleteSession = async (event, session) => {
    event.stopPropagation();

    const confirmDelete = window.confirm('确认删除该会话及其结果吗?');
    if (!confirmDelete) {
      return;
    }

    try {
      await optimizationAPI.deleteSession(session.session_id);
      if (activeSession === session.session_id) {
        setActiveSession(null);
      }
      toast.success('会话已删除');
      await loadSessions();
    } catch (error) {
      console.error('删除会话失败:', error);
      toast.error(error.response?.data?.detail || '删除会话失败');
    }
  };

  const handleViewSession = (sessionId) => {
    navigate(`/session/${sessionId}`);
  };

  const handleRetrySegment = async (event, session) => {
    event.stopPropagation();

    if (session.status !== 'failed') {
      return;
    }

    const confirmRetry = window.confirm('检测到会话执行失败。是否继续处理未完成的段落?');
    if (!confirmRetry) {
      return;
    }

    try {
      const response = await optimizationAPI.retryFailedSegments(session.session_id);
      setActiveSession(session.session_id);
      toast.success(response.data?.message || '已重新继续处理未完成段落');
      await loadSessions();
    } catch (error) {
      console.error('重试失败:', error);
      toast.error(error.response?.data?.detail || '重试失败，请稍后再试');
    }
  };

  const renderStatusAction = (session) => {
    if (session.status === 'failed') {
      return (
        <button
          onClick={(event) => handleRetrySegment(event, session)}
          className="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200"
        >
          继续处理
        </button>
      );
    }
    return null;
  };


  return (
    <div className="min-h-screen bg-ios-background">
      {/* 顶部导航栏 - iOS Glass Style */}
      <nav className="bg-white/80 backdrop-blur-xl border-b border-ios-separator sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-[52px]">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-ios-blue rounded-lg flex items-center justify-center">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-[17px] font-semibold text-black tracking-tight">
                AI 论文润色增强
              </h1>
            </div>
            
            <div className="flex items-center gap-4">
              {/* 队列状态 */}
              {queueStatus && (
                <div className="flex items-center gap-3 text-[13px]">
                  <div className="flex items-center gap-1.5 bg-gray-100 px-2 py-1 rounded-md">
                    <Users className="w-3.5 h-3.5 text-ios-gray" />
                    <span className="text-ios-gray font-medium">
                      {queueStatus.current_users}/{queueStatus.max_users}
                    </span>
                  </div>
                  {queueStatus.queue_length > 0 && (
                    <div className="flex items-center gap-1.5 bg-orange-50 px-2 py-1 rounded-md">
                      <Clock className="w-3.5 h-3.5 text-ios-orange" />
                      <span className="text-ios-orange font-medium">
                        {queueStatus.queue_length} 排队
                      </span>
                    </div>
                  )}
                </div>
              )}
              
              <button
                onClick={handleLogout}
                className="text-ios-red text-[17px] hover:opacity-70 transition-opacity font-normal"
              >
                退出
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧 - 输入区域 */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* 说明卡片 */}
            <div className="bg-white rounded-2xl shadow-ios overflow-hidden">
              <div className="p-4 flex items-start gap-3 bg-blue-50/50">
                <Info className="w-5 h-5 text-ios-blue flex-shrink-0 mt-0.5" />
                <div className="text-[15px] text-black">
                  <p className="font-semibold mb-1 text-ios-blue">当前模式说明</p>
                  <p className="text-gray-700 leading-relaxed">
                    {processingMode === 'paper_polish' && '仅进行论文润色，提升文本的学术性和表达质量。'}
                    {processingMode === 'paper_polish_enhance' && '先进行论文润色，然后自动进行原创性增强，两阶段处理。'}
                    {processingMode === 'emotion_polish' && '专为感情文章设计，生成更自然、更具人性化的表达。'}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-ios p-5">
              <div className="h-[40px] flex items-center mb-2">
                <h2 className="text-[20px] font-bold text-black tracking-tight pl-1">
                  新建任务
                </h2>
              </div>
              
              {/* 处理模式选择 - iOS Segmented Control Style */}
              <div className="mb-5">
                <label className="block text-[13px] font-medium text-ios-gray mb-2 ml-1 uppercase tracking-wide">
                  选择模式
                </label>
                <div className="space-y-3">
                  {[
                    { id: 'paper_polish', title: '论文润色', desc: '提升学术表达质量' },
                    { id: 'paper_polish_enhance', title: '润色 + 增强', desc: '提升原创性与学术水平' },
                    { id: 'emotion_polish', title: '感情文章润色', desc: '自然、人性化表达' }
                  ].map((mode) => (
                    <label
                      key={mode.id}
                      className={`flex items-center p-3.5 rounded-xl cursor-pointer transition-all border ${
                        processingMode === mode.id
                          ? 'bg-blue-50 border-ios-blue ring-1 ring-ios-blue/20'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="processingMode"
                        value={mode.id}
                        checked={processingMode === mode.id}
                        onChange={(e) => setProcessingMode(e.target.value)}
                        className="mr-3 w-5 h-5 text-ios-blue focus:ring-ios-blue border-gray-300"
                      />
                      <div>
                        <div className={`font-semibold text-[15px] ${processingMode === mode.id ? 'text-ios-blue' : 'text-black'}`}>
                          {mode.title}
                        </div>
                        <div className="text-[13px] text-ios-gray mt-0.5">
                          {mode.desc}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
              
              <div className="relative">
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="在此粘贴您的内容..."
                  className="w-full h-64 px-4 py-3 bg-gray-50 rounded-xl focus:bg-white focus:ring-2 focus:ring-ios-blue/20 transition-all text-[16px] leading-relaxed text-black placeholder-gray-400 border-none outline-none resize-none"
                />
                <div className="absolute bottom-3 right-3 text-[12px] text-ios-gray bg-white/80 px-2 py-1 rounded-md backdrop-blur-sm">
                  {text.length} 字
                </div>
              </div>
              
              <div className="mt-5 flex justify-end">
                <button
                  onClick={handleStartOptimization}
                  disabled={!text.trim() || activeSession || isSubmitting}
                  className="flex items-center gap-2 bg-ios-blue hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3 px-8 rounded-xl transition-all active:scale-[0.98] shadow-sm text-[17px]"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      提交中...
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 fill-current" />
                      开始优化
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* 活跃会话进度 */}
            {activeSession && sessions.find(s => s.session_id === activeSession) && (
              <div className="bg-white rounded-2xl shadow-ios p-5 border border-blue-100">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-[17px] font-bold text-black flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-ios-blue animate-pulse" />
                    正在处理
                  </h2>
                  <span className="text-[13px] font-medium px-2 py-1 bg-blue-50 text-ios-blue rounded-md">
                    进行中
                  </span>
                </div>
                
                {(() => {
                  const session = sessions.find(s => s.session_id === activeSession);
                  const getStageName = (stage) => {
                    if (stage === 'polish') return '论文润色';
                    if (stage === 'emotion_polish') return '感情文章润色';
                    if (stage === 'enhance') return '原创性增强';
                    return stage;
                  };
                  return (
                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-[13px] mb-2 font-medium">
                          <span className="text-ios-gray">
                            当前阶段: <span className="text-black">{getStageName(session.current_stage)}</span>
                          </span>
                          <span className="text-ios-blue">
                            {session.progress.toFixed(1)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-ios-blue h-2 rounded-full transition-all duration-500 ease-out shadow-[0_0_10px_rgba(0,122,255,0.3)]"
                            style={{ width: `${session.progress}%` }}
                          />
                        </div>
                      </div>
                      
                      <div className="flex justify-between items-center text-[13px]">
                        <span className="text-ios-gray">
                          进度: <span className="font-medium text-black">{session.current_position + 1}</span> / {session.total_segments} 段
                        </span>
                        
                        {session.status === 'queued' && queueStatus?.your_position && (
                          <div className="flex items-center gap-1.5 text-ios-orange">
                            <Clock className="w-3.5 h-3.5" />
                            <span>
                              排队第 {queueStatus.your_position} 位
                              (~{Math.ceil(queueStatus.estimated_wait_time / 60)}分)
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          {/* 右侧 - 历史会话 */}
          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-ios overflow-hidden flex flex-col h-[calc(100vh-140px)] sticky top-24">
              <div className="p-5 border-b border-gray-100 bg-white/50 backdrop-blur-sm z-10 h-[72px] flex items-center">
                <div className="flex items-center gap-2">
                  <History className="w-5 h-5 text-ios-gray" />
                  <h2 className="text-[20px] font-bold text-black tracking-tight">
                    历史记录
                  </h2>
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar h-full">
                {isLoadingSessions ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-6 h-6 border-2 border-ios-gray/30 border-t-ios-gray rounded-full animate-spin" />
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="text-center py-12 space-y-2">
                    <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mx-auto text-gray-300">
                      <History className="w-6 h-6" />
                    </div>
                    <p className="text-ios-gray text-sm">
                      暂无会话记录
                    </p>
                  </div>
                ) : (
                  sessions.map((session) => (
                    <div
                      key={session.id}
                      onClick={() => handleViewSession(session.session_id)}
                      className="group p-3 rounded-xl hover:bg-gray-50 transition-all cursor-pointer border border-transparent hover:border-gray-100 relative"
                    >
                      <div className="flex items-start justify-between mb-1.5 gap-2">
                        <div className="flex items-center gap-1.5">
                          {session.status === 'completed' && (
                            <CheckCircle className="w-4 h-4 text-ios-green" />
                          )}
                          {session.status === 'processing' && (
                            <div className="w-4 h-4 border-2 border-ios-blue border-t-transparent rounded-full animate-spin" />
                          )}
                          {session.status === 'failed' && (
                            <AlertCircle className="w-4 h-4 text-ios-red" />
                          )}
                          {session.status === 'stopped' && (
                            <AlertCircle className="w-4 h-4 text-orange-500" />
                          )}
                          <span className={`text-[13px] font-medium ${
                            session.status === 'completed' ? 'text-black' :
                            session.status === 'processing' ? 'text-ios-blue' :
                            session.status === 'failed' ? 'text-ios-red' :
                            session.status === 'stopped' ? 'text-orange-600' : 'text-ios-gray'
                          }`}>
                            {session.status === 'completed' && '已完成'}
                            {session.status === 'processing' && '处理中'}
                            {session.status === 'queued' && '排队中'}
                            {session.status === 'failed' && '失败'}
                            {session.status === 'stopped' && '已停止'}
                          </span>
                        </div>
                        
                        <span className="text-[11px] text-ios-gray/70 font-medium">
                          {new Date(session.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      
                      <p className="text-[13px] text-ios-gray leading-snug line-clamp-2 mb-2 pr-6">
                        {session.original_text?.substring(0, 100)}...
                      </p>
                      
                      {session.status === 'processing' && (
                        <div className="w-full bg-gray-100 rounded-full h-1 mb-1">
                          <div
                            className="bg-ios-blue h-1 rounded-full"
                            style={{ width: `${session.progress}%` }}
                          />
                        </div>
                      )}

                      {/* 操作按钮 - 悬停显示或移动端常显 */}
                      <div className="flex items-center justify-between mt-1">
                         {renderStatusAction(session)}
                         <button
                            onClick={(event) => handleDeleteSession(event, session)}
                            className="p-1.5 text-gray-300 hover:text-ios-red hover:bg-red-50 rounded-lg transition-colors ml-auto"
                            title="删除会话"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                      </div>

                      {session.status === 'failed' && session.current_position < session.total_segments && (
                         <div className="text-[11px] text-ios-red bg-red-50 px-2 py-1 rounded mt-1">
                           {session.error_message ? '发生错误' : '网络超时'}
                         </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkspacePage;
