import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  FileText, Upload, Download, History, LogOut, Play,
  CheckCircle, AlertCircle, Trash2, Info, Settings,
  Loader2, FileUp, X, ArrowLeft, ArrowRight, Sparkles,
  Edit3, Eye, BookOpen, HelpCircle, ChevronDown, ChevronUp
} from 'lucide-react';
import { wordFormatterAPI } from '../api';

const WordFormatterPage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Check for data passed from other pages
  const preprocessedText = location.state?.preprocessedText || null;
  const passedSpecJson = location.state?.specJson || null;
  const passedSpecName = location.state?.specName || null;

  const [inputMode, setInputMode] = useState('file'); // 'file' or 'text'
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [specs, setSpecs] = useState([]);
  const [savedSpecs, setSavedSpecs] = useState([]);
  const [selectedSpec, setSelectedSpec] = useState('通用论文（首行缩进）');
  const [customSpecJson, setCustomSpecJson] = useState(null);
  const [includeCover, setIncludeCover] = useState(true);
  const [includeToc, setIncludeToc] = useState(true);
  const [jobs, setJobs] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [usage, setUsage] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [showPreviewMode, setShowPreviewMode] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [showSampleCode, setShowSampleCode] = useState(false);

  const fileInputRef = useRef(null);
  const eventSourceRef = useRef(null);

  // Initialize with passed data
  useEffect(() => {
    if (preprocessedText) {
      setText(preprocessedText);
      setInputMode('text');
      toast.success('已加载预处理后的文本');
    }
    if (passedSpecJson) {
      setCustomSpecJson(passedSpecJson);
      setSelectedSpec('_custom_');
      toast.success(`已加载规范: ${passedSpecName || '自定义规范'}`);
    }
  }, [preprocessedText, passedSpecJson, passedSpecName]);

  useEffect(() => {
    loadSpecs();
    loadSavedSpecs();
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

  const loadSavedSpecs = async () => {
    try {
      const response = await wordFormatterAPI.listSavedSpecs();
      setSavedSpecs(response.data.specs || []);
    } catch (error) {
      console.error('Load saved specs failed:', error);
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
      if (es.readyState === EventSource.CLOSED) {
        es.close();
        return;
      }
      es.close();
      setTimeout(() => {
        loadJobs();
      }, 1000);
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
      toast.error('请输入文本内容');
      return;
    }
    if (inputMode === 'file' && !file) {
      toast.error('请选择文件');
      return;
    }
    if (isSubmitting || activeJob) {
      return;
    }

    try {
      setIsSubmitting(true);
      let response;

      // Determine spec to use
      const specToUse = selectedSpec === '_custom_' ? null : selectedSpec;
      const specJsonToUse = selectedSpec === '_custom_' ? customSpecJson : null;

      if (inputMode === 'file') {
        response = await wordFormatterAPI.formatFile(file, {
          spec_name: specToUse,
          spec_json: specJsonToUse,
          include_cover: includeCover,
          include_toc: includeToc,
        });
      } else {
        response = await wordFormatterAPI.formatText({
          text,
          spec_name: specToUse,
          spec_json: specJsonToUse,
          include_cover: includeCover,
          include_toc: includeToc,
        });
      }

      setActiveJob(response.data.job_id);
      toast.success('任务已开始');
      setText('');
      setFile(null);
      loadJobs();
    } catch (error) {
      toast.error('启动失败: ' + (error.response?.data?.detail || error.message));
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
    if (!window.confirm('确定删除此任务？')) return;

    try {
      await wordFormatterAPI.deleteJob(job.job_id);
      if (activeJob === job.job_id) {
        setActiveJob(null);
      }
      toast.success('任务已删除');
      loadJobs();
    } catch (error) {
      toast.error('删除失败');
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
        toast.error('仅支持 .docx、.txt、.md 文件');
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
        toast.error('仅支持 .docx、.txt、.md 文件');
      }
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('authToken');
    sessionStorage.removeItem('username');
    navigate('/');
  };

  const handleSelectSavedSpec = (spec) => {
    setCustomSpecJson(spec.spec_json);
    setSelectedSpec('_custom_');
    toast.success(`已加载保存的规范: ${spec.name}`);
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // Check if we have workflow data
  const hasWorkflowData = preprocessedText || passedSpecJson;

  return (
    <div className="min-h-screen bg-ios-background">
      {/* Navigation */}
      <nav className="bg-white/80 backdrop-blur-xl border-b border-ios-separator sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-[52px]">
            <div className="flex items-center gap-2">
              {hasWorkflowData && (
                <Link
                  to="/format-checker"
                  className="flex items-center gap-1 text-gray-600 hover:text-gray-900 mr-2"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span className="text-sm">返回格式检测</span>
                </Link>
              )}
              <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
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
        {/* Workflow Indicator */}
        {hasWorkflowData && (
          <div className="mb-6 flex items-center justify-center gap-2 text-sm text-gray-500">
            <span className="px-3 py-1 bg-gray-100 rounded-full">1. 生成规范</span>
            <ArrowRight className="w-4 h-4" />
            <span className="px-3 py-1 bg-gray-100 rounded-full">2. 格式检测</span>
            <ArrowRight className="w-4 h-4" />
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full font-medium">
              3. 生成 Word
            </span>
          </div>
        )}

        {/* Workflow Data Indicators */}
        {hasWorkflowData && (
          <div className="mb-4 flex flex-wrap gap-2">
            {preprocessedText && (
              <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-sm">
                <CheckCircle className="w-4 h-4 text-green-600" />
                <span className="text-green-700">已加载预处理文本 ({preprocessedText.length} 字符)</span>
                <button
                  onClick={() => setShowPreviewMode(!showPreviewMode)}
                  className="ml-2 text-green-600 hover:text-green-700"
                >
                  {showPreviewMode ? <Eye className="w-4 h-4" /> : <Edit3 className="w-4 h-4" />}
                </button>
              </div>
            )}
            {passedSpecJson && (
              <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm">
                <Sparkles className="w-4 h-4 text-blue-600" />
                <span className="text-blue-700">使用自定义规范: {passedSpecName || '自定义'}</span>
              </div>
            )}
          </div>
        )}

        {/* Quick Start Guide - Only show when no workflow data */}
        {!hasWorkflowData && (
          <div className="mb-6 bg-gradient-to-r from-blue-50 to-blue-50 rounded-2xl p-5 border border-blue-100">
            <h3 className="text-[15px] font-semibold text-blue-900 mb-3">推荐工作流程</h3>
            <div className="flex items-center gap-4 text-sm">
              <Link
                to="/spec-generator"
                className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg border border-blue-200 text-blue-700 hover:bg-blue-50 transition-colors"
              >
                <span className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center text-xs font-bold">1</span>
                生成排版规范
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                to="/format-checker"
                className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg border border-blue-200 text-blue-700 hover:bg-blue-50 transition-colors"
              >
                <span className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center text-xs font-bold">2</span>
                格式检测
                <ArrowRight className="w-4 h-4" />
              </Link>
              <span className="flex items-center gap-2 px-4 py-2 bg-blue-100 rounded-lg text-blue-700 font-medium">
                <span className="w-6 h-6 bg-blue-200 rounded-full flex items-center justify-center text-xs font-bold">3</span>
                生成 Word
              </span>
            </div>
            <p className="mt-3 text-[13px] text-blue-600">
              或者直接在下方上传文件/输入文本，使用内置规范快速排版
            </p>
          </div>
        )}

        {/* Markdown Format Guide */}
        <div className="mb-6 bg-white rounded-2xl shadow-ios border border-gray-100 overflow-hidden">
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                <BookOpen className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-left">
                <h3 className="text-[15px] font-semibold text-gray-900">Markdown 论文格式指南</h3>
                <p className="text-[13px] text-gray-500">查看格式要求和样例代码</p>
              </div>
            </div>
            {showGuide ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
          </button>

          {showGuide && (
            <div className="px-5 pb-5 border-t border-gray-100">
              <div className="mt-4 space-y-4">
                {/* Format Requirements */}
                <div className="bg-blue-50 rounded-xl p-4">
                  <h4 className="text-[14px] font-semibold text-blue-900 mb-3 flex items-center gap-2">
                    <HelpCircle className="w-4 h-4" />
                    格式要求
                  </h4>
                  <ul className="text-[13px] text-blue-800 space-y-2">
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>YAML 头部（可选）：</strong>在文件开头使用 <code className="bg-blue-100 px-1 rounded">---</code> 包裹元信息</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>标题层级：</strong>使用 <code className="bg-blue-100 px-1 rounded">#</code> 表示一级标题，<code className="bg-blue-100 px-1 rounded">##</code> 表示二级标题，以此类推</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>智能级别检测：</strong>系统会自动检测标题起始级别，即使用 <code className="bg-blue-100 px-1 rounded">##</code> 作为一级标题也能正确排版</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>前置章节：</strong>摘要、Abstract、关键词、致谢、参考文献等会自动识别并使用专用样式</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>参考文献：</strong>以 <code className="bg-blue-100 px-1 rounded">[1]</code> 开头的段落会被识别为参考文献条目</span>
                    </li>
                  </ul>
                </div>

                {/* Sample Code Toggle */}
                <div className="border border-gray-200 rounded-xl overflow-hidden">
                  <button
                    onClick={() => setShowSampleCode(!showSampleCode)}
                    className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <span className="text-[14px] font-medium text-gray-700">查看 Markdown 样例代码</span>
                    {showSampleCode ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
                  </button>

                  {showSampleCode && (
                    <div className="p-4 bg-gray-900 text-gray-100 text-[12px] font-mono overflow-x-auto max-h-[400px] overflow-y-auto">
                      <pre>{`---
title_cn: 基于深度学习的图像识别技术研究
title_en: Research on Image Recognition Based on Deep Learning
author: 张三
major: 计算机科学与技术
tutor: 李四 教授
---

# 摘要

随着人工智能技术的快速发展，深度学习在图像识别领域取得了显著突破...

# 关键词

深度学习　图像识别　卷积神经网络　特征提取

# Abstract

With the rapid development of artificial intelligence...

# Key Words

Deep Learning; Image Recognition; Convolutional Neural Network

# 绪论

## 研究背景

图像识别是计算机视觉领域的核心问题之一...

## 研究意义

本研究的意义主要体现在以下几个方面：

1. 理论意义：深化对深度学习模型作用机制的理解
2. 实践意义：为实际应用提供高效可靠的解决方案

# 相关工作

## 传统图像识别方法

传统的图像识别方法主要依赖于手工设计的特征...

### SIFT特征

尺度不变特征变换（SIFT）是一种经典的局部特征描述方法...

### HOG特征

方向梯度直方图（HOG）主要用于行人检测等任务...

## 深度学习方法

深度学习方法通过多层神经网络自动学习图像特征...

# 实验分析

## 数据集介绍

| 数据集 | 类别数 | 训练集 | 测试集 |
| ------ | ------ | ------ | ------ |
| CIFAR-10 | 10 | 50000 | 10000 |
| ImageNet | 1000 | 1.2M | 50000 |

## 实验结果

本文方法在各数据集上的准确率如下：

1. CIFAR-10：96.5%
2. ImageNet Top-1：78.9%

# 致谢

感谢导师李四教授在本研究过程中给予的悉心指导...

# 参考文献

[1] LeCun Y, Bengio Y, Hinton G. Deep learning[J]. Nature, 2015.

[2] He K, et al. Deep residual learning for image recognition. CVPR, 2016.

[3] Krizhevsky A, et al. ImageNet classification with deep CNNs. NeurIPS, 2012.`}</pre>
                    </div>
                  )}
                </div>

                {/* Download Sample Files */}
                <div className="flex flex-wrap gap-3">
                  <a
                    href="/sample-paper.md"
                    download="sample-paper.md"
                    className="flex items-center gap-2 px-4 py-2 bg-green-50 hover:bg-green-100 border border-green-200 rounded-lg text-[13px] text-green-700 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    下载标准样例（# 一级标题）
                  </a>
                  <a
                    href="/sample-paper-level2.md"
                    download="sample-paper-level2.md"
                    className="flex items-center gap-2 px-4 py-2 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg text-[13px] text-amber-700 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    下载样例（## 作为一级标题）
                  </a>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left - Input Area */}
          <div className="lg:col-span-2 space-y-6">

            {/* Info Card */}
            <div className="bg-white rounded-2xl shadow-ios overflow-hidden">
              <div className="p-4 flex items-start gap-3 bg-blue-50/50">
                <Info className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                <div className="text-[15px] text-black">
                  <p className="font-semibold mb-1 text-blue-600">AI Word 精确排版</p>
                  <p className="text-gray-700 leading-relaxed">
                    根据学术论文规范自动排版文档。
                    支持 .docx、.txt、.md 文件或直接输入文本。
                  </p>
                </div>
              </div>
            </div>

            {/* Main Input Card */}
            <div className="bg-white rounded-2xl shadow-ios p-5">
              <div className="h-[40px] flex items-center justify-between mb-4">
                <h2 className="text-[20px] font-bold text-black tracking-tight pl-1">
                  {hasWorkflowData ? '确认并开始排版' : '新建任务'}
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
                    文件
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
                    文本
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
                      ? 'border-blue-500 bg-blue-50'
                      : file
                      ? 'border-blue-300 bg-blue-50/50'
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
                      <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mx-auto">
                        <FileUp className="w-6 h-6 text-blue-500" />
                      </div>
                      <div>
                        <p className="font-medium text-black">{file.name}</p>
                        <p className="text-[13px] text-ios-gray">{formatFileSize(file.size)}</p>
                      </div>
                      <button
                        onClick={() => setFile(null)}
                        className="text-ios-red text-[13px] hover:underline"
                      >
                        移除
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center mx-auto">
                        <Upload className="w-6 h-6 text-gray-400" />
                      </div>
                      <div>
                        <p className="text-black font-medium">拖拽文件到此处</p>
                        <p className="text-[13px] text-ios-gray">或</p>
                      </div>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="px-4 py-2 bg-blue-500 text-white rounded-lg text-[14px] font-medium hover:bg-blue-600 transition-colors"
                      >
                        浏览文件
                      </button>
                      <p className="text-[12px] text-ios-gray">
                        支持格式: .docx, .txt, .md
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
                    placeholder="在此粘贴文档内容..."
                    className="w-full h-64 px-4 py-3 bg-gray-50 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all text-[16px] leading-relaxed text-black placeholder-gray-400 border-none outline-none resize-none"
                  />
                  <div className="absolute bottom-3 right-3 text-[12px] text-ios-gray bg-white/80 px-2 py-1 rounded-md backdrop-blur-sm">
                    {text.length} 字符
                  </div>
                </div>
              )}

              {/* Options */}
              <div className="mt-5 space-y-4">
                {/* Spec Selection */}
                <div>
                  <label className="block text-[13px] font-medium text-ios-gray mb-2 ml-1 uppercase tracking-wide">
                    排版规范
                  </label>
                  <select
                    value={selectedSpec}
                    onChange={(e) => {
                      const value = e.target.value;
                      // 检查是否选择了保存的规范
                      if (value.startsWith('saved_')) {
                        const specId = parseInt(value.replace('saved_', ''), 10);
                        const savedSpec = savedSpecs.find((s) => s.id === specId);
                        if (savedSpec) {
                          handleSelectSavedSpec(savedSpec);
                          return;
                        }
                      }
                      setSelectedSpec(value);
                      if (value !== '_custom_') {
                        setCustomSpecJson(null);
                      }
                    }}
                    className="w-full px-3 py-2.5 bg-gray-50 rounded-xl border-none text-[15px] text-black focus:ring-2 focus:ring-blue-500/20"
                  >
                    {customSpecJson && (
                      <option value="_custom_">
                        ✨ 自定义规范{passedSpecName ? `: ${passedSpecName}` : ''}
                      </option>
                    )}
                    <optgroup label="内置规范">
                      {specs.map((spec) => (
                        <option key={spec} value={spec}>{spec}</option>
                      ))}
                    </optgroup>
                    {savedSpecs.length > 0 && (
                      <optgroup label="保存的规范">
                        {savedSpecs.map((spec) => (
                          <option
                            key={`saved_${spec.id}`}
                            value={`saved_${spec.id}`}
                          >
                            {spec.name}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                  {!hasWorkflowData && (
                    <div className="mt-2 flex gap-2">
                      <Link
                        to="/spec-generator"
                        className="text-[12px] text-blue-600 hover:text-blue-700 flex items-center gap-1"
                      >
                        <Sparkles className="w-3 h-3" />
                        创建自定义规范
                      </Link>
                    </div>
                  )}
                </div>

                {/* Toggles */}
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeCover}
                      onChange={(e) => setIncludeCover(e.target.checked)}
                      className="w-4 h-4 text-blue-500 rounded focus:ring-blue-500"
                    />
                    <span className="text-[14px] text-black">封面页</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeToc}
                      onChange={(e) => setIncludeToc(e.target.checked)}
                      className="w-4 h-4 text-blue-500 rounded focus:ring-blue-500"
                    />
                    <span className="text-[14px] text-black">目录页</span>
                  </label>
                </div>
              </div>

              {/* Submit Button */}
              <div className="mt-5 flex justify-end">
                <button
                  onClick={handleSubmit}
                  disabled={(inputMode === 'text' && !text.trim()) || (inputMode === 'file' && !file) || activeJob || isSubmitting}
                  className="flex items-center gap-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3 px-8 rounded-xl transition-all active:scale-[0.98] shadow-sm text-[17px]"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      处理中...
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 fill-current" />
                      开始排版
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Active Job Progress */}
            {activeJob && jobs.find(j => j.job_id === activeJob) && (
              <div className="bg-white rounded-2xl shadow-ios p-5 border border-blue-100">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-[17px] font-bold text-black flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                    处理中
                  </h2>
                  <span className="text-[13px] font-medium px-2 py-1 bg-blue-50 text-blue-600 rounded-md">
                    {jobs.find(j => j.job_id === activeJob)?.phase || '运行中'}
                  </span>
                </div>

                {(() => {
                  const job = jobs.find(j => j.job_id === activeJob);
                  return (
                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-[13px] mb-2 font-medium">
                          <span className="text-ios-gray">
                            {job?.message || '正在处理文档...'}
                          </span>
                          <span className="text-blue-600">
                            {((job?.progress || 0) * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full transition-all duration-500 ease-out"
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
                    历史记录
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
                      暂无任务
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
                            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                          )}
                          {job.status === 'failed' && (
                            <AlertCircle className="w-4 h-4 text-ios-red" />
                          )}
                          <span className={`text-[13px] font-medium ${
                            job.status === 'completed' ? 'text-black' :
                            job.status === 'running' || job.status === 'pending' ? 'text-blue-600' :
                            job.status === 'failed' ? 'text-ios-red' : 'text-ios-gray'
                          }`}>
                            {job.status === 'completed' && '已完成'}
                            {job.status === 'running' && '运行中'}
                            {job.status === 'pending' && '等待中'}
                            {job.status === 'failed' && '失败'}
                          </span>
                        </div>

                        <span className="text-[11px] text-ios-gray/70 font-medium">
                          {new Date(job.created_at).toLocaleDateString()}
                        </span>
                      </div>

                      <p className="text-[13px] text-ios-gray leading-snug line-clamp-2 mb-2 pr-6">
                        {job.input_file_name || job.output_filename || '文本输入'}
                      </p>

                      {(job.status === 'running' || job.status === 'pending') && (
                        <div className="w-full bg-gray-100 rounded-full h-1 mb-1">
                          <div
                            className="bg-blue-500 h-1 rounded-full"
                            style={{ width: `${(job.progress || 0) * 100}%` }}
                          />
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="flex items-center justify-between mt-1">
                        {job.status === 'completed' && (
                          <button
                            onClick={() => handleDownload(job)}
                            className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" />
                            下载
                          </button>
                        )}
                        <button
                          onClick={(event) => handleDeleteJob(event, job)}
                          className="p-1.5 text-gray-300 hover:text-ios-red hover:bg-red-50 rounded-lg transition-colors ml-auto"
                          title="删除"
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
