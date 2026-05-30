"""Email notification service using Resend API."""
import os
import asyncio
import logging
import resend

logger = logging.getLogger("server")

def _clean(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s


resend.api_key = _clean(os.environ.get("RESEND_API_KEY", ""))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
APP_NAME = "Scormify"


async def send_email(to: str, subject: str, html: str) -> dict:
    """Send an email via Resend. Falls back to test sender if domain not verified yet."""
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not set, skipping email")
        return {"status": "skipped", "reason": "no_api_key"}

    # Try with verified domain first, fallback to test sender
    senders = [f"{APP_NAME} <{SENDER_EMAIL}>"]
    if SENDER_EMAIL != "onboarding@resend.dev":
        senders.append(f"{APP_NAME} <onboarding@resend.dev>")

    for sender in senders:
        params = {
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        try:
            result = await asyncio.to_thread(resend.Emails.send, params)
            email_id = result.get("id") if isinstance(result, dict) else str(result)
            logger.info(f"Email sent to {to} from {sender}: {subject} (id={email_id})")
            return {"status": "sent", "id": email_id, "from": sender}
        except Exception as e:
            err_msg = str(e)
            if "not verified" in err_msg and sender != senders[-1]:
                logger.info(f"Domain not verified yet, trying fallback sender...")
                continue
            logger.error(f"Email send failed to {to}: {e}")
            return {"status": "error", "error": err_msg[:200]}


def _base_template(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#1e293b;border-radius:12px;overflow:hidden;">
  <tr><td style="background:linear-gradient(135deg,#7c3aed,#2563eb);padding:24px 32px;">
    <h1 style="margin:0;color:#fff;font-size:22px;">{APP_NAME}</h1>
    <p style="margin:4px 0 0;color:#e2e8f0;font-size:13px;">{title}</p>
  </td></tr>
  <tr><td style="padding:28px 32px;color:#cbd5e1;font-size:14px;line-height:1.6;">
    {body_html}
  </td></tr>
  <tr><td style="padding:16px 32px;border-top:1px solid #334155;text-align:center;">
    <p style="margin:0;color:#64748b;font-size:11px;">Este email foi enviado automaticamente pelo {APP_NAME}.</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


async def notify_approval_submitted(approver_email: str, author_name: str, course_title: str, session_id: str):
    html = _base_template("Novo Storyboard para Aprovacao", f"""
    <h2 style="color:#f8fafc;font-size:18px;margin:0 0 12px;">Storyboard Aguardando Aprovacao</h2>
    <p><strong style="color:#a78bfa;">{author_name}</strong> enviou o storyboard do curso 
    <strong style="color:#60a5fa;">"{course_title}"</strong> para sua aprovacao.</p>
    <p style="color:#94a3b8;font-size:12px;">ID da sessao: {session_id}</p>
    """)
    return await send_email(approver_email, f"[Aprovacao] {course_title} - Aguardando sua revisao", html)


async def notify_approval_approved(author_email: str, approver_name: str, course_title: str):
    html = _base_template("Storyboard Aprovado!", f"""
    <div style="text-align:center;margin-bottom:16px;">
      <span style="display:inline-block;background:#059669;border-radius:50%;padding:12px;">
        <span style="color:#fff;font-size:24px;">&#10003;</span>
      </span>
    </div>
    <h2 style="color:#10b981;font-size:18px;margin:0 0 12px;text-align:center;">Storyboard Aprovado!</h2>
    <p><strong style="color:#a78bfa;">{approver_name}</strong> aprovou o storyboard do curso 
    <strong style="color:#60a5fa;">"{course_title}"</strong>.</p>
    <p>A geracao do curso sera iniciada automaticamente.</p>
    """)
    return await send_email(author_email, f"[Aprovado] {course_title} - Storyboard aprovado!", html)


async def notify_approval_rejected(author_email: str, approver_name: str, course_title: str, reason: str = ""):
    reason_html = f'<p style="background:#1e1b2e;border-left:3px solid #ef4444;padding:12px;border-radius:4px;color:#fca5a5;">"{reason}"</p>' if reason else ""
    html = _base_template("Storyboard Devolvido", f"""
    <h2 style="color:#f87171;font-size:18px;margin:0 0 12px;">Storyboard Devolvido para Revisao</h2>
    <p><strong style="color:#a78bfa;">{approver_name}</strong> devolveu o storyboard do curso 
    <strong style="color:#60a5fa;">"{course_title}"</strong> para ajustes.</p>
    {reason_html}
    <p>Por favor, revise e reenvie para aprovacao.</p>
    """)
    return await send_email(author_email, f"[Devolvido] {course_title} - Ajustes necessarios", html)


async def notify_course_generated(author_email: str, course_title: str, slides_count: int, quiz_count: int, project_id: str):
    html = _base_template("Curso Gerado com Sucesso!", f"""
    <div style="text-align:center;margin-bottom:16px;">
      <span style="display:inline-block;background:#7c3aed;border-radius:50%;padding:12px;">
        <span style="color:#fff;font-size:24px;">&#9733;</span>
      </span>
    </div>
    <h2 style="color:#a78bfa;font-size:18px;margin:0 0 12px;text-align:center;">Curso Gerado!</h2>
    <p>Seu curso <strong style="color:#60a5fa;">"{course_title}"</strong> foi gerado com sucesso pelo Agente IA.</p>
    <table width="100%" cellpadding="8" cellspacing="0" style="margin:16px 0;background:#0f172a;border-radius:8px;">
    <tr>
      <td style="text-align:center;border-right:1px solid #334155;">
        <p style="margin:0;font-size:24px;color:#a78bfa;font-weight:bold;">{slides_count}</p>
        <p style="margin:2px 0 0;font-size:11px;color:#94a3b8;">Slides</p>
      </td>
      <td style="text-align:center;">
        <p style="margin:0;font-size:24px;color:#f59e0b;font-weight:bold;">{quiz_count}</p>
        <p style="margin:2px 0 0;font-size:11px;color:#94a3b8;">Perguntas</p>
      </td>
    </tr></table>
    """)
    return await send_email(author_email, f"[Gerado] {course_title} - {slides_count} slides prontos!", html)


async def notify_tutor_summary(admin_email: str, course_title: str, questions_count: int, top_questions: list):
    questions_html = ""
    for i, q in enumerate(top_questions[:5]):
        questions_html += f'<tr><td style="padding:6px 12px;border-bottom:1px solid #334155;color:#e2e8f0;font-size:13px;">{i+1}. {q.get("question","")[:100]}</td><td style="padding:6px 12px;border-bottom:1px solid #334155;color:#f59e0b;font-size:13px;text-align:right;">{q.get("count",0)}x</td></tr>'

    html = _base_template("Resumo do Tutor IA", f"""
    <h2 style="color:#f8fafc;font-size:18px;margin:0 0 12px;">Atividade do Tutor IA</h2>
    <p>O curso <strong style="color:#60a5fa;">"{course_title}"</strong> recebeu 
    <strong style="color:#f59e0b;">{questions_count} perguntas</strong> dos alunos.</p>
    {"<h3 style='color:#94a3b8;font-size:14px;margin:16px 0 8px;'>Perguntas mais frequentes:</h3><table width='100%' cellpadding='0' cellspacing='0' style='background:#0f172a;border-radius:8px;overflow:hidden;'>" + questions_html + "</table>" if questions_html else ""}
    """)
    return await send_email(admin_email, f"[Tutor IA] {course_title} - {questions_count} perguntas", html)
