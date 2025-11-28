import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  ArrowLeft, Download, FileText, GitCompare,
  CheckCircle, AlertCircle, Shield, Square
} from 'lucide-react';
import { optimizationAPI } from '../api';

const SessionDetailPage = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [segments, setSegments] = useState([]);
  const [changes, setChanges] = useState([]);
  const [activeTab, setActiveTab] = useState('result');
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportFormat, setExportFormat] = useState('txt');

  useEffect(() => {
    loadSessionDetail();
    loadChanges();

    // 建立 SSE 连接
    const streamUrl = optimizationAPI.getStreamUrl(sessionId);
    const eventSource = new EventSource(streamUrl);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'content') {
          handleStreamUpdate(data);
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE Error:', error);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [sessionId]);

  const handleStreamUpdate = (data) => {
    setSegments(prevSegments => {
      const newSegments = [...prevSegments];
      const segmentIndex = data.segment_index;
      
      // 确保段落存在
      if (!newSegments[segmentIndex]) {
        // 如果段落不存在（这不应该发生，除非初始化延迟），可以尝试重新加载或创建一个占位符
        // 这里简单地忽略或记录错误
        console.warn(`Segment ${segmentIndex} not found for update`);
        return prevSegments;
      }

      const segment = { ...newSegments[segmentIndex] };
      
      // 更新内容
      if (data.stage === 'polish' || data.stage === 'emotion_polish') {
        segment.polished_text = (segment.polished_text || "") + data.content;
      } else if (data.stage === 'enhance') {
        segment.enhanced_text = (segment.enhanced_text || "") + data.content;
      }
      
      // 标记为处理中（如果尚未标记）
      if (segment.status !== 'processing') {
          segment.status = 'processing';
      }

      newSegments[segmentIndex] = segment;
      return newSegments;
    });

    // 同时更新会话状态为 processing
    setSession(prev => {
        if (prev && prev.status !== 'processing') {
            return { ...prev, status: 'processing' };
        }
        return prev;
    });
  };

  const loadSessionDetail = async () => {
    try {
      const response = await optimizationAPI.getSessionDetail(sessionId);
      setSession(response.data);
      setSegments(response.data.segments || []);
    } catch (error) {
      toast.error('加载会话详情失败');
      navigate('/workspace');
    }
  };

  const loadChanges = async () => {
    try {
      const response = await optimizationAPI.getSessionChanges(sessionId);
      setChanges(response.data);
    } catch (error) {
      console.error('加载变更记录失败:', error);
    }
  };

  const handleExport = async (acknowledged) => {
    if (!acknowledged) {
      toast.error('请确认学术诚信承诺');
      return;
    }

    try {
      const response = await optimizationAPI.exportSession(sessionId, {
        session_id: sessionId,
        acknowledge_academic_integrity: true,
        export_format: exportFormat,
      });

      // 下载文件
      const blob = new Blob([response.data.content], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = response.data.filename;
      a.click();
      window.URL.revokeObjectURL(url);

      toast.success('导出成功');
      setShowExportModal(false);
    } catch (error) {
      toast.error('导出失败: ' + error.response?.data?.detail);
    }
  };

  const handleStop = async () => {
    if (!window.confirm('确定要停止当前的优化任务吗？已完成的段落将保留。')) {
      return;
    }

    try {
      await optimizationAPI.stopSession(sessionId);
      toast.success('任务已停止');
      loadSessionDetail(); // 刷新状态
    } catch (error) {
      toast.error('停止任务失败: ' + (error.response?.data?.detail || '未知错误'));
    }
  };

  const getFinalText = () => {
    return segments
      .sort((a, b) => a.segment_index - b.segment_index)
      .map(seg => seg.enhanced_text || seg.polished_text || seg.original_text)
      .join('\n\n');
  };

  const getOriginalText = () => {
    return segments
      .sort((a, b) => a.segment_index - b.segment_index)
      .map(seg => seg.original_text)
      .join('\n\n');
  };

  if (!session) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ios-background">
      {/* 顶部导航 - iOS Glass Style */}
      <nav className="bg-white/80 backdrop-blur-xl border-b border-ios-separator sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-[52px]">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/workspace')}
                className="flex items-center gap-1 text-ios-blue hover:opacity-70 transition-opacity -ml-2 px-2 py-1 rounded-lg"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="text-[17px] font-normal">返回</span>
              </button>
              
              <div className="h-6 w-[1px] bg-gray-300 mx-1" />

              <div className="flex items-center gap-2">
                <h1 className="text-[17px] font-semibold text-black">
                  会话详情
                </h1>
                <span className="text-[13px] text-ios-gray font-normal">
                  {new Date(session.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {session.status === 'completed' && (
                <>
                  <div className="hidden sm:flex items-center gap-1.5 text-ios-green bg-green-50 px-2 py-1 rounded-md">
                    <CheckCircle className="w-4 h-4" />
                    <span className="text-[13px] font-medium">已完成</span>
                  </div>
                  
                  <button
                    onClick={() => setShowExportModal(true)}
                    className="flex items-center gap-1.5 bg-ios-blue hover:bg-blue-600 text-white font-semibold py-1.5 px-4 rounded-full transition-all active:scale-[0.98] text-[15px]"
                  >
                    <Download className="w-4 h-4" />
                    导出
                  </button>
                </>
              )}
              
              {session.status === 'failed' && (
                <div className="flex items-center gap-1.5 text-ios-red bg-red-50 px-2 py-1 rounded-md">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-[13px] font-medium">处理失败</span>
                </div>
              )}

              {session.status === 'stopped' && (
                <div className="flex items-center gap-1.5 text-orange-600 bg-orange-50 px-2 py-1 rounded-md">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-[13px] font-medium">已停止</span>
                </div>
              )}

              {(session.status === 'processing' || session.status === 'queued') && (
                <button
                  onClick={handleStop}
                  className="flex items-center gap-1.5 bg-red-50 hover:bg-red-100 text-red-600 font-semibold py-1.5 px-4 rounded-full transition-all active:scale-[0.98] text-[15px]"
                >
                  <Square className="w-4 h-4 fill-current" />
                  停止
                </button>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        
        {/* iOS Segmented Control */}
        <div className="flex justify-center mb-6">
          <div className="bg-gray-200/80 p-1 rounded-xl inline-flex w-full max-w-md">
            <button
              onClick={() => setActiveTab('result')}
              className={`flex-1 py-1.5 px-4 rounded-[9px] text-[13px] font-medium transition-all duration-200 ${
                activeTab === 'result'
                  ? 'bg-white text-black shadow-sm'
                  : 'text-gray-600 hover:text-black'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <FileText className="w-4 h-4" />
                优化结果
              </div>
            </button>
            <button
              onClick={() => setActiveTab('compare')}
              className={`flex-1 py-1.5 px-4 rounded-[9px] text-[13px] font-medium transition-all duration-200 ${
                activeTab === 'compare'
                  ? 'bg-white text-black shadow-sm'
                  : 'text-gray-600 hover:text-black'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <GitCompare className="w-4 h-4" />
                变更对照
              </div>
            </button>
          </div>
        </div>

        {/* 内容区域 */}
        <div className="space-y-6">
          {activeTab === 'result' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-2xl shadow-ios overflow-hidden flex flex-col h-[calc(100vh-180px)]">
                <div className="p-3 bg-gray-50 border-b border-gray-100 flex justify-between items-center">
                  <h3 className="text-[15px] font-semibold text-black ml-2">
                    优化后的文本
                  </h3>
                  <button
                    className="text-ios-blue text-[13px] px-3 py-1 hover:bg-blue-50 rounded-md transition-colors"
                    onClick={() => {
                        navigator.clipboard.writeText(getFinalText());
                        toast.success('已复制到剪贴板');
                    }}
                  >
                    复制全文
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-5 bg-white custom-scrollbar">
                  <pre className="whitespace-pre-wrap font-sans text-[16px] text-black leading-relaxed">
                    {getFinalText()}
                  </pre>
                </div>
              </div>
              
              <div className="bg-white rounded-2xl shadow-ios overflow-hidden flex flex-col h-[calc(100vh-180px)]">
                <div className="p-3 bg-gray-50 border-b border-gray-100">
                  <h3 className="text-[15px] font-semibold text-gray-500 ml-2">
                    原始文本
                  </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-5 bg-gray-50/50 custom-scrollbar">
                  <pre className="whitespace-pre-wrap font-sans text-[15px] text-gray-500 leading-relaxed">
                    {getOriginalText()}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'compare' && (
            <div className="bg-white rounded-2xl shadow-ios p-6 min-h-[calc(100vh-180px)]">
              <h3 className="text-[20px] font-bold text-black mb-6 tracking-tight">
                变更对照记录
              </h3>
              
              {changes.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4 text-gray-300">
                    <GitCompare className="w-8 h-8" />
                  </div>
                  <p className="text-ios-gray">
                    暂无变更记录
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {changes.map((change, index) => (
                    <div key={change.id} className="border border-gray-100 rounded-xl p-5 hover:shadow-md transition-shadow">
                      <div className="flex items-center gap-2 mb-4">
                        <span className="bg-blue-50 text-ios-blue text-[11px] font-bold px-2 py-1 rounded-md uppercase tracking-wide">
                          段落 {change.segment_index + 1}
                        </span>
                        <span className="bg-purple-50 text-ios-purple text-[11px] font-bold px-2 py-1 rounded-md uppercase tracking-wide">
                          {change.stage === 'polish' ? '润色' :
                           change.stage === 'emotion_polish' ? '感情润色' :
                           '增强'}
                        </span>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                          <h4 className="text-[13px] font-semibold text-ios-gray mb-2 uppercase tracking-wide">
                            修改前
                          </h4>
                          <div className="bg-red-50/50 border border-red-100 rounded-lg p-4 text-[15px] text-gray-800 leading-relaxed">
                            {change.before_text}
                          </div>
                        </div>
                        
                        <div>
                          <h4 className="text-[13px] font-semibold text-ios-gray mb-2 uppercase tracking-wide">
                            修改后
                          </h4>
                          <div className="bg-green-50/50 border border-green-100 rounded-lg p-4 text-[15px] text-black leading-relaxed font-medium">
                            {change.after_text}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 导出确认模态框 - iOS Alert Style */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 z-[100]">
          <div className="bg-white rounded-[14px] shadow-2xl max-w-sm w-full overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 text-center">
              <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="w-6 h-6 text-ios-orange" />
              </div>
              <h2 className="text-[17px] font-semibold text-black mb-2">
                学术诚信确认
              </h2>
              <p className="text-[13px] text-black mb-4">
                请确认您已审核所有内容，并对最终论文负责。
              </p>

              <div className="bg-gray-50 rounded-lg p-3 text-left mb-4">
                <ul className="space-y-1.5 text-[12px] text-gray-600">
                  <li className="flex items-start gap-2">
                    <span className="text-ios-green font-bold">✓</span> 符合学术规范
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-ios-green font-bold">✓</span> 核心观点原创
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-ios-green font-bold">✓</span> 承担全部责任
                  </li>
                </ul>
              </div>

              <div className="mb-4">
                <label className="block text-[12px] font-medium text-ios-gray mb-1.5 text-left">
                  导出格式
                </label>
                <select
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-100 rounded-lg text-[15px] border-none focus:ring-0"
                >
                  <option value="txt">文本文件 (.txt)</option>
                  <option value="docx" disabled>Word文档 (.docx) - 即将支持</option>
                  <option value="pdf" disabled>PDF文件 (.pdf) - 即将支持</option>
                </select>
              </div>
            </div>

            <div className="flex border-t border-gray-200 divide-x divide-gray-200">
              <button
                onClick={() => setShowExportModal(false)}
                className="flex-1 py-3.5 text-[17px] font-normal text-ios-blue hover:bg-gray-50 active:bg-gray-100 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => handleExport(true)}
                className="flex-1 py-3.5 text-[17px] font-semibold text-ios-blue hover:bg-gray-50 active:bg-gray-100 transition-colors"
              >
                确认导出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionDetailPage;
