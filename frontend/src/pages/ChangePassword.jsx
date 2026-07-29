import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Eye, EyeOff, KeyRound, Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { authFetch, API_URL } from '../utils/authFetch';

const MIN_PASSWORD_LENGTH = 12;

export default function ChangePassword() {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!currentPassword) {
      toast.error('Informe a senha atual.');
      return;
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      toast.error(`A nova senha deve ter pelo menos ${MIN_PASSWORD_LENGTH} caracteres.`);
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('A confirmação não corresponde à nova senha.');
      return;
    }
    if (newPassword === currentPassword) {
      toast.error('A nova senha deve ser diferente da senha atual.');
      return;
    }

    setSaving(true);
    try {
      const response = await authFetch(`${API_URL}/api/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ currentPassword, newPassword }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || 'Não foi possível alterar a senha.');
      }

      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      toast.success('Senha alterada com sucesso.');
      navigate('/');
    } catch (error) {
      const message = error?.message || 'Não foi possível alterar a senha.';
      if (message === 'Current password is incorrect') {
        toast.error('A senha atual está incorreta.');
      } else {
        toast.error(message);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border/60 bg-card/60 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center">
          <Button
            variant="ghost"
            onClick={() => navigate('/')}
            className="gap-2"
            data-testid="back-to-dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
            Voltar ao painel
          </Button>
        </div>
      </header>

      <main className="max-w-xl mx-auto px-6 py-12">
        <Card className="border-border/60 shadow-xl">
          <CardHeader className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6 text-primary" />
            </div>
            <div>
              <CardTitle className="text-2xl">Trocar senha</CardTitle>
              <CardDescription className="mt-2">
                Use uma senha exclusiva, com pelo menos {MIN_PASSWORD_LENGTH} caracteres.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="current-password" className="text-sm font-medium">
                  Senha atual
                </label>
                <div className="relative">
                  <Input
                    id="current-password"
                    type={showCurrent ? 'text' : 'password'}
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    autoComplete="current-password"
                    className="pr-11"
                    data-testid="current-password"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowCurrent((value) => !value)}
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8"
                    aria-label={showCurrent ? 'Ocultar senha atual' : 'Mostrar senha atual'}
                  >
                    {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="new-password" className="text-sm font-medium">
                  Nova senha
                </label>
                <div className="relative">
                  <Input
                    id="new-password"
                    type={showNew ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    autoComplete="new-password"
                    minLength={MIN_PASSWORD_LENGTH}
                    className="pr-11"
                    data-testid="new-password"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowNew((value) => !value)}
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8"
                    aria-label={showNew ? 'Ocultar nova senha' : 'Mostrar nova senha'}
                  >
                    {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="confirm-password" className="text-sm font-medium">
                  Confirmar nova senha
                </label>
                <Input
                  id="confirm-password"
                  type={showNew ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={MIN_PASSWORD_LENGTH}
                  data-testid="confirm-password"
                />
              </div>

              <div className="rounded-lg border border-border/60 bg-muted/40 p-4 text-sm text-muted-foreground">
                Após confirmar a nova senha, o segredo inicial poderá ser removido do Render.
              </div>

              <Button
                type="submit"
                disabled={saving}
                className="w-full gap-2"
                data-testid="change-password-submit"
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Alterando...
                  </>
                ) : (
                  <>
                    <KeyRound className="w-4 h-4" />
                    Alterar senha
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
