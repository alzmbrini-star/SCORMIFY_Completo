# PRD - Course Authoring Tool

## Original Problem Statement
Application is a React/FastAPI course authoring tool with features including SCORM export, PPT import, AI-powered script generation, TTS (ElevenLabs), and avatar video generation (HeyGen).

## Core Requirements
- **[DONE]** Fix all login and deployment-related issues
- **[DONE]** Implement PPT import for production environment
- **[DONE]** Resolve all SCORM and HTML export regressions
- **[DONE]** Ensure all core functionalities are stable in production
- **[DONE]** Achieve stable production deployment (Nginx startup conflict resolved)
- **[DONE]** Ensure projects are visible and accessible after login

## Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Proxy:** Nginx (port 80) managed by deployment orchestrator

## 3rd Party Integrations
- ElevenLabs (TTS)
- HeyGen (avatar video)
- Google Gemini via Emergent LLM Key (AI script generation)
- ConvertAPI (PPT conversion, user API key)

## What's Been Implemented
- SCORM export hardened against None values
- SCORM quiz completion logic fixed (waits for quiz before LMSFinish)
- FastAPI non-blocking startup (health check responds immediately)
- Automated export file cleanup (background task)
- Nginx config patcher script (`fix_nginx_modules.sh`) - patches configs without starting Nginx
- Deployment orchestrator compatibility ensured

## Deployment Fix (Feb 2026)
- **Root cause:** `fix_nginx_modules.sh` STEP 4 was executing `nginx` / `nginx -s reload` commands, creating a port 80 conflict with the deployment orchestrator's own Nginx startup
- **Fix:** Removed all nginx start/reload commands from the script. Now only patches config files and validates with `nginx -t`
- **Deployment agent check:** All checks passed

## Backlog
- **P2:** Refactor `backend/src/exporters/html_exporter.py` to use external templates for HTML, CSS, JS
