import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { Settings, Save, RefreshCw, Cpu, Brain } from 'lucide-react';

const ConfigManager = ({ adminToken }) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  
  const [formData, setFormData] = useState({
    POLISH_MODEL: '',
    POLISH_API_KEY: '',
    POLISH_BASE_URL: '',
    ENHANCE_MODEL: '',
    ENHANCE_API_KEY: '',
    ENHANCE_BASE_URL: '',
    EMOTION_MODEL: '',
    EMOTION_API_KEY: '',
    EMOTION_BASE_URL: '',
    MAX_CONCURRENT_USERS: '',
    HISTORY_COMPRESSION_THRESHOLD: '',
    COMPRESSION_MODEL: '',
    COMPRESSION_API_KEY: '',
    COMPRESSION_BASE_URL: '',
    DEFAULT_USAGE_LIMIT: '',
    SEGMENT_SKIP_THRESHOLD: '',
    MAX_UPLOAD_FILE_SIZE_MB: '',
    THINKING_MODE_ENABLED: true,
    THINKING_MODE_EFFORT: 'high'
  });

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/admin/config', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      
      // 填充表单,直接使用返回的值
      setFormData({
        POLISH_MODEL: response.data.polish.model || '',
        POLISH_API_KEY: response.data.polish.api_key || '',
        POLISH_BASE_URL: response.data.polish.base_url || '',
        ENHANCE_MODEL: response.data.enhance.model || '',
        ENHANCE_API_KEY: response.data.enhance.api_key || '',
        ENHANCE_BASE_URL: response.data.enhance.base_url || '',
        EMOTION_MODEL: response.data.emotion?.model || '',
        EMOTION_API_KEY: response.data.emotion?.api_key || '',
        EMOTION_BASE_URL: response.data.emotion?.base_url || '',
        MAX_CONCURRENT_USERS: response.data.system.max_concurrent_users?.toString() || '',
        HISTORY_COMPRESSION_THRESHOLD: response.data.system.history_compression_threshold?.toString() || '',
        COMPRESSION_MODEL: response.data.system.compression_model || '',
        COMPRESSION_API_KEY: response.data.compression?.api_key || '',
        COMPRESSION_BASE_URL: response.data.compression?.base_url || '',
        DEFAULT_USAGE_LIMIT: response.data.system.default_usage_limit?.toString() || '',
        SEGMENT_SKIP_THRESHOLD: response.data.system.segment_skip_threshold?.toString() || '',
        MAX_UPLOAD_FILE_SIZE_MB: response.data.system.max_upload_file_size_mb?.toString() || '',
        THINKING_MODE_ENABLED: response.data.thinking?.enabled ?? true,
        THINKING_MODE_EFFORT: response.data.thinking?.effort || 'high'
      });
    } catch (error) {
      toast.error('获取配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // 只发送已修改的非空值
      const updates = {};
      Object.keys(formData).forEach(key => {
        const value = formData[key];
        // 布尔值需要转换为字符串
        if (typeof value === 'boolean') {
          updates[key] = value.toString();
        } else if (typeof value === 'string' && value.trim()) {
          updates[key] = value.trim();
        }
      });

      const response = await axios.post('/api/admin/config', updates, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });

      toast.success(response.data.message);
      fetchConfig();
    } catch (error) {
      toast.error(error.response?.data?.detail || '保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 润色模型配置 */}
      <div className="bg-white rounded-2xl shadow-ios p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-teal-50 rounded-xl flex items-center justify-center">
            <Cpu className="w-5 h-5 text-teal-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">润色模型配置</h3>
        </div>

        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              模型名称
            </label>
            <input
              type="text"
              value={formData.POLISH_MODEL}
              onChange={(e) => setFormData({...formData, POLISH_MODEL: e.target.value})}
              placeholder="gemini-2.5-pro"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              API Key (可选)
            </label>
            <input
              type="text"
              value={formData.POLISH_API_KEY}
              onChange={(e) => setFormData({...formData, POLISH_API_KEY: e.target.value})}
              placeholder="留空使用默认 OpenAI Key"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Base URL
            </label>
            <input
              type="text"
              value={formData.POLISH_BASE_URL}
              onChange={(e) => setFormData({...formData, POLISH_BASE_URL: e.target.value})}
              placeholder="http://localhost:8317/v1"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>
        </div>
      </div>

      {/* 增强模型配置 */}
      <div className="bg-white rounded-2xl shadow-ios p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center">
            <Cpu className="w-5 h-5 text-purple-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">论文增强模型配置</h3>
        </div>

        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              模型名称
            </label>
            <input
              type="text"
              value={formData.ENHANCE_MODEL}
              onChange={(e) => setFormData({...formData, ENHANCE_MODEL: e.target.value})}
              placeholder="gemini-2.5-pro"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              API Key (可选)
            </label>
            <input
              type="text"
              value={formData.ENHANCE_API_KEY}
              onChange={(e) => setFormData({...formData, ENHANCE_API_KEY: e.target.value})}
              placeholder="留空使用默认 OpenAI Key"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Base URL
            </label>
            <input
              type="text"
              value={formData.ENHANCE_BASE_URL}
              onChange={(e) => setFormData({...formData, ENHANCE_BASE_URL: e.target.value})}
              placeholder="http://localhost:8317/v1"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>
        </div>
      </div>

      {/* 感情文章润色模型配置 */}
      <div className="bg-white rounded-2xl shadow-ios p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-rose-50 rounded-xl flex items-center justify-center">
            <Cpu className="w-5 h-5 text-rose-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">感情文章润色模型配置</h3>
        </div>

        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              模型名称
            </label>
            <input
              type="text"
              value={formData.EMOTION_MODEL}
              onChange={(e) => setFormData({...formData, EMOTION_MODEL: e.target.value})}
              placeholder="gemini-2.5-pro"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              API Key (可选)
            </label>
            <input
              type="text"
              value={formData.EMOTION_API_KEY}
              onChange={(e) => setFormData({...formData, EMOTION_API_KEY: e.target.value})}
              placeholder="留空使用默认 OpenAI Key"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Base URL
            </label>
            <input
              type="text"
              value={formData.EMOTION_BASE_URL}
              onChange={(e) => setFormData({...formData, EMOTION_BASE_URL: e.target.value})}
              placeholder="http://localhost:8317/v1"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>
        </div>
      </div>

      {/* 思考模式配置 */}
      <div className="bg-white rounded-2xl shadow-ios p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center">
            <Brain className="w-5 h-5 text-indigo-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">思考模式配置</h3>
        </div>

        <div className="space-y-5">
          {/* 启用开关 */}
          <div className="flex items-center justify-between">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                启用思考模式
              </label>
              <p className="text-xs text-gray-400 mt-1">
                开启后模型会进行深度推理，可能增加响应时间和 token 消耗
              </p>
            </div>
            <button
              type="button"
              onClick={() => setFormData({
                ...formData,
                THINKING_MODE_ENABLED: !formData.THINKING_MODE_ENABLED
              })}
              className={`relative w-12 h-7 rounded-full transition-colors ${
                formData.THINKING_MODE_ENABLED
                  ? 'bg-indigo-600'
                  : 'bg-gray-200'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full shadow transition-transform ${
                formData.THINKING_MODE_ENABLED
                  ? 'translate-x-5'
                  : 'translate-x-0'
              }`} />
            </button>
          </div>

          {/* 思考强度选择器 */}
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              思考强度
            </label>
            <select
              value={formData.THINKING_MODE_EFFORT}
              onChange={(e) => setFormData({...formData, THINKING_MODE_EFFORT: e.target.value})}
              disabled={!formData.THINKING_MODE_ENABLED}
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="none">无推理 (最低延迟)</option>
              <option value="low">轻度推理</option>
              <option value="medium">中度推理</option>
              <option value="high">深度推理 (推荐)</option>
              <option value="xhigh">极深推理 (仅部分模型支持)</option>
            </select>
            <p className="mt-1.5 text-xs text-gray-400">
              更高的强度会增加推理 token 消耗和响应时间，但可能获得更好的结果
            </p>
          </div>
        </div>
      </div>

      {/* 系统配置 */}
      <div className="bg-white rounded-2xl shadow-ios p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-orange-50 rounded-xl flex items-center justify-center">
            <Settings className="w-5 h-5 text-orange-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">系统配置</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              最大并发用户数
            </label>
            <input
              type="number"
              value={formData.MAX_CONCURRENT_USERS}
              onChange={(e) => setFormData({...formData, MAX_CONCURRENT_USERS: e.target.value})}
              placeholder="5"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              历史压缩阈值（字符）
            </label>
            <input
              type="number"
              value={formData.HISTORY_COMPRESSION_THRESHOLD}
              onChange={(e) => setFormData({...formData, HISTORY_COMPRESSION_THRESHOLD: e.target.value})}
              placeholder="5000"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              压缩模型
            </label>
            <input
              type="text"
              value={formData.COMPRESSION_MODEL}
              onChange={(e) => setFormData({...formData, COMPRESSION_MODEL: e.target.value})}
              placeholder="gemini-2.5-pro"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              压缩 API Key (可选)
            </label>
            <input
              type="text"
              value={formData.COMPRESSION_API_KEY}
              onChange={(e) => setFormData({...formData, COMPRESSION_API_KEY: e.target.value})}
              placeholder="留空使用默认 OpenAI Key"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm font-mono"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-500 mb-2">
              压缩 Base URL
            </label>
            <input
              type="text"
              value={formData.COMPRESSION_BASE_URL}
              onChange={(e) => setFormData({...formData, COMPRESSION_BASE_URL: e.target.value})}
              placeholder="http://localhost:8317/v1"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              默认使用次数限制
            </label>
            <input
              type="number"
              value={formData.DEFAULT_USAGE_LIMIT}
              onChange={(e) => setFormData({...formData, DEFAULT_USAGE_LIMIT: e.target.value})}
              placeholder="1"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
            <p className="mt-1.5 text-xs text-gray-400">新用户的默认使用次数限制</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              段落跳过阈值（字符）
            </label>
            <input
              type="number"
              value={formData.SEGMENT_SKIP_THRESHOLD}
              onChange={(e) => setFormData({...formData, SEGMENT_SKIP_THRESHOLD: e.target.value})}
              placeholder="15"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
            <p className="mt-1.5 text-xs text-gray-400">小于此字数的段落将被识别为标题并跳过</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Word 排版文件大小限制 (MB)
            </label>
            <input
              type="number"
              value={formData.MAX_UPLOAD_FILE_SIZE_MB}
              onChange={(e) => setFormData({...formData, MAX_UPLOAD_FILE_SIZE_MB: e.target.value})}
              placeholder="0"
              min="0"
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            />
            <p className="mt-1.5 text-xs text-gray-400">0 表示无限制</p>
          </div>
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-4">
        <button
          onClick={fetchConfig}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 bg-white border border-gray-200 hover:bg-gray-50 disabled:bg-gray-50 text-gray-700 rounded-xl transition-all active:scale-[0.98] font-medium shadow-sm"
        >
          <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-xl transition-all active:scale-[0.98] font-semibold shadow-sm"
        >
          {saving ? (
            <>
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              保存中...
            </>
          ) : (
            <>
              <Save className="w-5 h-5" />
              保存配置
            </>
          )}
        </button>
      </div>

      <div className="bg-green-50/50 border border-green-100 rounded-xl p-4">
        <p className="text-sm font-medium text-green-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500"></span>
          配置修改后会立即生效，无需重启服务！
        </p>
      </div>
    </div>
  );
};

export default ConfigManager;
