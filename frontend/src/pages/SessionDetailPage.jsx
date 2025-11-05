import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { 
  ArrowLeft, Download, FileText, GitCompare, 
  CheckCircle, AlertCircle, Shield 
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
  }, [sessionId]);

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
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/workspace')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              
              <div className="flex items-center gap-3">
                <FileText className="w-6 h-6 text-blue-600" />
                <div>
                  <h1 className="text-lg font-semibold text-gray-800">
                    会话详情
                  </h1>
                  <p className="text-xs text-gray-500">
                    {new Date(session.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {session.status === 'completed' && (
                <>
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="w-5 h-5" />
                    <span className="font-medium">已完成</span>
                  </div>
                  
                  <button
                    onClick={() => setShowExportModal(true)}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
                  >
                    <Download className="w-5 h-5" />
                    导出
                  </button>
                </>
              )}
              
              {session.status === 'failed' && (
                <div className="flex items-center gap-2 text-red-600">
                  <AlertCircle className="w-5 h-5" />
                  <span className="font-medium">处理失败</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 标签页 */}
        <div className="bg-white rounded-t-xl shadow-sm border-b">
          <div className="flex gap-4 px-6">
            <button
              onClick={() => setActiveTab('result')}
              className={`py-4 px-2 font-medium border-b-2 transition-colors ${
                activeTab === 'result'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-800'
              }`}
            >
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                优化结果
              </div>
            </button>
            
            <button
              onClick={() => setActiveTab('compare')}
              className={`py-4 px-2 font-medium border-b-2 transition-colors ${
                activeTab === 'compare'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-800'
              }`}
            >
              <div className="flex items-center gap-2">
                <GitCompare className="w-5 h-5" />
                变更对照
              </div>
            </button>
          </div>
        </div>

        {/* 内容区域 */}
        <div className="bg-white rounded-b-xl shadow-sm p-6">
          {activeTab === 'result' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-3">
                  优化后的文本
                </h3>
                <div className="bg-gray-50 rounded-lg p-6 max-h-[600px] overflow-y-auto">
                  <pre className="whitespace-pre-wrap font-sans text-gray-800 leading-relaxed">
                    {getFinalText()}
                  </pre>
                </div>
              </div>
              
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-3">
                  原始文本
                </h3>
                <div className="bg-gray-50 rounded-lg p-6 max-h-96 overflow-y-auto">
                  <pre className="whitespace-pre-wrap font-sans text-gray-600 leading-relaxed">
                    {getOriginalText()}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'compare' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">
                变更对照记录
              </h3>
              
              {changes.length === 0 ? (
                <p className="text-gray-500 text-center py-8">
                  暂无变更记录
                </p>
              ) : (
                changes.map((change, index) => (
                  <div key={change.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded">
                        段落 {change.segment_index + 1}
                      </span>
                      <span className="bg-purple-100 text-purple-800 text-xs font-medium px-2.5 py-0.5 rounded">
                        {change.stage === 'polish' ? '润色阶段' : 
                         change.stage === 'emotion_polish' ? '感情润色阶段' : 
                         '增强阶段'}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-sm font-medium text-gray-700 mb-2">
                          修改前
                        </h4>
                        <div className="bg-red-50 rounded p-3 text-sm text-gray-800">
                          {change.before_text}
                        </div>
                      </div>
                      
                      <div>
                        <h4 className="text-sm font-medium text-gray-700 mb-2">
                          修改后
                        </h4>
                        <div className="bg-green-50 rounded p-3 text-sm text-gray-800">
                          {change.after_text}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* 导出确认模态框 */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6">
            <div className="text-center mb-6">
              <Shield className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-800">
                学术诚信确认
              </h2>
            </div>

            <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded mb-6">
              <p className="text-yellow-900 mb-3">
                在导出优化结果前,请再次确认:
              </p>
              <ul className="space-y-2 text-yellow-800 text-sm">
                <li>✓ 我已审核所有优化内容,确保其符合学术规范</li>
                <li>✓ 论文的核心观点和研究成果是我的原创工作</li>
                <li>✓ 我对最终提交的论文内容承担全部责任</li>
                <li>✓ 我了解学术不端行为的严重后果</li>
              </ul>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                导出格式
              </label>
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="txt">文本文件 (.txt)</option>
                <option value="docx" disabled>Word文档 (.docx) - 即将支持</option>
                <option value="pdf" disabled>PDF文件 (.pdf) - 即将支持</option>
              </select>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowExportModal(false)}
                className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => handleExport(true)}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-lg transition-colors"
              >
                我已确认,导出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionDetailPage;
