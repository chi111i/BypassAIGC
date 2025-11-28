import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { Database, Table as TableIcon, Edit3, Trash2, RefreshCw, Search, X } from 'lucide-react';

const DatabaseManager = ({ adminToken }) => {
  const [loading, setLoading] = useState(false);
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState('');
  const [tableData, setTableData] = useState([]);
  const [tableColumns, setTableColumns] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingRecord, setEditingRecord] = useState(null);
  const [editFormData, setEditFormData] = useState({});

  useEffect(() => {
    fetchTables();
  }, []);

  useEffect(() => {
    if (selectedTable) {
      fetchTableData(selectedTable);
    }
  }, [selectedTable]);

  const fetchTables = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/admin/database/tables', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setTables(response.data.tables);
      if (response.data.tables.length > 0 && !selectedTable) {
        setSelectedTable(response.data.tables[0]);
      }
    } catch (error) {
      toast.error('获取表列表失败');
      console.error('Error fetching tables:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTableData = async (tableName) => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/admin/database/${tableName}`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      // 后端返回的是 items，不是 records
      const records = response.data.items || response.data.records || [];
      setTableData(records);
      if (records.length > 0) {
        setTableColumns(Object.keys(records[0]));
      } else {
        setTableColumns([]);
      }
    } catch (error) {
      toast.error('获取表数据失败');
      console.error('Error fetching table data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEditRecord = (record) => {
    setEditingRecord(record);
    setEditFormData({ ...record });
  };

  const handleSaveEdit = async () => {
    if (!editingRecord || !editingRecord.id) {
      toast.error('无效的记录ID');
      return;
    }

    try {
      await axios.put(
        `/api/admin/database/${selectedTable}/${editingRecord.id}`,
        editFormData,
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success('记录更新成功');
      setEditingRecord(null);
      setEditFormData({});
      fetchTableData(selectedTable);
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新记录失败');
    }
  };

  const handleDeleteRecord = async (recordId) => {
    if (!window.confirm('确定要删除这条记录吗?此操作不可撤销。')) {
      return;
    }

    try {
      await axios.delete(`/api/admin/database/${selectedTable}/${recordId}`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      toast.success('记录已删除');
      fetchTableData(selectedTable);
    } catch (error) {
      toast.error('删除记录失败');
    }
  };

  const formatValue = (value) => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (typeof value === 'string' && value.length > 50) {
      return value.substring(0, 50) + '...';
    }
    return String(value);
  };

  const filteredData = tableData.filter(record => {
    if (!searchTerm) return true;
    return Object.values(record).some(value =>
      String(value).toLowerCase().includes(searchTerm.toLowerCase())
    );
  });

  const getTableNameInChinese = (tableName) => {
    const nameMap = {
      'users': '用户表',
      'optimization_sessions': '优化会话表',
      'optimization_segments': '优化段落表',
      'system_settings': '系统设置表',
      'card_keys': '卡密表',
      'session_history': '会话历史表'
    };
    return nameMap[tableName] || tableName;
  };

  if (loading && !tableData.length) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 表选择器 */}
      <div className="bg-white rounded-2xl shadow-ios p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
            <Database className="w-5 h-5 text-blue-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">数据库管理</h3>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 items-end mb-4">
          <div className="flex-1 w-full">
            <label className="block text-sm font-medium text-gray-500 mb-2">
              选择数据表
            </label>
            <select
              value={selectedTable}
              onChange={(e) => setSelectedTable(e.target.value)}
              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
            >
              {tables.map(table => (
                <option key={table} value={table}>
                  {getTableNameInChinese(table)}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => fetchTableData(selectedTable)}
            disabled={loading}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-xl transition-all active:scale-[0.98] font-semibold text-sm shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新数据
          </button>
        </div>

        {/* 搜索框 */}
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索记录..."
            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
          />
        </div>
      </div>

      {/* 数据表格 */}
      <div className="bg-white rounded-2xl shadow-ios overflow-hidden border border-gray-100">
        {tableData.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <TableIcon className="w-8 h-8 text-gray-300" />
            </div>
            <p className="text-gray-500 font-medium">该表暂无数据</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50/50 border-b border-gray-100">
                <tr>
                  {tableColumns.map(column => (
                    <th
                      key={column}
                      className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {column}
                    </th>
                  ))}
                  <th className="px-6 py-4 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider sticky right-0 bg-gray-50/95 backdrop-blur-sm border-l border-gray-100">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredData.map((record, index) => (
                  <tr key={record.id || index} className="hover:bg-blue-50/30 transition-colors">
                    {tableColumns.map(column => (
                      <td key={column} className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {formatValue(record[column])}
                      </td>
                    ))}
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium sticky right-0 bg-white/95 backdrop-blur-sm border-l border-gray-100 group-hover:bg-blue-50/30 transition-colors">
                      <button
                        onClick={() => handleEditRecord(record)}
                        className="text-blue-600 hover:text-blue-800 p-1.5 hover:bg-blue-50 rounded-lg transition-colors mr-2"
                        title="编辑"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteRecord(record.id)}
                        className="text-red-600 hover:text-red-800 p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-6 py-4 bg-gray-50/50 border-t border-gray-100 text-sm font-medium text-gray-500 flex justify-between items-center">
          <span>共 {filteredData.length} 条记录</span>
        </div>
      </div>

      {/* 编辑弹窗 */}
      {editingRecord && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <h3 className="text-xl font-semibold text-gray-800">编辑记录</h3>
              <button
                onClick={() => {
                  setEditingRecord(null);
                  setEditFormData({});
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {tableColumns.map(column => (
                <div key={column}>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {column}
                  </label>
                  {column === 'id' ? (
                    <input
                      type="text"
                      value={editFormData[column] || ''}
                      disabled
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-600"
                    />
                  ) : typeof editFormData[column] === 'boolean' ? (
                    <select
                      value={editFormData[column] ? 'true' : 'false'}
                      onChange={(e) =>
                        setEditFormData({
                          ...editFormData,
                          [column]: e.target.value === 'true'
                        })
                      }
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={editFormData[column] || ''}
                      onChange={(e) =>
                        setEditFormData({
                          ...editFormData,
                          [column]: e.target.value
                        })
                      }
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  )}
                </div>
              ))}
            </div>

            <div className="sticky bottom-0 bg-gray-50 px-6 py-4 flex gap-4 border-t border-gray-200">
              <button
                onClick={() => {
                  setEditingRecord(null);
                  setEditFormData({});
                }}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSaveEdit}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DatabaseManager;
