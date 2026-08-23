import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authHeaders } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import {
  Building2,
  Users,
  Plus,
  ArrowLeft,
  Edit,
  Trash2,
  Shield,
  Check,
  X,
  Key,
  UserPlus,
  Settings,
  Bot,
  MessageSquare,
  Save,
  BarChart3,
  Calendar,
  DollarSign,
  FileText,
  Loader2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Activity,
  Database,
  Upload,
  Image as ImageIcon,
  Package,
} from 'lucide-react';

import { getApiUrl } from '../utils/apiUrl';
import TutorDashboard from './TutorDashboard';
import IntegrationsHealthPanel from './IntegrationsHealthPanel';
import CostReportPanel from '../components/admin/CostReportPanel';
import DataMigrationPanel from '../components/admin/DataMigrationPanel';
import PlatesCleanupPanel from '../components/admin/PlatesCleanupPanel';
import BrandLibraryDialog from '../components/admin/BrandLibraryDialog';
import BatchExportPanel from '../components/admin/BatchExportPanel';
import GameQuestionBankPanel from '../components/admin/GameQuestionBankPanel';
import { Palette, Eraser } from 'lucide-react';
const API_URL = getApiUrl();

export default function Admin() {
  const navigate = useNavigate();
  const { user, isSuperAdmin, isCompanyAdmin, logout } = useAuth();
  
  const [activeTab, setActiveTab] = useState('companies');
  const [companies, setCompanies] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Modal states
  const [showCompanyModal, setShowCompanyModal] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);
  const [editingCompany, setEditingCompany] = useState(null);
  const [editingUser, setEditingUser] = useState(null);
  
  // Form states
  const [companyForm, setCompanyForm] = useState({ name: '', slug: '', maxUsers: 10, maxProjects: 100 });
  const [userForm, setUserForm] = useState({ name: '', email: '', password: '', roles: ['editor'], companyId: '' });
  
  // Tutor states
  const [tutorSettings, setTutorSettings] = useState({
    enabled: true,
    tutorName: 'Tutor IA',
    avatarUrl: '',
    messageLimit: 50,
    suggestedQuestions: [],
    systemPrompt: '',
    apiUrl: '',
    provider: 'openai',
    model: '',
    configured: false,
    publicEnabled: false
  });
  const [newSuggestion, setNewSuggestion] = useState('');
  const [tutorLoading, setTutorLoading] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  
  // Reports states
  const [reports, setReports] = useState([]);
  const [leonardoSummary, setLeonardoSummary] = useState(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [expandedCompany, setExpandedCompany] = useState(null);
  // Brand Library dialog state
  const [brandLibCompany, setBrandLibCompany] = useState(null);

  useEffect(() => {
    if (!isCompanyAdmin) {
      navigate('/');
      return;
    }
    fetchData();
    fetchTutorSettings();
  }, [isCompanyAdmin, navigate]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = async () => {
    setLoading(true);
    try {
      if (isSuperAdmin) {
        const compRes = await fetch(`${API_URL}/api/companies`, { headers: authHeaders(), credentials: 'include' });
        if (compRes.ok) setCompanies(await compRes.json());
      }
      
      const userRes = await fetch(`${API_URL}/api/users`, { headers: authHeaders(), credentials: 'include' });
      if (userRes.ok) setUsers(await userRes.json());
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTutorSettings = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/tutor-settings`, { headers: authHeaders(), credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setTutorSettings(prev => ({ ...prev, ...data }));
      }
    } catch (e) { console.error('Tutor settings fetch error:', e); }
  };

  const saveTutorSettings = async () => {
    setTutorLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/tutor-settings`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify(tutorSettings)
      });
      if (res.ok) toast.success('Configuracoes do Tutor IA salvas!');
      else toast.error('Erro ao salvar configuracoes');
    } catch (e) { toast.error('Erro ao salvar'); }
    finally { setTutorLoading(false); }
  };

  // Convert an uploaded image into a data-URI so it can be embedded straight
  // into exported SCORM/HTML packages (no external host needed — works
  // offline inside any LMS). Cap at ~2MB to keep the settings doc small.
  const handleAvatarUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Envie um arquivo de imagem (PNG, JPG, WEBP)');
      return;
    }
    const MAX_BYTES = 2 * 1024 * 1024;
    if (file.size > MAX_BYTES) {
      toast.error('Imagem muito grande (máx. 2 MB)');
      return;
    }
    setAvatarUploading(true);
    try {
      const dataUri = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('read-error'));
        reader.readAsDataURL(file);
      });
      setTutorSettings(prev => ({ ...prev, avatarUrl: dataUri }));
      toast.success('Avatar carregado. Clique em Salvar para aplicar.');
    } catch (err) {
      toast.error('Não foi possível ler o arquivo');
    } finally {
      setAvatarUploading(false);
      // Allow re-selecting the same file
      if (e.target) e.target.value = '';
    }
  };

  const removeAvatar = () => {
    setTutorSettings(prev => ({ ...prev, avatarUrl: '' }));
  };

  const fetchReports = async () => {
    setReportsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/reports`, { headers: authHeaders(), credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setReports(data.reports || []);
        setLeonardoSummary(data.leonardo || null);
      } else {
        toast.error('Erro ao carregar relatórios');
      }
    } catch (e) { 
      console.error('Reports fetch error:', e); 
      toast.error('Erro ao carregar relatórios');
    }
    finally { setReportsLoading(false); }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toLocaleDateString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch { return dateStr; }
  };

  const addSuggestion = () => {
    if (newSuggestion.trim()) {
      setTutorSettings(prev => ({
        ...prev,
        suggestedQuestions: [...prev.suggestedQuestions, newSuggestion.trim()]
      }));
      setNewSuggestion('');
    }
  };

  const removeSuggestion = (index) => {
    setTutorSettings(prev => ({
      ...prev,
      suggestedQuestions: prev.suggestedQuestions.filter((_, i) => i !== index)
    }));
  };

  // Company CRUD
  const handleSaveCompany = async () => {
    try {
      const url = editingCompany 
        ? `${API_URL}/api/companies/${editingCompany.id}`
        : `${API_URL}/api/companies`;
      
      const res = await fetch(url, {
        method: editingCompany ? 'PUT' : 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify(companyForm)
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail);
      }

      toast.success(editingCompany ? 'Empresa atualizada!' : 'Empresa criada!');
      setShowCompanyModal(false);
      setEditingCompany(null);
      setCompanyForm({ name: '', slug: '', maxUsers: 10, maxProjects: 100 });
      fetchData();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleDeleteCompany = async (company) => {
    if (!confirm(`Excluir permanentemente a empresa "${company.name}" e TODOS os seus usuários?\n\nEsta ação não pode ser desfeita.`)) return;
    
    try {
      const res = await fetch(`${API_URL}/api/companies/${company.id}`, {
        method: 'DELETE',
        headers: authHeaders(),
        credentials: 'include'
      });
      
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Erro ao excluir empresa');
      }
      
      toast.success('Empresa e seus usuários excluídos permanentemente');
      fetchData();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleUpdatePermissions = async (company, permission, value) => {
    try {
      const newPermissions = { ...company.permissions, [permission]: value };
      
      const res = await fetch(`${API_URL}/api/companies/${company.id}`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify({ permissions: newPermissions })
      });

      if (!res.ok) throw new Error('Erro ao atualizar permissões');
      
      toast.success('Permissões atualizadas');
      fetchData();
    } catch (error) {
      toast.error(error.message);
    }
  };

  // User CRUD
  const handleSaveUser = async () => {
    try {
      const url = editingUser 
        ? `${API_URL}/api/users/${editingUser.user_id}`
        : `${API_URL}/api/users`;
      
      const body = editingUser 
        ? { name: userForm.name, roles: userForm.roles, ...(userForm.password ? { password: userForm.password } : {}) }
        : userForm;

      const res = await fetch(url, {
        method: editingUser ? 'PUT' : 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        let detail = '';
        try { detail = (await res.clone().json()).detail; } catch {
          try { detail = await res.clone().text(); } catch {
            // Status-based fallback when body stream is consumed by platform interceptor
            if (res.status === 400) detail = 'Dados invalidos ou email ja existe';
            else if (res.status === 403) detail = 'Sem permissao';
            else if (res.status === 404) detail = 'Nao encontrado';
            else detail = `Erro ${res.status}`;
          }
        }
        throw new Error(detail || `Erro ${res.status}`);
      }

      toast.success(editingUser ? 'Usuario atualizado!' : 'Usuario criado!');
      setShowUserModal(false);
      setEditingUser(null);
      setUserForm({ name: '', email: '', password: '', roles: ['editor'], companyId: user?.companyId || '' });
      fetchData();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleDeleteUser = async (targetUser) => {
    if (!confirm(`Excluir permanentemente o usuário "${targetUser.name}" (${targetUser.email})?\n\nEsta ação não pode ser desfeita.`)) return;
    
    try {
      const res = await fetch(`${API_URL}/api/users/${targetUser.user_id}`, {
        method: 'DELETE',
        headers: authHeaders(),
        credentials: 'include'
      });
      
      if (!res.ok) {
        const clone = res.clone();
        let detail = 'Erro ao excluir usuario';
        try { const d = await clone.json(); detail = d.detail || detail; } catch {}
        throw new Error(detail);
      }
      
      toast.success('Usuario excluido permanentemente');
      fetchData();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const openEditCompany = (company) => {
    setEditingCompany(company);
    setCompanyForm({
      name: company.name,
      slug: company.slug,
      maxUsers: company.maxUsers,
      maxProjects: company.maxProjects
    });
    setShowCompanyModal(true);
  };

  const openEditUser = (targetUser) => {
    setEditingUser(targetUser);
    setUserForm({
      name: targetUser.name,
      email: targetUser.email,
      password: '',
      roles: targetUser.roles || [targetUser.role || 'editor'],
      companyId: targetUser.companyId
    });
    setShowUserModal(true);
  };

  const openNewUser = () => {
    setEditingUser(null);
    setUserForm({
      name: '',
      email: '',
      password: '',
      roles: ['editor'],
      companyId: isSuperAdmin ? (companies[0]?.id || '') : user?.companyId
    });
    setShowUserModal(true);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Settings className="w-6 h-6" />
              Administração
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-slate-400 text-sm">
              {user?.name} ({(user?.roles || [user?.role]).includes('super_admin') ? 'Super Admin' : 'Admin'})
            </span>
            <Button variant="outline" size="sm" onClick={logout}>
              Sair
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex flex-wrap gap-4 mb-8">
          {isSuperAdmin && (
            <Button
              variant={activeTab === 'companies' ? 'default' : 'outline'}
              onClick={() => setActiveTab('companies')}
              className="gap-2"
            >
              <Building2 className="w-4 h-4" />
              Empresas
            </Button>
          )}
          <Button
            variant={activeTab === 'users' ? 'default' : 'outline'}
            onClick={() => setActiveTab('users')}
            className="gap-2"
          >
            <Users className="w-4 h-4" />
            Usuarios
          </Button>
          <Button
            variant={activeTab === 'game_questions' ? 'default' : 'outline'}
            onClick={() => setActiveTab('game_questions')}
            className="gap-2"
            data-testid="tab-game-questions"
          >
            <Database className="w-4 h-4" />
            Questões dos Jogos
          </Button>
          <Button
            variant={activeTab === 'tutor' ? 'default' : 'outline'}
            onClick={() => setActiveTab('tutor')}
            className="gap-2"
          >
            <Bot className="w-4 h-4" />
            Tutor IA
          </Button>
          <Button
            variant={activeTab === 'reports' ? 'default' : 'outline'}
            onClick={() => { setActiveTab('reports'); if (reports.length === 0) fetchReports(); }}
            className="gap-2"
          >
            <BarChart3 className="w-4 h-4" />
            Relatorios
          </Button>
          <Button
            variant={activeTab === 'tutor_dashboard' ? 'default' : 'outline'}
            onClick={() => setActiveTab('tutor_dashboard')}
            className="gap-2"
            data-testid="tab-tutor-dashboard"
          >
            <MessageSquare className="w-4 h-4" />
            Dashboard Tutor
          </Button>
          {isSuperAdmin && (
            <Button
              variant={activeTab === 'integrations_health' ? 'default' : 'outline'}
              onClick={() => setActiveTab('integrations_health')}
              className="gap-2"
              data-testid="tab-integrations-health"
            >
              <Activity className="w-4 h-4" />
              Integracoes
            </Button>
          )}
          {isSuperAdmin && (
            <Button
              variant={activeTab === 'cost_report' ? 'default' : 'outline'}
              onClick={() => setActiveTab('cost_report')}
              className="gap-2"
              data-testid="tab-cost-report"
            >
              <DollarSign className="w-4 h-4" />
              Custos por Empresa
            </Button>
          )}
          {isSuperAdmin && (
            <Button
              variant={activeTab === 'data_migration' ? 'default' : 'outline'}
              onClick={() => setActiveTab('data_migration')}
              className="gap-2"
              data-testid="tab-data-migration"
            >
              <Database className="w-4 h-4" />
              Migracao
            </Button>
          )}
          {isSuperAdmin && (
            <Button
              variant={activeTab === 'plates_cleanup' ? 'default' : 'outline'}
              onClick={() => setActiveTab('plates_cleanup')}
              className="gap-2"
              data-testid="tab-plates-cleanup"
            >
              <Eraser className="w-4 h-4" />
              Limpeza
            </Button>
          )}
          {/* Batch SCORM export — visible to super_admin (all courses) and
              company_admin (only their company's courses). Backend RBAC does
              the filtering — this is only a visibility gate. */}
          <Button
            variant={activeTab === 'batch_export' ? 'default' : 'outline'}
            onClick={() => setActiveTab('batch_export')}
            className="gap-2"
            data-testid="tab-batch-export"
          >
            <Package className="w-4 h-4" />
            Exportação em Lote
          </Button>
        </div>

        {/* Batch SCORM Export Tab */}
        {activeTab === 'batch_export' && <BatchExportPanel />}

        {activeTab === 'game_questions' && (
          <GameQuestionBankPanel user={user} isSuperAdmin={isSuperAdmin} companies={companies} />
        )}

        {/* Cost Report Tab */}
        {activeTab === 'cost_report' && isSuperAdmin && <CostReportPanel />}

        {/* Data Migration Tab */}
        {activeTab === 'data_migration' && isSuperAdmin && <DataMigrationPanel />}

        {/* Plates Cleanup Tab */}
        {activeTab === 'plates_cleanup' && isSuperAdmin && <PlatesCleanupPanel />}

        {/* Companies Tab */}
        {activeTab === 'companies' && isSuperAdmin && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-white">Empresas</h2>
              <Button onClick={() => { setEditingCompany(null); setCompanyForm({ name: '', slug: '', maxUsers: 10, maxProjects: 100 }); setShowCompanyModal(true); }} className="gap-2">
                <Plus className="w-4 h-4" />
                Nova Empresa
              </Button>
            </div>

            <div className="grid gap-4">
              {companies.map(company => (
                <div key={company.id} className="bg-slate-800 rounded-lg p-6 border border-slate-700">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-white">{company.name}</h3>
                      <p className="text-slate-400 text-sm">/{company.slug}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setBrandLibCompany(company)}
                        data-testid={`open-brand-library-${company.id}`}
                        title="Biblioteca de Marca"
                      >
                        <Palette className="w-4 h-4 text-indigo-400" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => openEditCompany(company)}>
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDeleteCompany(company)}>
                        <Trash2 className="w-4 h-4 text-red-400" />
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-slate-700/50 rounded p-3">
                      <p className="text-slate-400 text-xs">Usuários</p>
                      <p className="text-white font-semibold">{company.userCount || 0} / {company.maxUsers}</p>
                    </div>
                    <div className="bg-slate-700/50 rounded p-3">
                      <p className="text-slate-400 text-xs">Projetos</p>
                      <p className="text-white font-semibold">{company.projectCount || 0} / {company.maxProjects}</p>
                    </div>
                    <div className="bg-slate-700/50 rounded p-3">
                      <p className="text-slate-400 text-xs">Status</p>
                      <p className={`font-semibold ${company.isActive ? 'text-green-400' : 'text-red-400'}`}>
                        {company.isActive ? 'Ativo' : 'Inativo'}
                      </p>
                    </div>
                  </div>

                  {/* Permissions */}
                  <div className="border-t border-slate-700 pt-4">
                    <p className="text-slate-400 text-sm mb-3 flex items-center gap-2">
                      <Key className="w-4 h-4" />
                      Permissões de API
                    </p>
                    <div className="flex gap-4 flex-wrap">
                      <label className="flex items-center gap-2 text-white cursor-pointer">
                        <input
                          type="checkbox"
                          checked={company.permissions?.agentAccess || false}
                          onChange={(e) => handleUpdatePermissions(company, 'agentAccess', e.target.checked)}
                          className="rounded"
                          data-testid={`perm-agent-${company.id}`}
                        />
                        Agente IA
                      </label>
                      <label className="flex items-center gap-2 text-white cursor-pointer">
                        <input
                          type="checkbox"
                          checked={company.permissions?.heygen || false}
                          onChange={(e) => handleUpdatePermissions(company, 'heygen', e.target.checked)}
                          className="rounded"
                        />
                        HeyGen (Avatar IA)
                      </label>
                      <label className="flex items-center gap-2 text-white cursor-pointer">
                        <input
                          type="checkbox"
                          checked={company.permissions?.elevenlabs || false}
                          onChange={(e) => handleUpdatePermissions(company, 'elevenlabs', e.target.checked)}
                          className="rounded"
                        />
                        ElevenLabs (TTS)
                      </label>
                    </div>
                  </div>
                </div>
              ))}

              {companies.length === 0 && (
                <div className="text-center py-12 text-slate-400">
                  Nenhuma empresa cadastrada
                </div>
              )}
            </div>
          </div>
        )}

        {/* Users Tab */}
        {activeTab === 'users' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-white">Usuários</h2>
              <Button onClick={openNewUser} className="gap-2">
                <UserPlus className="w-4 h-4" />
                Novo Usuário
              </Button>
            </div>

            <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-700">
                  <tr>
                    <th className="text-left p-4 text-slate-300 font-medium">Nome</th>
                    <th className="text-left p-4 text-slate-300 font-medium">Email</th>
                    <th className="text-left p-4 text-slate-300 font-medium">Função</th>
                    {isSuperAdmin && <th className="text-left p-4 text-slate-300 font-medium">Empresa</th>}
                    <th className="text-left p-4 text-slate-300 font-medium">Status</th>
                    <th className="text-right p-4 text-slate-300 font-medium">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.user_id} className="border-t border-slate-700 hover:bg-slate-700/50">
                      <td className="p-4 text-white">{u.name}</td>
                      <td className="p-4 text-slate-300">{u.email}</td>
                      <td className="p-4">
                        <div className="flex flex-wrap gap-1">
                          {(u.roles || [u.role]).map(r => (
                            <span key={r} className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              r === 'super_admin' ? 'bg-purple-500/20 text-purple-400' :
                              r === 'company_admin' ? 'bg-blue-500/20 text-blue-400' :
                              r === 'aprovador' ? 'bg-amber-500/20 text-amber-400' :
                              'bg-slate-500/20 text-slate-400'
                            }`}>
                              {r === 'super_admin' ? 'Super Admin' : r === 'company_admin' ? 'Admin' : r === 'aprovador' ? 'Aprovador' : 'Editor'}
                            </span>
                          ))}
                        </div>
                      </td>
                      {isSuperAdmin && (
                        <td className="p-4 text-slate-300">
                          {companies.find(c => c.id === u.companyId)?.name || '-'}
                        </td>
                      )}
                      <td className="p-4">
                        {u.isActive ? (
                          <span className="text-green-400 flex items-center gap-1">
                            <Check className="w-4 h-4" /> Ativo
                          </span>
                        ) : (
                          <span className="text-red-400 flex items-center gap-1">
                            <X className="w-4 h-4" /> Inativo
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-right">
                        <Button variant="ghost" size="icon" onClick={() => openEditUser(u)}>
                          <Edit className="w-4 h-4" />
                        </Button>
                        {u.user_id !== user?.user_id && (
                          <Button variant="ghost" size="icon" onClick={() => handleDeleteUser(u)}>
                            <Trash2 className="w-4 h-4 text-red-400" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {users.length === 0 && (
                <div className="text-center py-12 text-slate-400">
                  Nenhum usuário cadastrado
                </div>
              )}
            </div>
          </div>
        )}

      {/* Tutor IA Tab */}
      {activeTab === 'tutor' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-white">Tutor IA</h2>
            <Button onClick={saveTutorSettings} disabled={tutorLoading} className="gap-2" data-testid="save-tutor-settings">
              <Save className="w-4 h-4" />
              {tutorLoading ? 'Salvando...' : 'Salvar'}
            </Button>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 space-y-6">
            <div
              className={`rounded-lg border p-4 ${
                tutorSettings.configured && tutorSettings.publicEnabled
                  ? 'border-emerald-500/40 bg-emerald-500/10'
                  : 'border-amber-500/40 bg-amber-500/10'
              }`}
              data-testid="tutor-openai-status"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-white font-medium">Integração OpenAI</h3>
                  <p className="text-sm text-slate-300 mt-1">
                    {tutorSettings.configured && tutorSettings.publicEnabled
                      ? `Conectada e ativa — modelo ${tutorSettings.model || 'configurado no servidor'}`
                      : 'Aguardando OPENAI_API_KEY e ativação do Tutor no backend'}
                  </p>
                </div>
                <span className={`text-xs font-semibold px-3 py-1 rounded-full ${
                  tutorSettings.configured && tutorSettings.publicEnabled
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : 'bg-amber-500/20 text-amber-300'
                }`}>
                  {tutorSettings.configured && tutorSettings.publicEnabled ? 'Pronto' : 'Configuração pendente'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                A chave permanece somente no Render e nunca é incluída no curso exportado.
              </p>
            </div>

            {/* Enable/Disable */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-white font-medium">Ativar Tutor IA</h3>
                <p className="text-sm text-slate-400">Inclui um chat de IA nos pacotes SCORM exportados</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer" data-testid="tutor-enabled-toggle">
                <input
                  type="checkbox"
                  checked={tutorSettings.enabled}
                  onChange={(e) => setTutorSettings(prev => ({ ...prev, enabled: e.target.checked }))}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-600 peer-focus:ring-2 peer-focus:ring-indigo-500 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
              </label>
            </div>

            {/* Tutor Name */}
            <div>
              <label className="block text-sm text-slate-300 mb-1">Nome do Tutor</label>
              <Input
                value={tutorSettings.tutorName}
                onChange={(e) => setTutorSettings(prev => ({ ...prev, tutorName: e.target.value }))}
                placeholder="Ex: Tutor IA, Professor Virtual"
                data-testid="tutor-name-input"
              />
            </div>

            {/* Tutor Avatar */}
            <div data-testid="tutor-avatar-section">
              <label className="block text-sm text-slate-300 mb-2">Foto/Avatar do Tutor</label>
              <div className="flex items-center gap-4">
                <div
                  className="w-20 h-20 rounded-full overflow-hidden bg-slate-700 border-2 border-slate-600 flex items-center justify-center shrink-0"
                  data-testid="tutor-avatar-preview"
                >
                  {tutorSettings.avatarUrl ? (
                    <img src={tutorSettings.avatarUrl} alt="Avatar do Tutor" className="w-full h-full object-cover" />
                  ) : (
                    <ImageIcon className="w-8 h-8 text-slate-500" />
                  )}
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <label
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white text-sm cursor-pointer transition-colors disabled:opacity-50"
                      data-testid="tutor-avatar-upload-label"
                    >
                      {avatarUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      {avatarUploading ? 'Carregando...' : 'Escolher imagem'}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/jpg,image/webp"
                        className="hidden"
                        onChange={handleAvatarUpload}
                        disabled={avatarUploading}
                        data-testid="tutor-avatar-input"
                      />
                    </label>
                    {tutorSettings.avatarUrl && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={removeAvatar}
                        data-testid="tutor-avatar-remove"
                      >
                        <X className="w-3 h-3 mr-1" /> Remover
                      </Button>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">
                    PNG, JPG ou WEBP até 2 MB. A imagem é embutida no curso exportado (funciona offline em qualquer LMS).
                  </p>
                </div>
              </div>
            </div>

            {/* Message Limit */}
            <div>
              <label className="block text-sm text-slate-300 mb-1">Limite de mensagens por sessao</label>
              <Input
                type="number"
                value={tutorSettings.messageLimit}
                onChange={(e) => setTutorSettings(prev => ({ ...prev, messageLimit: parseInt(e.target.value) || 50 }))}
                min={1}
                max={500}
                data-testid="tutor-message-limit"
              />
            </div>

            {/* API URL for Export */}
            <div>
              <label className="block text-sm text-slate-300 mb-1">URL do Backend (para exportacao SCORM/HTML)</label>
              <Input
                value={tutorSettings.apiUrl || ''}
                onChange={(e) => setTutorSettings(prev => ({ ...prev, apiUrl: e.target.value }))}
                placeholder="Ex: https://seu-dominio.com (deixe vazio para usar padrao)"
                data-testid="tutor-api-url"
              />
              <p className="text-xs text-slate-500 mt-1">URL usada pelo Tutor IA nos cursos exportados. Deixe vazio para usar a URL padrao do sistema.</p>
            </div>

            {/* System Prompt */}
            <div>
              <label className="block text-sm text-slate-300 mb-1">Instrucoes adicionais (opcional)</label>
              <textarea
                value={tutorSettings.systemPrompt}
                onChange={(e) => setTutorSettings(prev => ({ ...prev, systemPrompt: e.target.value }))}
                placeholder="Ex: Responda sempre em portugues formal. Foque em exemplos praticos..."
                rows={3}
                className="w-full px-3 py-2 rounded-md bg-slate-700 border border-slate-600 text-white text-sm resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                data-testid="tutor-system-prompt"
              />
            </div>

            {/* Suggested Questions */}
            <div>
              <label className="block text-sm text-slate-300 mb-2">Sugestoes de perguntas</label>
              <p className="text-xs text-slate-500 mb-3">Perguntas pre-definidas que aparecem no chat para o aluno clicar</p>
              
              <div className="flex gap-2 mb-3">
                <Input
                  value={newSuggestion}
                  onChange={(e) => setNewSuggestion(e.target.value)}
                  placeholder="Ex: Qual o objetivo deste curso?"
                  onKeyDown={(e) => e.key === 'Enter' && addSuggestion()}
                  data-testid="tutor-new-suggestion-input"
                />
                <Button onClick={addSuggestion} variant="outline" className="gap-1 shrink-0" data-testid="tutor-add-suggestion">
                  <Plus className="w-4 h-4" /> Adicionar
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                {tutorSettings.suggestedQuestions.map((q, i) => (
                  <span key={i} className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-600/20 text-indigo-300 text-sm border border-indigo-500/30">
                    <MessageSquare className="w-3 h-3" />
                    {q}
                    <button onClick={() => removeSuggestion(i)} className="ml-1 hover:text-red-400" data-testid={`tutor-remove-suggestion-${i}`}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {tutorSettings.suggestedQuestions.length === 0 && (
                  <p className="text-sm text-slate-500 italic">Nenhuma sugestao adicionada</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reports Tab */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-white">Relatórios de Uso</h2>
            <Button 
              onClick={fetchReports} 
              disabled={reportsLoading} 
              variant="outline" 
              className="gap-2"
              data-testid="refresh-reports-btn"
            >
              {reportsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
              {reportsLoading ? 'Carregando...' : 'Atualizar'}
            </Button>
          </div>

          {/* Leonardo AI Usage Summary */}
          {leonardoSummary && leonardoSummary.totalGenerations > 0 && (
            <div className="bg-gradient-to-r from-fuchsia-950/40 to-violet-950/40 border border-fuchsia-800/30 rounded-xl p-5" data-testid="leonardo-usage-card">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-5 h-5 text-fuchsia-400" />
                <h3 className="text-base font-semibold text-fuchsia-200">Leonardo AI - Uso de Imagens</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-fuchsia-600/20 text-fuchsia-300 ml-auto">{leonardoSummary.model}</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-fuchsia-300">{leonardoSummary.completedGenerations}</p>
                  <p className="text-[11px] text-slate-400">Imagens Geradas</p>
                </div>
                <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-amber-300">{leonardoSummary.pendingGenerations}</p>
                  <p className="text-[11px] text-slate-400">Pendentes</p>
                </div>
                <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                  <DollarSign className="w-4 h-4 mx-auto text-green-400 mb-0.5" />
                  <p className="text-2xl font-bold text-green-300">${leonardoSummary.totalCostUSD.toFixed(4)}</p>
                  <p className="text-[11px] text-slate-400">Custo USD</p>
                </div>
                <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                  <DollarSign className="w-4 h-4 mx-auto text-emerald-400 mb-0.5" />
                  <p className="text-2xl font-bold text-emerald-300">R$ {leonardoSummary.totalCostBRL.toFixed(2)}</p>
                  <p className="text-[11px] text-slate-400">Custo BRL</p>
                </div>
              </div>
              <p className="text-[10px] text-fuchsia-400/50 mt-3 text-center">
                Custo por imagem: ${leonardoSummary.costPerImage} USD | Total de gerações: {leonardoSummary.totalGenerations}
              </p>
            </div>
          )}

          {reportsLoading && reports.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
            </div>
          ) : reports.length === 0 ? (
            <div className="bg-slate-800 rounded-lg p-12 text-center border border-slate-700">
              <BarChart3 className="w-12 h-12 mx-auto text-slate-500 mb-4" />
              <p className="text-slate-400">Nenhum dado de uso encontrado</p>
              <p className="text-sm text-slate-500 mt-2">Os dados aparecem após a criação de cursos pelo Agente IA</p>
            </div>
          ) : (
            <div className="space-y-4">
              {reports.map((report, idx) => (
                <div 
                  key={report.company?.id || idx} 
                  className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden"
                  data-testid={`report-company-${report.company?.id || 'orphan'}`}
                >
                  {/* Company Header */}
                  <div 
                    className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-750"
                    onClick={() => setExpandedCompany(expandedCompany === report.company?.id ? null : report.company?.id)}
                  >
                    <div className="flex items-center gap-4">
                      <div className="bg-indigo-600/20 p-2 rounded-lg">
                        <Building2 className="w-5 h-5 text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-white">{report.company?.name}</h3>
                        <p className="text-sm text-slate-400">{report.company?.slug}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
                      {/* Stats Summary */}
                      <div className="flex items-center gap-6 text-sm">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-white">{report.stats?.totalCourses || 0}</div>
                          <div className="text-slate-400">Cursos</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-emerald-400">
                            R$ {(report.stats?.totalCostBRL || 0).toFixed(2)}
                          </div>
                          <div className="text-slate-400">Custo Total</div>
                        </div>
                      </div>
                      {expandedCompany === report.company?.id ? (
                        <ChevronUp className="w-5 h-5 text-slate-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {expandedCompany === report.company?.id && (
                    <div className="border-t border-slate-700 p-4 space-y-6">
                      {/* Stats Grid */}
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                          <FileText className="w-5 h-5 mx-auto text-blue-400 mb-1" />
                          <div className="text-xl font-bold text-white">{report.stats?.totalCourses || 0}</div>
                          <div className="text-xs text-slate-400">Cursos Total</div>
                          {report.courses && report.courses.length > 0 && (
                            <div className="flex flex-wrap justify-center gap-1 mt-1">
                              {(() => {
                                const agentCount = report.courses.filter(c => (c.source || (c.createdByAgent ? 'agent' : 'manual')) === 'agent').length;
                                const pptCount = report.courses.filter(c => c.source === 'ppt').length;
                                const manualCount = report.courses.length - agentCount - pptCount;
                                return <>
                                  {agentCount > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-600/20 text-emerald-300">{agentCount} IA</span>}
                                  {pptCount > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-600/20 text-blue-300">{pptCount} PPT</span>}
                                  {manualCount > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-slate-600/20 text-slate-300">{manualCount} Manual</span>}
                                </>;
                              })()}
                            </div>
                          )}
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                          <div className="w-5 h-5 mx-auto text-purple-400 mb-1 flex items-center justify-center">🖼️</div>
                          <div className="text-xl font-bold text-white">{report.stats?.totalAiImages || 0}</div>
                          <div className="text-xs text-slate-400">Imagens IA</div>
                        </div>
                        {(report.stats?.totalLeonardoImages || 0) > 0 && (
                          <div className="bg-fuchsia-950/30 border border-fuchsia-800/20 rounded-lg p-3 text-center">
                            <Sparkles className="w-5 h-5 mx-auto text-fuchsia-400 mb-1" />
                            <div className="text-xl font-bold text-fuchsia-200">{report.stats.totalLeonardoImages}</div>
                            <div className="text-xs text-fuchsia-400/70">Leonardo AI</div>
                          </div>
                        )}
                        <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                          <div className="w-5 h-5 mx-auto text-orange-400 mb-1 flex items-center justify-center">🔊</div>
                          <div className="text-xl font-bold text-white">{report.stats?.totalNarrations || 0}</div>
                          <div className="text-xs text-slate-400">Narracoes</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                          <DollarSign className="w-5 h-5 mx-auto text-green-400 mb-1" />
                          <div className="text-xl font-bold text-white">${report.stats?.totalCostUSD?.toFixed(4) || '0.00'}</div>
                          <div className="text-xs text-slate-400">Custo USD</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                          <DollarSign className="w-5 h-5 mx-auto text-emerald-400 mb-1" />
                          <div className="text-xl font-bold text-white">R$ {report.stats?.totalCostBRL?.toFixed(2) || '0.00'}</div>
                          <div className="text-xs text-slate-400">Custo BRL</div>
                        </div>
                      </div>

                      {/* Editors List */}
                      {report.editors && report.editors.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                            <Users className="w-4 h-4" /> Editores ({report.editors.length})
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {report.editors.map((editor, editorIdx) => (
                              <span 
                                key={editor.id || editorIdx}
                                className="px-3 py-1 bg-slate-700 rounded-full text-sm text-slate-300"
                              >
                                {editor.name} <span className="text-slate-500">({editor.email})</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Courses Table */}
                      {report.courses && report.courses.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                            <FileText className="w-4 h-4" /> Cursos Criados ({report.courses.length})
                          </h4>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b border-slate-700">
                                  <th className="text-left py-2 px-3 text-slate-400 font-medium">Curso</th>
                                  <th className="text-left py-2 px-3 text-slate-400 font-medium">Editor</th>
                                  <th className="text-left py-2 px-3 text-slate-400 font-medium">Origem</th>
                                  <th className="text-left py-2 px-3 text-slate-400 font-medium">Data</th>
                                </tr>
                              </thead>
                              <tbody>
                                {report.courses.map((course, courseIdx) => {
                                  const sourceLabels = { agent: 'Agente IA', ppt: 'PPT Import', manual: 'Manual' };
                                  const sourceColors = { agent: 'bg-emerald-600/20 text-emerald-300', ppt: 'bg-blue-600/20 text-blue-300', manual: 'bg-slate-600/20 text-slate-300' };
                                  const src = course.source || 'manual';
                                  return (
                                    <tr key={course.id || courseIdx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                                      <td className="py-2 px-3 text-white">{course.name || 'Sem nome'}</td>
                                      <td className="py-2 px-3 text-slate-300">{course.editorName || 'Desconhecido'}</td>
                                      <td className="py-2 px-3">
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${sourceColors[src] || sourceColors.manual}`}>
                                          {sourceLabels[src] || src}
                                        </span>
                                      </td>
                                      <td className="py-2 px-3 text-slate-400">{formatDate(course.createdAt)}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {(!report.courses || report.courses.length === 0) && (
                        <p className="text-sm text-slate-500 text-center py-4">Nenhum curso criado ainda</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      </div>

      {/* Tutor Dashboard Tab */}
      {activeTab === 'tutor_dashboard' && (
        <div className="max-w-5xl mx-auto px-4 pb-8">
          <TutorDashboard />
        </div>
      )}

      {/* Integrations Health Tab (Super Admin only) */}
      {activeTab === 'integrations_health' && isSuperAdmin && (
        <div className="max-w-7xl mx-auto px-4 pb-8">
          <IntegrationsHealthPanel />
        </div>
      )}

      {/* Company Modal */}
      {showCompanyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-6 w-full max-w-md border border-slate-700">
            <h3 className="text-xl font-bold text-white mb-4">
              {editingCompany ? 'Editar Empresa' : 'Nova Empresa'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-300 mb-1">Nome</label>
                <Input
                  value={companyForm.name}
                  onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
                  placeholder="Nome da empresa"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Slug (URL)</label>
                <Input
                  value={companyForm.slug}
                  onChange={(e) => setCompanyForm({ ...companyForm, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                  placeholder="empresa-exemplo"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Máx. Usuários</label>
                  <Input
                    type="number"
                    value={companyForm.maxUsers}
                    onChange={(e) => setCompanyForm({ ...companyForm, maxUsers: parseInt(e.target.value) })}
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Máx. Projetos</label>
                  <Input
                    type="number"
                    value={companyForm.maxProjects}
                    onChange={(e) => setCompanyForm({ ...companyForm, maxProjects: parseInt(e.target.value) })}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowCompanyModal(false)}>Cancelar</Button>
              <Button onClick={handleSaveCompany}>Salvar</Button>
            </div>
          </div>
        </div>
      )}

      {/* User Modal */}
      {showUserModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-6 w-full max-w-md border border-slate-700">
            <h3 className="text-xl font-bold text-white mb-4">
              {editingUser ? 'Editar Usuário' : 'Novo Usuário'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-300 mb-1">Nome</label>
                <Input
                  value={userForm.name}
                  onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
                  placeholder="Nome completo"
                />
              </div>
              {!editingUser && (
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Email</label>
                  <Input
                    type="email"
                    value={userForm.email}
                    onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                    placeholder="email@exemplo.com"
                  />
                </div>
              )}
              {editingUser && (
                <div className="text-sm text-slate-400 bg-slate-700/50 rounded-md px-3 py-2">
                  {editingUser.email}
                </div>
              )}
              <div>
                <label className="block text-sm text-slate-300 mb-1">
                  {editingUser ? 'Nova Senha (deixe vazio para manter a atual)' : 'Senha'}
                </label>
                <Input
                  type="password"
                  value={userForm.password}
                  onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                  placeholder={editingUser ? 'Deixe vazio para não alterar' : 'Mínimo 6 caracteres'}
                />
              </div>
              {isSuperAdmin && !editingUser && (
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Empresa</label>
                  <select
                    value={userForm.companyId}
                    onChange={(e) => setUserForm({ ...userForm, companyId: e.target.value })}
                    className="w-full h-10 px-3 rounded-md bg-slate-700 border border-slate-600 text-white"
                  >
                    <option value="">Selecione...</option>
                    {companies.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm text-slate-300 mb-2">Funcoes (multiplas)</label>
                <div className="space-y-2">
                  {[
                    { value: 'editor', label: 'Editor', desc: 'Criar e editar cursos' },
                    { value: 'aprovador', label: 'Aprovador', desc: 'Aprovar storyboards' },
                    ...((isSuperAdmin || (user?.roles || [user?.role]).includes('company_admin')) ? [{ value: 'company_admin', label: 'Admin da Empresa', desc: 'Gerenciar usuarios da empresa' }] : []),
                    ...(isSuperAdmin ? [{ value: 'super_admin', label: 'Super Admin', desc: 'Acesso total ao sistema' }] : []),
                  ].map(opt => (
                    <label key={opt.value} className={`flex items-center gap-3 p-2 rounded-lg border cursor-pointer transition-colors ${
                      userForm.roles.includes(opt.value)
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                    }`}>
                      <input
                        type="checkbox"
                        checked={userForm.roles.includes(opt.value)}
                        onChange={(e) => {
                          const newRoles = e.target.checked
                            ? [...userForm.roles, opt.value]
                            : userForm.roles.filter(r => r !== opt.value);
                          setUserForm({ ...userForm, roles: newRoles.length > 0 ? newRoles : ['editor'] });
                        }}
                        className="w-4 h-4 rounded border-slate-500 text-violet-500 focus:ring-violet-500 bg-slate-700"
                      />
                      <div>
                        <span className="text-sm text-white font-medium">{opt.label}</span>
                        <p className="text-[10px] text-slate-400">{opt.desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowUserModal(false)}>Cancelar</Button>
              <Button onClick={handleSaveUser}>Salvar</Button>
            </div>
          </div>
        </div>
      )}

      {/* Brand Library dialog (super_admin only) */}
      <BrandLibraryDialog
        open={!!brandLibCompany}
        onClose={() => setBrandLibCompany(null)}
        company={brandLibCompany}
      />
    </div>
  );
}
