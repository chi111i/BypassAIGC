import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  FileText, Upload, Download, History, LogOut, Play,
  CheckCircle, AlertCircle, Trash2, Info, Settings,
  Loader2, FileUp, X, Sparkles
} from 'lucide-react';
import { wordFormatterAPI } from '../api';

const WordFormatterPage = () => {
  const [inputMode, setInputMode] = useState('file'); // 'file' or 'text'
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [specs, setSpecs] = useState([]);
  const [selectedSpec, setSelectedSpec] = useState('Generic_CN');
  const [useAI, setUseAI] = useState(false);
  const [includeCover, setIncludeCover] = useState(true);
  const [includeToc, setIncludeToc] = useState(true);
  const [jobs, setJobs] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [usage, setUsage] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef(null);
  const eventSourceRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadSpecs();
    loadJobs();
    loadUsage();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (activeJob) {
      startSSE(activeJob);
    }
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [activeJob]);

  const loadSpecs = async () => {
    try {
      const response = await wordFormatterAPI.listSpecs();
      setSpecs(response.data.specs || []);
    } catch (error) {
      console.error('Load specs failed:', error);
    }
  };

  const loadJobs = async () => {
    try {
      setIsLoadingJobs(true);
      const response = await wordFormatterAPI.listJobs(20);
      setJobs(response.data.jobs || []);

      const processing = response.data.jobs?.find(
        j => j.status === 'running' || j.status === 'pending'
      );
      if (processing) {
        setActiveJob(processing.job_id);
      }
    } catch (error) {
      console.error('Load jobs failed:', error);
    } finally {
      setIsLoadingJobs(false);
    }
  };

  const loadUsage = async () => {
    try {
      const response = await wordFormatterAPI.getUsage();
      setUsage(response.data);
    } catch (error) {
      console.error('Load usage failed:', error);
    }
  };

  const startSSE = (jobId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = wordFormatterAPI.getStreamUrl(jobId);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        updateJobProgress(jobId, data);
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.addEventListener('progress', (event) => {
      try {
        const data = JSON.parse(event.data);
        updateJobProgress(jobId, { ...data, status: 'running' });
      } catch (e) {
        console.error('SSE progress error:', e);
      }
    });

    es.addEventListener('completed', (event) => {
      try {
        const data = JSON.parse(event.data);
        updateJobProgress(jobId, { status: 'completed', ...data });
        setActiveJob(null);
        toast.success('Word 排版完成!');
        loadJobs();
        loadUsage();
      } catch (e) {
        console.error('SSE completed error:', e);
      }
      es.close();
    });

    es.addEventListener('error', (event) => {
      try {
        const data = JSON.parse(event.data);
        updateJobProgress(jobId, { status: 'failed', error: data.message });
        setActiveJob(null);
        toast.error(`排版失败: ${data.message}`);
      } catch (e) {
        console.error('SSE error event:', e);
      }
      es.close();
    });

    es.onerror = () => {
      es.close();
    };
  };

  const updateJobProgress = (jobId, data) => {
    setJobs(prev =>
      prev.map(j =>
        j.job_id === jobId ? { ...j, ...data } : j
      )
    );
  };

  const handleSubmit = async () => {
    if (inputMode === 'text' && !text.trim()) {
      toast.error('Please enter text');
      return;
    }
    if (inputMode === 'file' && !file) {
      toast.error('Please select a file');
      return;
    }
    if (isSubmitting || activeJob) {
      return;
    }

    try {
      setIsSubmitting(true);
      let response;

      if (inputMode === 'file') {
        response = await wordFormatterAPI.formatFile(file, {
          spec_name: selectedSpec,
          include_cover: includeCover,
          include_toc: includeToc,
          use_ai_recognition: useAI,
        });
      } else {
        response = await wordFormatterAPI.formatText({
          text,
          spec_name: selectedSpec,
          include_cover: includeCover,
          include_toc: includeToc,
          use_ai_recognition: useAI,
        });
      }

      setActiveJob(response.data.job_id);
      toast.success('Task started');
      setText('');
      setFile(null);
      loadJobs();
    } catch (error) {
      toast.error('Start failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownload = async (job) => {
    if (job.status !== 'completed') return;
    const url = wordFormatterAPI.getDownloadUrl(job.job_id);
    window.open(url, '_blank');
  };

  const handleDeleteJob = async (event, job) => {
    event.stopPropagation();
    if (!window.confirm('Confirm delete this job?')) return;

    try {
      await wordFormatterAPI.deleteJob(job.job_id);
      if (activeJob === job.job_id) {
        setActiveJob(null);
      }
      toast.success('Job deleted');
      loadJobs();
    } catch (error) {
      toast.error('Delete failed');
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (isValidFile(droppedFile)) {
        setFile(droppedFile);
        setInputMode('file');
      } else {
        toast.error('Only .docx, .txt, .md files supported');
      }
    }
  };

  const isValidFile = (f) => {
    const ext = f.name.split('.').pop().toLowerCase();
    return ['docx', 'txt', 'md', 'markdown'].includes(ext);
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (isValidFile(selectedFile)) {
        setFile(selectedFile);
      } else {
        toast.error('Only .docx, .txt, .md files supported');
      }
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('cardKey');
    navigate('/');
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="min-h-screen bg-ios-background">
      {/* Navigation */}
      <nav className="bg-white/80 backdrop-blur-xl border-b border-ios-separator sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-[52px]">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-[17px] font-semibold text-black tracking-tight">
                AI Word 精确排版
              </h1>
            </div>

            <div className="flex items-center gap-4">
              {usage && (
                <div className="text-[13px] text-ios-gray">
                  已使用: <span className="font-medium text-black">{usage.usage_count}</span>
                  {usage.usage_limit > 0 && ` / ${usage.usage_limit}`}
                </div>
              )}

              <Link
                to="/workspace"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-[13px] font-medium text-gray-700 transition-colors"
              >
                <FileText className="w-4 h-4" />
                <span className="hidden sm:inline">论文润色</span>
              </Link>

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
          {/* Left - Input Area */}
          <div className="lg:col-span-2 space-y-6">

            {/* Info Card */}
            <div className="bg-white rounded-2xl shadow-ios overflow-hidden">
              <div className="p-4 flex items-start gap-3 bg-purple-50/50">
                <Info className="w-5 h-5 text-purple-500 flex-shrink-0 mt-0.5" />
                <div className="text-[15px] text-black">
                  <p className="font-semibold mb-1 text-purple-600">AI Word Formatter</p>
                  <p className="text-gray-700 leading-relaxed">
                    Automatically format documents according to academic paper standards.
                    Supports .docx, .txt, .md files or direct text input.
                  </p>
                </div>
              </div>
            </div>

            {/* Main Input Card */}
            <div className="bg-white rounded-2xl shadow-ios p-5">
              <div className="h-[40px] flex items-center justify-between mb-4">
                <h2 className="text-[20px] font-bold text-black tracking-tight pl-1">
                  New Task
                </h2>

                {/* Input Mode Toggle */}
                <div className="flex bg-gray-100 rounded-lg p-1">
                  <button
                    onClick={() => setInputMode('file')}
                    className={`px-3 py-1.5 text-[13px] font-medium rounded-md transition-all ${
                      inputMode === 'file'
                        ? 'bg-white text-black shadow-sm'
                        : 'text-ios-gray hover:text-black'
                    }`}
                  >
                    <Upload className="w-4 h-4 inline mr-1" />
                    File
                  </button>
                  <button
                    onClick={() => setInputMode('text')}
                    className={`px-3 py-1.5 text-[13px] font-medium rounded-md transition-all ${
                      inputMode === 'text'
                        ? 'bg-white text-black shadow-sm'
                        : 'text-ios-gray hover:text-black'
                    }`}
                  >
                    <FileText className="w-4 h-4 inline mr-1" />
                    Text
                  </button>
                </div>
              </div>

              {/* File Upload Area */}
              {inputMode === 'file' && (
                <div
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                    dragActive
                      ? 'border-purple-500 bg-purple-50'
                      : file
                      ? 'border-purple-300 bg-purple-50/50'
                      : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".docx,.txt,.md,.markdown"
                    onChange={handleFileSelect}
                    className="hidden"
                  />

                  {file ? (
                    <div className="space-y-3">
                      <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mx-auto">
                        <FileUp className="w-6 h-6 text-purple-500" />
                      </div>
                      <div>
                        <p className="font-medium text-black">{file.name}</p>
                        <p className="text-[13px] text-ios-gray">{formatFileSize(file.size)}</p>
                      </div>
                      <button
                        onClick={() => setFile(null)}
                        className="text-ios-red text-[13px] hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center mx-auto">
                        <Upload className="w-6 h-6 text-gray-400" />
                      </div>
                      <div>
                        <p className="text-black font-medium">Drag & drop file here</p>
                        <p className="text-[13px] text-ios-gray">or</p>
                      </div>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="px-4 py-2 bg-purple-500 text-white rounded-lg text-[14px] font-medium hover:bg-purple-600 transition-colors"
                      >
                        Browse Files
                      </button>
                      <p className="text-[12px] text-ios-gray">
                        Supported: .docx, .txt, .md
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Text Input Area */}
              {inputMode === 'text' && (
                <div className="relative">
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Paste your document content here..."
                    className="w-full h-64 px-4 py-3 bg-gray-50 rounded-xl focus:bg-white focus:ring-2 focus:ring-purple-500/20 transition-all text-[16px] leading-relaxed text-black placeholder-gray-400 border-none outline-none resize-none"
                  />
                  <div className="absolute bottom-3 right-3 text-[12px] text-ios-gray bg-white/80 px-2 py-1 rounded-md backdrop-blur-sm">
                    {text.length} chars
                  </div>
                </div>
              )}

              {/* Options */}
              <div className="mt-5 space-y-4">
                {/* Spec Selection */}
                <div>
                  <label className="block text-[13px] font-medium text-ios-gray mb-2 ml-1 uppercase tracking-wide">
                    Format Spec
                  </label>
                  <select
                    value={selectedSpec}
                    onChange={(e) => setSelectedSpec(e.target.value)}
                    className="w-full px-3 py-2.5 bg-gray-50 rounded-xl border-none text-[15px] text-black focus:ring-2 focus:ring-purple-500/20"
                  >
                    {specs.map((spec) => (
                      <option key={spec} value={spec}>{spec}</option>
                    ))}
                  </select>
                </div>

                {/* Toggles */}
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeCover}
                      onChange={(e) => setIncludeCover(e.target.checked)}
                      className="w-4 h-4 text-purple-500 rounded focus:ring-purple-500"
                    />
                    <span className="text-[14px] text-black">Include Cover</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeToc}
                      onChange={(e) => setIncludeToc(e.target.checked)}
                      className="w-4 h-4 text-purple-500 rounded focus:ring-purple-500"
                    />
                    <span className="text-[14px] text-black">Include TOC</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={useAI}
                      onChange={(e) => setUseAI(e.target.checked)}
                      className="w-4 h-4 text-purple-500 rounded focus:ring-purple-500"
                    />
                    <span className="text-[14px] text-black flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                      AI Recognition
                    </span>
                  </label>
                </div>
              </div>

              {/* Submit Button */}
              <div className="mt-5 flex justify-end">
                <button
                  onClick={handleSubmit}
                  disabled={(inputMode === 'text' && !text.trim()) || (inputMode === 'file' && !file) || activeJob || isSubmitting}
                  className="flex items-center gap-2 bg-purple-500 hover:bg-purple-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3 px-8 rounded-xl transition-all active:scale-[0.98] shadow-sm text-[17px]"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 fill-current" />
                      Start Format
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Active Job Progress */}
            {activeJob && jobs.find(j => j.job_id === activeJob) && (
              <div className="bg-white rounded-2xl shadow-ios p-5 border border-purple-100">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-[17px] font-bold text-black flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
                    Processing
                  </h2>
                  <span className="text-[13px] font-medium px-2 py-1 bg-purple-50 text-purple-600 rounded-md">
                    {jobs.find(j => j.job_id === activeJob)?.phase || 'Running'}
                  </span>
                </div>

                {(() => {
                  const job = jobs.find(j => j.job_id === activeJob);
                  return (
                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-[13px] mb-2 font-medium">
                          <span className="text-ios-gray">
                            {job?.message || 'Processing document...'}
                          </span>
                          <span className="text-purple-600">
                            {((job?.progress || 0) * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-purple-500 h-2 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${(job?.progress || 0) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          {/* Right - History */}
          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-ios overflow-hidden flex flex-col h-[calc(100vh-140px)] sticky top-24">
              <div className="p-5 border-b border-gray-100 bg-white/50 backdrop-blur-sm z-10 h-[72px] flex items-center">
                <div className="flex items-center gap-2">
                  <History className="w-5 h-5 text-ios-gray" />
                  <h2 className="text-[20px] font-bold text-black tracking-tight">
                    History
                  </h2>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar h-full">
                {isLoadingJobs ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-ios-gray" />
                  </div>
                ) : jobs.length === 0 ? (
                  <div className="text-center py-12 space-y-2">
                    <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mx-auto text-gray-300">
                      <History className="w-6 h-6" />
                    </div>
                    <p className="text-ios-gray text-sm">
                      No jobs yet
                    </p>
                  </div>
                ) : (
                  jobs.map((job) => (
                    <div
                      key={job.job_id}
                      className="group p-3 rounded-xl hover:bg-gray-50 transition-all cursor-pointer border border-transparent hover:border-gray-100 relative"
                    >
                      <div className="flex items-start justify-between mb-1.5 gap-2">
                        <div className="flex items-center gap-1.5">
                          {job.status === 'completed' && (
                            <CheckCircle className="w-4 h-4 text-ios-green" />
                          )}
                          {(job.status === 'running' || job.status === 'pending') && (
                            <Loader2 className="w-4 h-4 text-purple-500 animate-spin" />
                          )}
                          {job.status === 'failed' && (
                            <AlertCircle className="w-4 h-4 text-ios-red" />
                          )}
                          <span className={`text-[13px] font-medium ${
                            job.status === 'completed' ? 'text-black' :
                            job.status === 'running' || job.status === 'pending' ? 'text-purple-600' :
                            job.status === 'failed' ? 'text-ios-red' : 'text-ios-gray'
                          }`}>
                            {job.status === 'completed' && 'Completed'}
                            {job.status === 'running' && 'Running'}
                            {job.status === 'pending' && 'Pending'}
                            {job.status === 'failed' && 'Failed'}
                          </span>
                        </div>

                        <span className="text-[11px] text-ios-gray/70 font-medium">
                          {new Date(job.created_at).toLocaleDateString()}
                        </span>
                      </div>

                      <p className="text-[13px] text-ios-gray leading-snug line-clamp-2 mb-2 pr-6">
                        {job.input_file_name || job.output_filename || 'Text input'}
                      </p>

                      {(job.status === 'running' || job.status === 'pending') && (
                        <div className="w-full bg-gray-100 rounded-full h-1 mb-1">
                          <div
                            className="bg-purple-500 h-1 rounded-full"
                            style={{ width: `${(job.progress || 0) * 100}%` }}
                          />
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="flex items-center justify-between mt-1">
                        {job.status === 'completed' && (
                          <button
                            onClick={() => handleDownload(job)}
                            className="px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200 flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" />
                            Download
                          </button>
                        )}
                        <button
                          onClick={(event) => handleDeleteJob(event, job)}
                          className="p-1.5 text-gray-300 hover:text-ios-red hover:bg-red-50 rounded-lg transition-colors ml-auto"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {job.status === 'failed' && job.error && (
                        <div className="text-[11px] text-ios-red bg-red-50 px-2 py-1 rounded mt-1">
                          {job.error}
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

export default WordFormatterPage;
