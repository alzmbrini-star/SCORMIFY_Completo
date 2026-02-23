import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
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
  Save
} from 'lucide-react';

import { getApiUrl } from '../utils/apiUrl';
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
  const [userForm, setUserForm] = useState({ name: '', email: '', password: '', role: 'editor', companyId: '' });
  
  // Tutor states
  const [tutorSettings, setTutorSettings] = useState({
    enabled: true,
    tutorName: 'Tutor IA',
    messageLimit: 50,
    suggestedQuestions: [],
    systemPrompt: ''
  });
  const [newSuggestion, setNewSuggestion] = useState('');
  const [tutorLoading, setTutorLoading] = useState(false);

  useEffect(() => {
    if (!isCompanyAdmin) {
      navigate('/');
      return;
    }
    fetchData();
    fetchTutorSettings();
  }, [isCompanyAdmin, navigate]);

  const fetchData = async () => {
    setLoading(true);
    try {
      if (isSuperAdmin) {
        const compRes = await fetch(`${API_URL}/api/companies`, { credentials: 'include' });
        if (compRes.ok) setCompanies(await compRes.json());
      }
      
      const userRes = await fetch(`${API_URL}/api/users`, { credentials: 'include' });
      if (userRes.ok) setUsers(await userRes.json());
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTutorSettings = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/tutor-settings`, { credentials: 'include' });
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
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(tutorSettings)
      });
      if (res.ok) toast.success('Configuracoes do Tutor IA salvas!');
      else toast.error('Erro ao salvar configuracoes');
    } catch (e) { toast.error('Erro ao salvar'); }
    finally { setTutorLoading(false); }
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
        headers: { 'Content-Type': 'application/json' },
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
    if (!confirm(`Desativar empresa "${company.name}"?`)) return;
    
    try {
      const res = await fetch(`${API_URL}/api/companies/${company.id}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (!res.ok) throw new Error('Erro ao desativar empresa');
      
      toast.success('Empresa desativada');
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
        headers: { 'Content-Type': 'application/json' },
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
        ? { name: userForm.name, role: userForm.role }
        : userForm;

      const res = await fetch(url, {
        method: editingUser ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail);
      }

      toast.success(editingUser ? 'Usuário atualizado!' : 'Usuário criado!');
      setShowUserModal(false);
      setEditingUser(null);
      setUserForm({ name: '', email: '', password: '', role: 'editor', companyId: user?.companyId || '' });
      fetchData();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleDeleteUser = async (targetUser) => {
    if (!confirm(`Desativar usuário "${targetUser.name}"?`)) return;
    
    try {
      const res = await fetch(`${API_URL}/api/users/${targetUser.user_id}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (!res.ok) throw new Error('Erro ao desativar usuário');
      
      toast.success('Usuário desativado');
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
      role: targetUser.role,
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
      role: 'editor',
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
              {user?.name} ({user?.role === 'super_admin' ? 'Super Admin' : 'Admin'})
            </span>
            <Button variant="outline" size="sm" onClick={logout}>
              Sair
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex gap-4 mb-8">
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
            variant={activeTab === 'tutor' ? 'default' : 'outline'}
            onClick={() => setActiveTab('tutor')}
            className="gap-2"
          >
            <Bot className="w-4 h-4" />
            Tutor IA
          </Button>
        </div>

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
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          u.role === 'super_admin' ? 'bg-purple-500/20 text-purple-400' :
                          u.role === 'company_admin' ? 'bg-blue-500/20 text-blue-400' :
                          'bg-slate-500/20 text-slate-400'
                        }`}>
                          {u.role === 'super_admin' ? 'Super Admin' : u.role === 'company_admin' ? 'Admin' : 'Editor'}
                        </span>
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
      </div>

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
                <>
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">Email</label>
                    <Input
                      type="email"
                      value={userForm.email}
                      onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                      placeholder="email@exemplo.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">Senha</label>
                    <Input
                      type="password"
                      value={userForm.password}
                      onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                      placeholder="Mínimo 6 caracteres"
                    />
                  </div>
                </>
              )}
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
                <label className="block text-sm text-slate-300 mb-1">Função</label>
                <select
                  value={userForm.role}
                  onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
                  className="w-full h-10 px-3 rounded-md bg-slate-700 border border-slate-600 text-white"
                >
                  <option value="editor">Editor</option>
                  {(isSuperAdmin || user?.role === 'company_admin') && (
                    <option value="company_admin">Admin da Empresa</option>
                  )}
                  {isSuperAdmin && (
                    <option value="super_admin">Super Admin</option>
                  )}
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowUserModal(false)}>Cancelar</Button>
              <Button onClick={handleSaveUser}>Salvar</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
