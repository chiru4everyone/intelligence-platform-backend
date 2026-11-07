"""
Vercel ASGI entry point — Intelligence Platform Backend.

Vercel serverless has no persistent filesystem and no startup lifecycle,
so this module:
  1. Serves the login page at GET / (HTML embedded directly — no file read)
  2. Mounts all API routers lazily (no lifespan DB init)
  3. Uses in-memory SQLite for the serverless context

Vercel picks up the `app` name from this module automatically.
"""
import sys
import os

# Ensure project root is importable
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from functools import wraps
from typing import Optional
import hashlib
import hmac
import secrets
import time
import datetime
import uuid

# ── Login page HTML (embedded — no filesystem dependency on serverless) ──────
_LOGIN_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Intelligence Platform — Sign In</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.39.3/dist/umd/supabase.min.js"></script>
<script>
/* Supabase credentials — injected by FastAPI from env vars */
window.__SUPA_URL__ = '{SUPA_URL}';
window.__SUPA_KEY__ = '{SUPA_KEY}';
</script>
<style>
:root{--ink:#080a0f;--ink2:#0d1017;--ink3:#131720;--ink4:#1a2030;--rule:rgba(255,255,255,.06);--rule2:rgba(255,255,255,.12);--white:#f0f2f7;--fog:#8a95a8;--ghost:#4a5568;--teal:#2ec4b6;--gold:#c8a96e;--coral:#e85d4a;--violet:#9b72e8;--agri:#4caf78;--sapph:#4a7fe8;--role-analyst:#4a7fe8;--role-senior:#9b72e8;--role-head:#c8a96e;--ff-serif:'DM Serif Display',Georgia,serif;--ff-body:'Inter',system-ui,sans-serif;--ff-mono:'JetBrains Mono',monospace;--r:6px;--r2:10px;color-scheme:dark}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:var(--ff-body);background:var(--ink);color:var(--white);-webkit-font-smoothing:antialiased}
.shell{min-height:100%;display:grid;grid-template-columns:1fr 1fr}
.brand-panel{position:relative;display:flex;flex-direction:column;justify-content:space-between;padding:48px 52px;background:var(--ink2);border-right:1px solid var(--rule);overflow:hidden}
.brand-panel::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 20% 30%,rgba(46,196,182,.07) 0%,transparent 70%),radial-gradient(ellipse 50% 60% at 80% 70%,rgba(74,127,232,.05) 0%,transparent 70%);pointer-events:none}
.brand-mark{position:relative;z-index:1}
.wordmark{font-family:var(--ff-serif);font-size:22px;color:var(--white);letter-spacing:-.3px;margin-bottom:6px}
.sector-tag{font-family:var(--ff-mono);font-size:9px;color:var(--teal);letter-spacing:1.8px;text-transform:uppercase}
.brand-hero{position:relative;z-index:1;flex:1;display:flex;flex-direction:column;justify-content:center;padding:40px 0}
.hero-eyebrow{font-family:var(--ff-mono);font-size:9px;color:var(--fog);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:20px}
.hero-headline{font-family:var(--ff-serif);font-size:clamp(28px,3.2vw,42px);line-height:1.18;color:var(--white);text-wrap:balance;margin-bottom:24px}
.hero-headline em{font-style:italic;color:var(--teal)}
.hero-desc{font-size:13.5px;line-height:1.65;color:var(--fog);max-width:340px}
.domain-row{position:relative;z-index:1;display:flex;gap:10px;flex-wrap:wrap}
.domain-chip{display:flex;align-items:center;gap:7px;padding:7px 12px;background:rgba(255,255,255,.04);border:1px solid var(--rule2);border-radius:20px;font-size:11px;color:var(--fog);font-family:var(--ff-mono)}
.domain-chip .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.login-panel{display:flex;flex-direction:column;justify-content:center;padding:48px max(28px,5vw);background:var(--ink)}
.login-inner{max-width:380px;width:100%;margin:0 auto}
.login-heading{font-family:var(--ff-serif);font-size:28px;color:var(--white);margin-bottom:6px}
.login-sub{font-size:13px;color:var(--fog);margin-bottom:36px}
.role-label{font-family:var(--ff-mono);font-size:9px;letter-spacing:1.4px;text-transform:uppercase;color:var(--fog);margin-bottom:10px}
.role-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:28px}
.role-card{position:relative;padding:14px 10px;background:var(--ink3);border:1.5px solid var(--rule2);border-radius:var(--r2);cursor:pointer;text-align:center;transition:border-color .2s,background .2s,transform .15s;user-select:none}
.role-card:hover{background:var(--ink4);transform:translateY(-1px)}
.role-card.active{background:var(--ink4)}
.role-card.active[data-role="analyst"]{border-color:var(--role-analyst);box-shadow:0 0 0 1px rgba(74,127,232,.2),inset 0 1px 0 rgba(74,127,232,.08)}
.role-card.active[data-role="senior"]{border-color:var(--role-senior);box-shadow:0 0 0 1px rgba(155,114,232,.2),inset 0 1px 0 rgba(155,114,232,.08)}
.role-card.active[data-role="head"]{border-color:var(--role-head);box-shadow:0 0 0 1px rgba(200,169,110,.2),inset 0 1px 0 rgba(200,169,110,.08)}
.role-icon{font-size:20px;margin-bottom:8px;line-height:1}
.role-name{font-size:11px;font-weight:600;color:var(--white);line-height:1.3;margin-bottom:2px}
.role-badge{font-family:var(--ff-mono);font-size:8.5px;letter-spacing:.8px;text-transform:uppercase;opacity:.55;line-height:1}
.role-card[data-role="analyst"] .role-badge{color:var(--role-analyst)}
.role-card[data-role="senior"] .role-badge{color:var(--role-senior)}
.role-card[data-role="head"] .role-badge{color:var(--role-head)}
.role-card::after{content:'';position:absolute;top:8px;right:8px;width:5px;height:5px;border-radius:50%;opacity:0;transition:opacity .2s}
.role-card.active[data-role="analyst"]::after{background:var(--role-analyst);opacity:1}
.role-card.active[data-role="senior"]::after{background:var(--role-senior);opacity:1}
.role-card.active[data-role="head"]::after{background:var(--role-head);opacity:1}
.field-group{display:flex;flex-direction:column;gap:14px;margin-bottom:24px}
.field{display:flex;flex-direction:column;gap:6px}
.field label{font-family:var(--ff-mono);font-size:9px;letter-spacing:1.4px;text-transform:uppercase;color:var(--fog)}
.field input{width:100%;padding:11px 14px;background:var(--ink3);border:1.5px solid var(--rule2);border-radius:var(--r);font-family:var(--ff-body);font-size:13.5px;color:var(--white);outline:none;transition:border-color .2s,box-shadow .2s;-webkit-appearance:none}
.field input::placeholder{color:var(--ghost)}
.field input:focus{border-color:var(--acc,var(--teal));box-shadow:0 0 0 3px var(--acc-glow,rgba(46,196,182,.12))}
.pw-row{display:flex;align-items:center;justify-content:space-between;gap:8px}
.pw-row label{margin-bottom:0}
.forgot-link{font-size:11px;color:var(--fog);text-decoration:none;transition:color .15s;flex-shrink:0}
.forgot-link:hover{color:var(--white)}
.btn-primary{width:100%;padding:13px 20px;background:var(--acc,var(--teal));border:none;border-radius:var(--r);font-family:var(--ff-body);font-size:13.5px;font-weight:600;color:var(--ink);cursor:pointer;letter-spacing:.2px;transition:opacity .15s,transform .1s;margin-bottom:12px}
.btn-primary:hover{opacity:.9}
.btn-primary:active{transform:scale(.99)}
.btn-sso{width:100%;padding:11px 20px;background:transparent;border:1.5px solid var(--rule2);border-radius:var(--r);font-family:var(--ff-body);font-size:13px;font-weight:500;color:var(--fog);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;transition:border-color .15s,color .15s}
.btn-sso:hover{color:var(--white)}
.sso-icon{width:15px;height:15px;opacity:.7}
.or-row{display:flex;align-items:center;gap:12px;margin-bottom:12px;margin-top:4px}
.or-row::before,.or-row::after{content:'';flex:1;height:1px;background:var(--rule2)}
.or-row span{font-family:var(--ff-mono);font-size:9px;color:var(--ghost);letter-spacing:1px;text-transform:uppercase}
.access-note{margin-top:20px;padding:12px 14px;background:rgba(255,255,255,.025);border:1px solid var(--rule);border-radius:var(--r);display:flex;gap:10px;align-items:flex-start}
.access-note-icon{font-size:14px;flex-shrink:0;margin-top:1px}
.access-note-text{font-size:11.5px;line-height:1.55;color:var(--fog)}
.access-note-text strong{color:var(--white);font-weight:600}
.field-error{font-size:11px;color:var(--coral);display:none}
.field.has-error input{border-color:var(--coral);box-shadow:0 0 0 3px rgba(232,93,74,.1)}
.field.has-error .field-error{display:block}
.toast{position:fixed;bottom:28px;left:50%;transform:translateX(-50%) translateY(12px);background:var(--ink4);border:1px solid var(--rule2);border-radius:24px;padding:10px 20px;font-size:12.5px;color:var(--white);display:flex;align-items:center;gap:8px;box-shadow:0 8px 32px rgba(0,0,0,.4);opacity:0;pointer-events:none;transition:opacity .25s,transform .25s;white-space:nowrap;z-index:100}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.access-note.note-analyst{border-color:rgba(74,127,232,.22);background:rgba(74,127,232,.04)}
.access-note.note-senior{border-color:rgba(155,114,232,.22);background:rgba(155,114,232,.04)}
.access-note.note-head{border-color:rgba(200,169,110,.22);background:rgba(200,169,110,.04)}
@media(max-width:720px){.shell{grid-template-columns:1fr}.brand-panel{display:none}.login-panel{padding:40px max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
@media(max-width:400px){.role-grid{grid-template-columns:1fr}.role-card{text-align:left;display:flex;align-items:center;gap:12px}.role-icon{margin-bottom:0}}
</style>
</head>
<body>
<div class="shell">
  <div class="brand-panel">
    <div class="brand-mark">
      <div class="wordmark">Intelligence Platform</div>
      <div class="sector-tag">Cross-Domain Market Intelligence</div>
    </div>
    <div class="brand-hero">
      <div class="hero-eyebrow">Analyst Workspace</div>
      <h1 class="hero-headline">From raw signal<br>to <em>decisive</em><br>intelligence.</h1>
      <p class="hero-desc">Your research environment spanning Epidemiology, Agriculture, Pharma Intelligence, Packaging, Markets, and Startup Ecosystems — India-first, globally benchmarked.</p>
    </div>
    <div class="domain-row">
      <div class="domain-chip"><span class="dot" style="background:#2ec4b6"></span>Epidemiology</div>
      <div class="domain-chip"><span class="dot" style="background:#4caf78"></span>Agriculture</div>
      <div class="domain-chip"><span class="dot" style="background:#d47ccc"></span>Pharma</div>
      <div class="domain-chip"><span class="dot" style="background:#c8a96e"></span>Markets</div>
      <div class="domain-chip"><span class="dot" style="background:#9b72e8"></span>Startups</div>
      <div class="domain-chip"><span class="dot" style="background:#e85d4a"></span>Packaging</div>
    </div>
  </div>
  <div class="login-panel">
    <div class="login-inner">
      <h2 class="login-heading">Sign in</h2>
      <p class="login-sub">Select your role, then enter your credentials.</p>
      <div class="role-label">Access level</div>
      <div class="role-grid" id="roleGrid">
        <div class="role-card active" data-role="analyst" tabindex="0" role="radio" aria-checked="true" aria-label="Analyst">
          <div class="role-icon">📊</div>
          <div class="role-name">Analyst</div>
          <div class="role-badge">Level 1</div>
        </div>
        <div class="role-card" data-role="senior" tabindex="0" role="radio" aria-checked="false" aria-label="Senior Analyst">
          <div class="role-icon">🔬</div>
          <div class="role-name">Senior Analyst</div>
          <div class="role-badge">Level 2</div>
        </div>
        <div class="role-card" data-role="head" tabindex="0" role="radio" aria-checked="false" aria-label="Head of Research">
          <div class="role-icon">🎯</div>
          <div class="role-name">Head of Research</div>
          <div class="role-badge">Level 3</div>
        </div>
      </div>
      <form id="loginForm" novalidate>
        <div class="field-group">
          <div class="field" id="emailField">
            <label for="email">Work email</label>
            <input type="email" id="email" name="email" placeholder="you@organisation.com" autocomplete="email">
            <span class="field-error">Enter a valid email address.</span>
          </div>
          <div class="field" id="passField">
            <div class="pw-row">
              <label for="password">Password</label>
              <a href="#" class="forgot-link" tabindex="-1">Forgot password?</a>
            </div>
            <input type="password" id="password" name="password" placeholder="••••••••" autocomplete="current-password">
            <span class="field-error">Password is required.</span>
          </div>
        </div>
        <button type="submit" class="btn-primary" id="signInBtn">Sign in as Analyst</button>
        <div class="or-row"><span>or</span></div>
        <button type="button" class="btn-sso" id="ssoBtn">
          <svg class="sso-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          Continue with SSO
        </button>
      </form>
      <div class="access-note note-analyst" id="accessNote">
        <div class="access-note-icon">🔵</div>
        <div class="access-note-text" id="accessText"><strong>Analyst access</strong> — Platform dashboards, sector reports, standard data exports.</div>
      </div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
(function(){
  const ROLES={analyst:{label:'Analyst',acc:'#4a7fe8',accGlow:'rgba(74,127,232,.14)',noteClass:'note-analyst',noteIcon:'🔵',noteText:'<strong>Analyst access</strong> — Platform dashboards, sector reports, and standard data exports. Contact your Senior Analyst to request elevated access.'},senior:{label:'Senior Analyst',acc:'#9b72e8',accGlow:'rgba(155,114,232,.14)',noteClass:'note-senior',noteIcon:'🟣',noteText:'<strong>Senior Analyst access</strong> — Full platform dashboards, custom research pipelines, file uploads, and team report management.'},head:{label:'Head of Research',acc:'#c8a96e',accGlow:'rgba(200,169,110,.14)',noteClass:'note-head',noteIcon:'🟡',noteText:'<strong>Head of Research access</strong> — All platform capabilities plus admin controls, user management, data model configuration, and client delivery workflows.'}};
  let activeRole='analyst';
  const cards=document.querySelectorAll('.role-card'),signInBtn=document.getElementById('signInBtn'),accessNote=document.getElementById('accessNote'),accessText=document.getElementById('accessText'),emailField=document.getElementById('emailField'),passField=document.getElementById('passField'),emailInput=document.getElementById('email'),passInput=document.getElementById('password'),form=document.getElementById('loginForm'),toast=document.getElementById('toast'),ssoBtn=document.getElementById('ssoBtn');
  function applyRole(k){activeRole=k;const c=ROLES[k],r=document.documentElement;r.style.setProperty('--acc',c.acc);r.style.setProperty('--acc-glow',c.accGlow);cards.forEach(x=>{const a=x.dataset.role===k;x.classList.toggle('active',a);x.setAttribute('aria-checked',a?'true':'false')});signInBtn.textContent='Sign in as '+c.label;accessNote.className='access-note '+c.noteClass;document.querySelector('#accessNote .access-note-icon').textContent=c.noteIcon;accessText.innerHTML=c.noteText}
  cards.forEach(card=>{card.addEventListener('click',()=>applyRole(card.dataset.role));card.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();applyRole(card.dataset.role)}})});
  function validate(){let ok=true;const e=emailInput.value.trim(),p=passInput.value;if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)){emailField.classList.add('has-error');ok=false}else emailField.classList.remove('has-error');if(!p){passField.classList.add('has-error');ok=false}else passField.classList.remove('has-error');return ok}
  emailInput.addEventListener('input',()=>emailField.classList.remove('has-error'));
  passInput.addEventListener('input',()=>passField.classList.remove('has-error'));
  let toastTimer;
  function showToast(msg,icon='✦'){toast.innerHTML='<span>'+icon+'</span> '+msg;toast.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.classList.remove('show'),3200)}
  /* ── Supabase client (env vars injected at build / runtime) ── */
  const SUPA_URL = window.__SUPA_URL__ || '';
  const SUPA_KEY = window.__SUPA_KEY__ || '';
  let supabase = null;
  if(SUPA_URL && SUPA_KEY && window.supabase){
    supabase = window.supabase.createClient(SUPA_URL, SUPA_KEY);
  }

  async function signIn(email, password, role) {
    if(!supabase) {
      /* Supabase not configured — show setup hint */
      showToast('Configure SUPABASE_URL & SUPABASE_KEY in Vercel env vars', '⚠');
      return false;
    }
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if(error) { showToast(error.message, '⚠'); return false; }

    /* Log the session with the selected role */
    try {
      await supabase.from('analyst_sessions').insert({
        user_id: data.user.id,
        role_at_login: role,
        vertical: 'all',
        user_agent: navigator.userAgent,
        session_token: data.session.access_token.slice(-32)
      });
    } catch(_) { /* non-fatal */ }

    /* Store role in localStorage for downstream pages */
    try { localStorage.setItem('ip_role', role); localStorage.setItem('ip_user', data.user.email); } catch(_){}
    return true;
  }

  form.addEventListener('submit', async e => {
    e.preventDefault();
    if(!validate()) return;
    const c = ROLES[activeRole], orig = signInBtn.textContent;
    signInBtn.textContent = 'Signing in…';
    signInBtn.disabled = true;
    try {
      const ok = await signIn(emailInput.value.trim(), passInput.value, activeRole);
      if(ok) {
        showToast('Welcome back — ' + c.label + ' session started', '✓');
        setTimeout(async () => {
          try {
            const sess = (await supabase.auth.getSession()).data.session;
            const res = await fetch('/api/me', {
              headers: { 'Authorization': 'Bearer ' + sess.access_token }
            });
            if(res.ok) {
              const profile = await res.json();
              const portals = {
                epi:       '/epi-intelligence/',
                agri:      '/agri-intelligence/',
                pharma:    '/pharma-intelligence/',
                markets:   '/markets-intelligence/',
                packaging: '/packaging-intelligence/',
                startups:  '/startup-intelligence/',
                all:       '/dashboard/'
              };
              window.location.href = portals[profile.vertical] || '/dashboard/';
            } else {
              window.location.href = '/dashboard/';
            }
          } catch(_) { window.location.href = '/dashboard/'; }
        }, 1000);
      }
    } finally {
      signInBtn.textContent = orig;
      signInBtn.disabled = false;
    }
  });

  ssoBtn.addEventListener('click', async () => {
    if(!supabase){ showToast('Configure Supabase env vars first', '⚠'); return; }
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin }
    });
    if(error) showToast(error.message, '⚠');
  });
  applyRole('analyst');
}());
</script>
</body>
</html>"""

# ── Epi intelligence page (embedded — no filesystem reads at runtime) ─────────
# File: pages/epi-intelligence.html — embedded here for Vercel serverless.
# Supabase credentials are injected at request time via string replacement.
import pathlib as _pl
_pages_dir = _pl.Path(__file__).parent.parent / "pages"

def _load_page(filename: str) -> str:
    """Load a page from pages/ directory at import time (safe — happens at build)."""
    try:
        return (_pages_dir / filename).read_text(encoding="utf-8")
    except Exception:
        return f"<html><body><h1>{filename} not found</h1></body></html>"

_EPI_HTML        = _load_page("epi-intelligence.html")
_AGRI_HTML       = _load_page("agri-intelligence.html")
_MARKETS_HTML    = _load_page("markets-intelligence.html")
_PACKAGING_HTML  = _load_page("packaging-intelligence.html")
_STARTUPS_HTML   = _load_page("startup-intelligence.html")
_PHARMA_HTML     = _load_page("pharma-intelligence.html")
_PREVIEW_HTML    = _load_page("preview.html")
_MASTER_HTML     = _load_page("master-dashboard.html")

# ── FastAPI app (no lifespan — serverless safe) ───────────────────────────────
app = FastAPI(
    title="Intelligence Platform API",
    description=(
        "Backend API for the Intelligence Platform portals. "
        "Accepts Excel / PowerPoint / Word uploads, parses them into platform tab data, "
        "and serves structured JSON to the frontend portals.\n\n"
        "**Admin endpoints** require `Authorization: Bearer <ADMIN_TOKEN>` header."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://intelligence-platform-cmot.vercel.app,https://intelligence-platform-backend.vercel.app"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
try:
    from app.routers import upload, data
    app.include_router(upload.router)
    app.include_router(data.router)
except Exception:
    pass  # Routers unavailable in stripped serverless env — API docs still show

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Login page — served as the homepage. Supabase credentials injected from env."""
    supa_url = os.environ.get("SUPABASE_URL", "").rstrip("/")   # strip trailing slash
    supa_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    html = _LOGIN_HTML.replace("'{SUPA_URL}'", f"'{supa_url}'").replace("'{SUPA_KEY}'", f"'{supa_key}'")
    return HTMLResponse(content=html)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "0.1.0", "service": "Intelligence Platform API"}


# ── Supabase client (lazy — only initialised when env vars are present) ───────
def _get_supa():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None


# ── Role + vertical access matrix ─────────────────────────────────────────────
PERMISSIONS = {
    "analyst": {
        "can_view":    True,
        "can_upload":  False,
        "can_approve": False,
        "can_publish": False,
    },
    "senior": {
        "can_view":    True,
        "can_upload":  True,
        "can_approve": True,
        "can_publish": False,
    },
    "head": {
        "can_view":    True,
        "can_upload":  True,
        "can_approve": True,
        "can_publish": True,
    },
}

PORTAL_MAP = {
    "epi":       "/epi-intelligence/",
    "agri":      "/agri-intelligence/",
    "pharma":    "/pharma-intelligence/",
    "markets":   "/markets-intelligence/",
    "packaging": "/packaging-intelligence/",
    "startups":  "/startup-intelligence/",
    "all":       "/dashboard/",
}


async def _resolve_profile(request: Request):
    """Extract Bearer token → verify with Supabase → return profile dict."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth.split(" ", 1)[1]
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Auth service not configured")
    try:
        user_resp = supa.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        uid = user_resp.user.id
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {exc}")
    try:
        profile_resp = (
            supa.table("profiles")
            .select("id, role, vertical, full_name, email")
            .eq("id", uid)
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Profile fetch failed: {exc}")
    if not profile_resp.data:
        raise HTTPException(status_code=403, detail="No profile found for this user")
    return profile_resp.data


def require_role(*allowed_roles: str):
    """
    Decorator for route handlers that enforces role-based access.

    Usage:
        @app.get("/api/admin/something")
        @require_role("senior", "head")
        async def my_route(request: Request): ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            profile = await _resolve_profile(request)
            if profile["role"] not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Role '{profile['role']}' is not permitted. Required: {list(allowed_roles)}"
                )
            # Attach profile to request state so the handler can read it
            request.state.role     = profile["role"]
            request.state.vertical = profile["vertical"]
            request.state.email    = profile.get("email", "")
            request.state.permissions = PERMISSIONS.get(profile["role"], {})
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# ── /api/me ───────────────────────────────────────────────────────────────────
@app.get("/api/me", tags=["auth"])
async def get_me(request: Request):
    """
    Return the authenticated user's role, vertical, and portal URL.

    Called by the login page after sign-in to determine where to redirect.
    Requires: Authorization: Bearer <supabase_access_token>
    """
    profile = await _resolve_profile(request)
    return {
        "role":        profile["role"],
        "vertical":    profile["vertical"],
        "full_name":   profile.get("full_name"),
        "email":       profile.get("email"),
        "permissions": PERMISSIONS.get(profile["role"], {}),
        "portal":      PORTAL_MAP.get(profile["vertical"], "/dashboard/"),
    }


# ── Example protected routes (extend as needed) ───────────────────────────────
@app.get("/api/admin/users", tags=["admin"])
@require_role("head")
async def list_users(request: Request):
    """Head of Research only — list all analyst profiles."""
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Auth service not configured")
    resp = supa.table("profiles").select("id, email, full_name, role, vertical, is_active, created_at").execute()
    return {"users": resp.data or []}


@app.post("/api/admin/deactivate/{user_id}", tags=["admin"])
@require_role("head")
async def deactivate_user(request: Request, user_id: str):
    """Head of Research only — deactivate an analyst account."""
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Auth service not configured")
    supa.table("profiles").update({"is_active": False}).eq("id", user_id).execute()
    return {"status": "deactivated", "user_id": user_id}


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER ADMIN LAYER
# Superuser access — above all analyst roles.
# Credentials stored in env vars only (never in the database).
# Session token is a signed HMAC — no DB needed to verify.
# ═══════════════════════════════════════════════════════════════════════════════

_MASTER_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Master Admin — Intelligence Platform</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--ink:#06080d;--ink2:#0c0f16;--ink3:#11151e;--ink4:#171c28;--rule:rgba(255,255,255,.06);--rule2:rgba(255,255,255,.1);--white:#eef0f5;--fog:#7a8599;--ghost:#3d4a60;--red:#e85d4a;--gold:#c8a96e;--teal:#2ec4b6;--r:6px;color-scheme:dark}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:'Inter',system-ui,sans-serif;background:var(--ink);color:var(--white);-webkit-font-smoothing:antialiased}
body{display:flex;align-items:center;justify-content:center;padding:24px;min-height:100vh}
.card{width:100%;max-width:360px;background:var(--ink2);border:1px solid var(--rule2);border-radius:12px;padding:40px 36px;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--gold),var(--teal));opacity:.7}
.lock-icon{font-size:28px;margin-bottom:16px;display:block;text-align:center}
.heading{font-size:17px;font-weight:600;color:var(--white);text-align:center;margin-bottom:4px;letter-spacing:-.2px}
.sub{font-size:12px;color:var(--fog);text-align:center;margin-bottom:32px;font-family:'JetBrains Mono',monospace;letter-spacing:.5px}
.field{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}
.field label{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1.4px;text-transform:uppercase;color:var(--fog)}
.field input{width:100%;padding:11px 14px;background:var(--ink3);border:1.5px solid var(--rule2);border-radius:var(--r);font-family:'Inter',monospace;font-size:13.5px;color:var(--white);outline:none;transition:border-color .2s,box-shadow .2s}
.field input:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(200,169,110,.12)}
.field input::placeholder{color:var(--ghost)}
.btn{width:100%;margin-top:8px;padding:13px;background:var(--gold);border:none;border-radius:var(--r);font-family:'Inter',sans-serif;font-size:13px;font-weight:600;color:#0c0a06;cursor:pointer;letter-spacing:.2px;transition:opacity .15s}
.btn:hover{opacity:.88}
.btn:disabled{opacity:.5;cursor:not-allowed}
.error{margin-top:14px;padding:10px 14px;background:rgba(232,93,74,.08);border:1px solid rgba(232,93,74,.25);border-radius:var(--r);font-size:11.5px;color:var(--red);display:none;text-align:center}
.error.show{display:block}
.warning{margin-top:20px;font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--ghost);text-align:center;letter-spacing:.5px;line-height:1.6}

/* Dashboard (hidden until login) */
.dashboard{display:none;width:100%;max-width:900px;flex-direction:column;gap:20px}
.dash-header{display:flex;align-items:center;justify-content:space-between;padding:20px 28px;background:var(--ink2);border:1px solid var(--rule2);border-radius:12px}
.dash-title{font-size:15px;font-weight:600;color:var(--white)}
.dash-sub{font-size:11px;color:var(--fog);font-family:'JetBrains Mono',monospace;margin-top:2px}
.logout-btn{padding:7px 16px;background:transparent;border:1px solid var(--rule2);border-radius:var(--r);font-size:12px;color:var(--fog);cursor:pointer;transition:color .15s,border-color .15s}
.logout-btn:hover{color:var(--white);border-color:var(--rule2)}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.stat-card{padding:18px 20px;background:var(--ink2);border:1px solid var(--rule2);border-radius:10px}
.stat-val{font-size:24px;font-weight:600;color:var(--white);margin-bottom:4px}
.stat-label{font-size:11px;color:var(--fog);font-family:'JetBrains Mono',monospace;letter-spacing:.5px}
.section{background:var(--ink2);border:1px solid var(--rule2);border-radius:10px;overflow:hidden}
.section-head{padding:16px 20px;border-bottom:1px solid var(--rule);display:flex;align-items:center;justify-content:space-between}
.section-title{font-size:13px;font-weight:600;color:var(--white)}
.section-action{font-size:11px;color:var(--teal);cursor:pointer;background:none;border:none;font-family:'Inter',sans-serif}
table{width:100%;border-collapse:collapse}
th{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:var(--fog);padding:10px 20px;text-align:left;border-bottom:1px solid var(--rule)}
td{padding:11px 20px;font-size:12.5px;color:var(--white);border-bottom:1px solid var(--rule)}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.018)}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:20px;font-size:10px;font-family:'JetBrains Mono',monospace;font-weight:500}
.badge-analyst{background:rgba(74,127,232,.12);color:#4a7fe8;border:1px solid rgba(74,127,232,.2)}
.badge-senior{background:rgba(155,114,232,.12);color:#9b72e8;border:1px solid rgba(155,114,232,.2)}
.badge-head{background:rgba(200,169,110,.12);color:#c8a96e;border:1px solid rgba(200,169,110,.2)}
.badge-active{background:rgba(46,196,182,.1);color:#2ec4b6;border:1px solid rgba(46,196,182,.2)}
.badge-inactive{background:rgba(232,93,74,.1);color:#e85d4a;border:1px solid rgba(232,93,74,.2)}
.action-btn{padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer;border:1px solid var(--rule2);background:transparent;color:var(--fog);font-family:'Inter',sans-serif;transition:color .15s}
.action-btn:hover{color:var(--white)}
.action-btn.danger{color:var(--red);border-color:rgba(232,93,74,.3)}
.empty-row{text-align:center;color:var(--fog);font-style:italic;padding:28px}
select.inline-select{background:var(--ink4);border:1px solid var(--rule2);color:var(--white);border-radius:4px;padding:3px 6px;font-size:11px;font-family:'JetBrains Mono',monospace}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(10px);background:var(--ink4);border:1px solid var(--rule2);border-radius:20px;padding:9px 18px;font-size:12px;color:var(--white);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;z-index:999}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
@media(max-width:700px){.stats-row{grid-template-columns:1fr 1fr}table{font-size:11px}th,td{padding:9px 12px}}
</style>
</head>
<body>

<!-- ── Login card ── -->
<div class="card" id="loginCard">
  <span class="lock-icon">🔐</span>
  <div class="heading">Master Admin</div>
  <div class="sub">INTELLIGENCE PLATFORM · SUPERUSER</div>
  <form id="masterForm" novalidate>
    <div class="field">
      <label>Admin email</label>
      <input type="email" id="mEmail" placeholder="master@platform.com" autocomplete="off">
    </div>
    <div class="field">
      <label>Password</label>
      <input type="password" id="mPass" placeholder="••••••••••••" autocomplete="off">
    </div>
    <button type="submit" class="btn" id="mBtn">Access Master Console</button>
  </form>
  <div class="error" id="mError">Invalid credentials. Access denied.</div>
  <div class="warning">⚠ Restricted access · All sessions are logged</div>
</div>

<!-- ── Dashboard ── -->
<div class="dashboard" id="dashboard">
  <div class="dash-header">
    <div>
      <div class="dash-title">Master Admin Console</div>
      <div class="dash-sub">INTELLIGENCE PLATFORM · SUPERUSER SESSION</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
      <a href="/workflow" target="_blank" style="padding:7px 14px;background:rgba(200,169,110,.12);border:1px solid rgba(200,169,110,.25);border-radius:6px;font-size:12px;color:#c8a96e;text-decoration:none;font-weight:500">📊 Workflow Dashboard</a>
      <button class="logout-btn" onclick="logout()">Sign out</button>
    </div>
  </div>

  <div class="stats-row">
    <div class="stat-card"><div class="stat-val" id="statTotal">—</div><div class="stat-label">Total users</div></div>
    <div class="stat-card"><div class="stat-val" id="statActive">—</div><div class="stat-label">Active</div></div>
    <div class="stat-card"><div class="stat-val" id="statSessions">—</div><div class="stat-label">Sessions today</div></div>
    <div class="stat-card"><div class="stat-val" id="statVerticals">6</div><div class="stat-label">Verticals</div></div>
  </div>

  <div class="section">
    <div class="section-head">
      <div class="section-title">Analyst Accounts</div>
      <button class="section-action" onclick="refreshUsers()">↻ Refresh</button>
    </div>
    <table>
      <thead><tr><th>Name / Email</th><th>Role</th><th>Vertical</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody id="userTable"><tr><td colspan="5" class="empty-row">Loading…</td></tr></tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-head">
      <div class="section-title">Recent Login Sessions</div>
      <button class="section-action" onclick="refreshSessions()">↻ Refresh</button>
    </div>
    <table>
      <thead><tr><th>Email</th><th>Role at login</th><th>Vertical</th><th>When</th></tr></thead>
      <tbody id="sessionTable"><tr><td colspan="4" class="empty-row">Loading…</td></tr></tbody>
    </table>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
(function(){
  let masterToken = '';

  /* ── login ── */
  document.getElementById('masterForm').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('mBtn');
    const err = document.getElementById('mError');
    btn.disabled = true; btn.textContent = 'Verifying…'; err.classList.remove('show');
    try {
      const res = await fetch('/api/master/login', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          email: document.getElementById('mEmail').value.trim(),
          password: document.getElementById('mPass').value
        })
      });
      if(!res.ok){ err.classList.add('show'); return; }
      const { token } = await res.json();
      masterToken = token;
      sessionStorage.setItem('_mt', token);
      showDashboard();
    } catch(_){ err.classList.add('show'); }
    finally { btn.disabled=false; btn.textContent='Access Master Console'; }
  });

  async function apiFetch(path, opts={}){
    return fetch(path, {
      ...opts,
      headers: { 'Authorization': 'Bearer ' + masterToken, 'Content-Type':'application/json', ...(opts.headers||{}) }
    });
  }

  function showDashboard(){
    document.getElementById('loginCard').style.display = 'none';
    const d = document.getElementById('dashboard');
    d.style.display = 'flex';
    refreshUsers(); refreshSessions();
  }

  function logout(){
    masterToken=''; sessionStorage.removeItem('_mt');
    document.getElementById('loginCard').style.display='';
    document.getElementById('dashboard').style.display='none';
  }
  window.logout = logout;

  async function refreshUsers(){
    const tbody = document.getElementById('userTable');
    tbody.innerHTML = '<tr><td colspan="5" class="empty-row">Loading…</td></tr>';
    try {
      const res = await apiFetch('/api/master/users');
      const { users } = await res.json();
      document.getElementById('statTotal').textContent = users.length;
      document.getElementById('statActive').textContent = users.filter(u=>u.is_active).length;
      tbody.innerHTML = users.length ? users.map(u => `
        <tr>
          <td><div style="font-weight:500">${u.full_name||'—'}</div><div style="font-size:11px;color:#7a8599">${u.email}</div></td>
          <td><span class="badge badge-${u.role}">${u.role}</span></td>
          <td><span style="font-family:monospace;font-size:11px">${u.vertical}</span></td>
          <td><span class="badge badge-${u.is_active?'active':'inactive'}">${u.is_active?'Active':'Inactive'}</span></td>
          <td style="display:flex;gap:6px;flex-wrap:wrap">
            <select class="inline-select" onchange="changeRole('${u.id}',this.value)">
              <option value="">role…</option>
              <option value="analyst">analyst</option>
              <option value="senior">senior</option>
              <option value="head">head</option>
            </select>
            <select class="inline-select" onchange="changeVertical('${u.id}',this.value)">
              <option value="">vertical…</option>
              ${['epi','agri','markets','packaging','startups','pharma','all'].map(v=>`<option value="${v}">${v}</option>`).join('')}
            </select>
            <button class="action-btn" onclick="toggleActive('${u.id}',${u.is_active})">${u.is_active?'Deactivate':'Activate'}</button>
            <button class="action-btn danger" onclick="deleteUser('${u.id}','${u.email}')">Delete</button>
          </td>
        </tr>`).join('') : '<tr><td colspan="5" class="empty-row">No analysts found.</td></tr>';
    } catch(_){ tbody.innerHTML='<tr><td colspan="5" class="empty-row">Failed to load.</td></tr>'; }
  }
  window.refreshUsers = refreshUsers;

  async function refreshSessions(){
    const tbody = document.getElementById('sessionTable');
    tbody.innerHTML = '<tr><td colspan="4" class="empty-row">Loading…</td></tr>';
    try {
      const res = await apiFetch('/api/master/audit');
      const { sessions } = await res.json();
      const today = sessions.filter(s=>s.login_at && s.login_at.startsWith(new Date().toISOString().slice(0,10)));
      document.getElementById('statSessions').textContent = today.length;
      tbody.innerHTML = sessions.length ? sessions.slice(0,30).map(s=>`
        <tr>
          <td style="font-size:11px;font-family:monospace">${s.profiles?.email||s.user_id?.slice(0,8)+'…'}</td>
          <td><span class="badge badge-${s.role_at_login}">${s.role_at_login}</span></td>
          <td style="font-family:monospace;font-size:11px">${s.vertical||'—'}</td>
          <td style="font-size:11px;color:#7a8599">${s.login_at ? new Date(s.login_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}) : '—'}</td>
        </tr>`).join('') : '<tr><td colspan="4" class="empty-row">No sessions yet.</td></tr>';
    } catch(_){ tbody.innerHTML='<tr><td colspan="4" class="empty-row">Failed to load.</td></tr>'; }
  }
  window.refreshSessions = refreshSessions;

  async function changeRole(id, role){ if(!role) return; await apiFetch('/api/master/users/'+id, {method:'PATCH',body:JSON.stringify({role})}); showToast('Role updated'); refreshUsers(); }
  async function changeVertical(id, vertical){ if(!vertical) return; await apiFetch('/api/master/users/'+id, {method:'PATCH',body:JSON.stringify({vertical})}); showToast('Vertical updated'); refreshUsers(); }
  async function toggleActive(id, current){ await apiFetch('/api/master/users/'+id, {method:'PATCH',body:JSON.stringify({is_active:!current})}); showToast(current?'User deactivated':'User activated'); refreshUsers(); }
  async function deleteUser(id, email){ if(!confirm('Permanently delete '+email+'?')) return; await apiFetch('/api/master/users/'+id, {method:'DELETE'}); showToast('User deleted'); refreshUsers(); }
  window.changeRole=changeRole; window.changeVertical=changeVertical; window.toggleActive=toggleActive; window.deleteUser=deleteUser;

  let _tt;
  function showToast(msg){ const t=document.getElementById('toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(_tt); _tt=setTimeout(()=>t.classList.remove('show'),2800); }

  /* restore session on page reload */
  const saved = sessionStorage.getItem('_mt');
  if(saved){ masterToken=saved; showDashboard(); }
}());
</script>
</body>
</html>"""


# ── Master auth helpers ────────────────────────────────────────────────────────
def _master_sign(payload: str) -> str:
    """HMAC-SHA256 sign a payload with MASTER_TOKEN as the key."""
    secret = os.environ.get("MASTER_TOKEN", "dev-master-secret-change-me")
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _issue_master_session() -> str:
    """Return a time-stamped signed session token."""
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    payload = f"master:{ts}:{nonce}"
    sig = _master_sign(payload)
    return f"{payload}:{sig}"


def _verify_master_session(token: str) -> bool:
    """Verify the token signature and that it is less than 8 hours old."""
    try:
        parts = token.split(":")
        if len(parts) != 4 or parts[0] != "master":
            return False
        _, ts, nonce, sig = parts
        payload = f"master:{ts}:{nonce}"
        expected = _master_sign(payload)
        if not hmac.compare_digest(expected, sig):
            return False
        age = int(time.time()) - int(ts)
        return age < 28800  # 8 hours
    except Exception:
        return False


def _require_master(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Master token required")
    token = auth.split(" ", 1)[1]
    if not _verify_master_session(token):
        raise HTTPException(status_code=401, detail="Invalid or expired master session")


# ── /master — login page ───────────────────────────────────────────────────────
@app.get("/master", response_class=HTMLResponse, include_in_schema=False)
async def master_page():
    """Master admin login — restricted URL, not linked from any public page."""
    return HTMLResponse(content=_MASTER_HTML)


# ── /api/master/login ─────────────────────────────────────────────────────────
@app.post("/api/master/login", tags=["master"])
async def master_login(request: Request):
    """
    Authenticate as master admin.
    Compares against MASTER_EMAIL and MASTER_PASSWORD env vars.
    Returns a signed session token (8-hour TTL).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    expected_email = os.environ.get("MASTER_EMAIL", "")
    expected_pass  = os.environ.get("MASTER_PASSWORD", "")

    if not expected_email or not expected_pass:
        raise HTTPException(status_code=503, detail="Master credentials not configured")

    email_ok = hmac.compare_digest(body.get("email", ""), expected_email)
    pass_ok   = hmac.compare_digest(body.get("password", ""), expected_pass)

    if not email_ok or not pass_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"token": _issue_master_session(), "expires_in": 28800}


# ── /api/master/users ─────────────────────────────────────────────────────────
@app.get("/api/master/users", tags=["master"])
async def master_list_users(request: Request):
    """List all analyst profiles across all verticals."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    resp = supa.table("profiles")\
        .select("id, email, full_name, role, vertical, is_active, created_at")\
        .order("created_at", desc=True)\
        .execute()
    return {"users": resp.data or []}


@app.patch("/api/master/users/{user_id}", tags=["master"])
async def master_update_user(request: Request, user_id: str):
    """Update a user's role, vertical, or active status."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    allowed_fields = {"role", "vertical", "is_active", "full_name"}
    update = {k: v for k, v in body.items() if k in allowed_fields}

    if "role" in update and update["role"] not in ("analyst", "senior", "head"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if "vertical" in update and update["vertical"] not in ("epi", "agri", "markets", "packaging", "startups", "pharma", "all"):
        raise HTTPException(status_code=400, detail="Invalid vertical")

    if not update:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    supa.table("profiles").update(update).eq("id", user_id).execute()
    return {"status": "updated", "user_id": user_id, "changes": update}


@app.delete("/api/master/users/{user_id}", tags=["master"])
async def master_delete_user(request: Request, user_id: str):
    """Hard-delete a user profile (Supabase auth record is kept — revoke separately)."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    supa.table("profiles").delete().eq("id", user_id).execute()
    return {"status": "deleted", "user_id": user_id}


# ── /api/master/audit ─────────────────────────────────────────────────────────
@app.get("/api/master/audit", tags=["master"])
async def master_audit(request: Request):
    """Full login session audit — all analysts, all verticals, most recent first."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    resp = supa.table("analyst_sessions")\
        .select("id, user_id, role_at_login, vertical, login_at, logout_at, user_agent, profiles(email, full_name)")\
        .order("login_at", desc=True)\
        .limit(200)\
        .execute()
    return {"sessions": resp.data or []}


# ── /api/master/dashboard ─────────────────────────────────────────────────────
@app.get("/api/master/dashboard", tags=["master"])
async def master_dashboard(request: Request):
    """Aggregate stats: user counts by role and vertical, session counts."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    users_resp    = supa.table("profiles").select("role, vertical, is_active").execute()
    sessions_resp = supa.table("analyst_sessions").select("login_at").execute()

    users    = users_resp.data or []
    sessions = sessions_resp.data or []

    from datetime import date
    today = date.today().isoformat()
    sessions_today = [s for s in sessions if s.get("login_at", "").startswith(today)]

    by_role     = {}
    by_vertical = {}
    for u in users:
        by_role[u["role"]] = by_role.get(u["role"], 0) + 1
        by_vertical[u["vertical"]] = by_vertical.get(u["vertical"], 0) + 1

    return {
        "total_users":      len(users),
        "active_users":     sum(1 for u in users if u.get("is_active")),
        "inactive_users":   sum(1 for u in users if not u.get("is_active")),
        "by_role":          by_role,
        "by_vertical":      by_vertical,
        "sessions_total":   len(sessions),
        "sessions_today":   len(sessions_today),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL WORKFLOW ENDPOINTS
# Stage machine: draft → submitted → senior_review → senior_approved →
#                head_review → approved → published  (or → rejected at any review)
# ═══════════════════════════════════════════════════════════════════════════════

STAGE_TRANSITIONS = {
    # (current_stage, action, actor_role) → new_stage
    ("draft",           "submit",  "analyst"): "submitted",
    ("draft",           "submit",  "senior"):  "submitted",
    ("submitted",       "review",  "senior"):  "senior_review",
    ("senior_review",   "approve", "senior"):  "senior_approved",
    ("senior_review",   "reject",  "senior"):  "rejected",
    ("senior_approved", "review",  "head"):    "head_review",
    ("head_review",     "approve", "head"):    "approved",
    ("head_review",     "reject",  "head"):    "rejected",
    ("approved",        "publish", "head"):    "published",
    # head can also submit directly
    ("draft",           "submit",  "head"):    "senior_approved",
}


def _log_activity(supa, *, table_name, record_id, actor, action,
                  field_name=None, old_value=None, new_value=None,
                  note=None, vertical=None):
    """Write one row to activity_log (non-fatal if it fails)."""
    try:
        supa.table("activity_log").insert({
            "table_name": table_name,
            "record_id":  str(record_id),
            "actor_id":   actor.get("id"),
            "actor_name": actor.get("full_name") or actor.get("email"),
            "actor_role": actor.get("role"),
            "action":     action,
            "field_name": field_name,
            "old_value":  str(old_value) if old_value is not None else None,
            "new_value":  str(new_value) if new_value is not None else None,
            "note":       note,
            "vertical":   vertical,
        }).execute()
    except Exception:
        pass


@app.post("/api/reports/{report_id}/workflow", tags=["workflow"])
async def workflow_action(request: Request, report_id: str):
    """
    Drive a report through the approval pipeline.

    Body: { "action": "submit|review|approve|reject|publish", "note": "optional" }

    Rules enforced:
    - Analysts can only submit their own draft reports
    - Senior analysts approve/reject submitted reports in their vertical
    - Head of Research approves/rejects senior-approved reports + publishes
    - Rejected reports go back to 'rejected' stage with a note
    """
    profile = await _resolve_profile(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    action = body.get("action", "").strip()
    note   = body.get("note", "").strip()

    if not action:
        raise HTTPException(status_code=400, detail="action is required")

    # Fetch the report
    resp = supa.table("reports")\
        .select("id, title, stage, vertical, author_id, author_name, assigned_senior_id")\
        .eq("id", report_id).single().execute()

    if not resp.data:
        raise HTTPException(status_code=404, detail="Report not found")

    report = resp.data
    role   = profile["role"]
    uid    = profile.get("id") or ""

    # Vertical access check
    if profile["vertical"] != "all" and profile["vertical"] != report["vertical"]:
        raise HTTPException(status_code=403, detail="You do not have access to this vertical")

    # Analyst can only submit their own reports
    if role == "analyst" and action == "submit" and report.get("author_id") != uid:
        raise HTTPException(status_code=403, detail="You can only submit your own reports")

    current_stage = report["stage"]
    new_stage = STAGE_TRANSITIONS.get((current_stage, action, role))

    if new_stage is None:
        raise HTTPException(
            status_code=422,
            detail=f"Action '{action}' is not allowed for role '{role}' on stage '{current_stage}'"
        )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    update_payload = {
        "stage":           new_stage,
        "stage_entered_at": now,
    }
    if action == "submit":
        update_payload["submitted_at"] = now
    if action in ("reject",):
        update_payload["rejection_note"] = note
        update_payload["rejected_by"]    = uid
        update_payload["rejected_at"]    = now
    if action == "review" and role == "senior":
        update_payload["assigned_senior_id"] = uid

    supa.table("reports").update(update_payload).eq("id", report_id).execute()

    # Workflow event
    try:
        supa.table("workflow_events").insert({
            "report_id":      report_id,
            "from_stage":     current_stage,
            "to_stage":       new_stage,
            "actor_id":       uid,
            "actor_name":     profile.get("full_name") or profile.get("email"),
            "note":           note or None,
            "is_rejection":   action == "reject",
            "rejection_note": note if action == "reject" else None,
        }).execute()
    except Exception:
        pass

    # Activity log
    _log_activity(supa,
        table_name="reports",
        record_id=report_id,
        actor=profile,
        action=action,
        field_name="stage",
        old_value=current_stage,
        new_value=new_stage,
        note=note or None,
        vertical=report["vertical"],
    )

    return {
        "report_id":   report_id,
        "action":      action,
        "from_stage":  current_stage,
        "to_stage":    new_stage,
        "actor_role":  role,
        "note":        note or None,
    }


@app.get("/api/reports", tags=["workflow"])
async def list_reports(request: Request, vertical: str = None, stage: str = None):
    """List reports scoped to the authenticated user's vertical."""
    profile = await _resolve_profile(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    q = supa.table("reports").select(
        "id, title, abstract, vertical, stage, priority, author_name, "
        "due_date, stage_entered_at, submitted_at, rejection_note, "
        "created_at, updated_at, assigned_senior_id, version"
    )

    # Vertical scoping
    user_vertical = profile["vertical"]
    if user_vertical != "all":
        q = q.eq("vertical", user_vertical)
    elif vertical:
        q = q.eq("vertical", vertical)

    if stage:
        q = q.eq("stage", stage)

    q = q.order("updated_at", desc=True)
    resp = q.execute()
    return {"reports": resp.data or []}


@app.get("/api/reports/{report_id}/history", tags=["workflow"])
async def report_history(request: Request, report_id: str):
    """Full workflow history for one report."""
    profile = await _resolve_profile(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    resp = supa.table("workflow_events")\
        .select("from_stage, to_stage, actor_name, actor_id, note, is_rejection, created_at")\
        .eq("report_id", report_id)\
        .order("created_at", desc=False)\
        .execute()
    return {"history": resp.data or []}


# ── /api/activity ─────────────────────────────────────────────────────────────
@app.get("/api/activity", tags=["workflow"])
async def activity_feed(request: Request, limit: int = 50):
    """Recent activity log — scoped to user's vertical."""
    profile = await _resolve_profile(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    q = supa.table("activity_log").select(
        "id, table_name, action, field_name, old_value, new_value, "
        "actor_name, actor_role, note, vertical, created_at"
    )
    if profile["vertical"] != "all":
        q = q.eq("vertical", profile["vertical"])
    q = q.order("created_at", desc=True).limit(min(limit, 200))
    resp = q.execute()
    return {"activity": resp.data or []}


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER GANTT DASHBOARD PAGE
# ═══════════════════════════════════════════════════════════════════════════════

_GANTT_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Workflow Dashboard — Master</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--ink:#06080d;--ink2:#0c0f16;--ink3:#11151e;--ink4:#171c28;--rule:rgba(255,255,255,.06);--rule2:rgba(255,255,255,.1);--white:#eef0f5;--fog:#7a8599;--ghost:#3d4a60;--teal:#2ec4b6;--gold:#c8a96e;--violet:#9b72e8;--sapph:#4a7fe8;--agri:#4caf78;--coral:#e85d4a;--r:6px;color-scheme:dark}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:'Inter',system-ui,sans-serif;background:var(--ink);color:var(--white);-webkit-font-smoothing:antialiased}
.shell{display:grid;grid-template-rows:56px 1fr;min-height:100vh}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:0 28px;background:var(--ink2);border-bottom:1px solid var(--rule2);position:sticky;top:0;z-index:10}
.topbar-left{display:flex;align-items:center;gap:16px}
.logo{font-size:14px;font-weight:600;color:var(--white)}
.logo span{color:var(--gold);font-family:'JetBrains Mono',monospace;font-size:11px;margin-left:8px;letter-spacing:.5px}
.nav-link{font-size:12px;color:var(--fog);text-decoration:none;padding:6px 10px;border-radius:4px;transition:color .15s,background .15s}
.nav-link:hover,.nav-link.active{color:var(--white);background:rgba(255,255,255,.05)}
.topbar-right{display:flex;align-items:center;gap:10px}
.filter-bar{display:flex;align-items:center;gap:8px}
.filter-select{background:var(--ink3);border:1px solid var(--rule2);color:var(--white);border-radius:var(--r);padding:5px 10px;font-size:12px;font-family:'Inter',sans-serif;cursor:pointer}
.refresh-btn{padding:6px 14px;background:transparent;border:1px solid var(--rule2);border-radius:var(--r);font-size:12px;color:var(--fog);cursor:pointer;transition:color .15s}
.refresh-btn:hover{color:var(--white)}
.main{padding:24px 28px;overflow-y:auto;display:flex;flex-direction:column;gap:20px}

/* stat row */
.stats-row{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.stat{padding:14px 16px;background:var(--ink2);border:1px solid var(--rule2);border-radius:8px}
.stat-val{font-size:22px;font-weight:600;margin-bottom:3px}
.stat-label{font-size:10px;color:var(--fog);font-family:'JetBrains Mono',monospace;letter-spacing:.5px}
.stat-val.on-track{color:var(--teal)}
.stat-val.at-risk{color:var(--gold)}
.stat-val.overdue{color:var(--coral)}

/* pipeline swimlanes */
.swimlane-wrap{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--rule);border:1px solid var(--rule2);border-radius:8px;overflow:hidden}
.lane{background:var(--ink2);min-height:300px}
.lane-head{padding:10px 12px;border-bottom:1px solid var(--rule);background:var(--ink3);display:flex;flex-direction:column;gap:3px}
.lane-title{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:var(--fog)}
.lane-count{font-size:18px;font-weight:600;color:var(--white)}
.lane-body{padding:8px;display:flex;flex-direction:column;gap:6px}
.report-card{padding:10px 10px 8px;background:var(--ink3);border:1px solid var(--rule2);border-radius:6px;cursor:pointer;transition:border-color .15s,background .15s;position:relative}
.report-card:hover{background:var(--ink4);border-color:var(--rule2)}
.report-card.on-track{border-left:3px solid var(--teal)}
.report-card.at-risk{border-left:3px solid var(--gold)}
.report-card.overdue{border-left:3px solid var(--coral)}
.rc-title{font-size:11.5px;font-weight:500;color:var(--white);line-height:1.4;margin-bottom:5px}
.rc-meta{font-size:10px;color:var(--fog);display:flex;flex-direction:column;gap:2px}
.rc-vertical{display:inline-block;padding:1px 6px;border-radius:3px;font-family:'JetBrains Mono',monospace;font-size:9px;margin-bottom:4px}
.v-epi{background:rgba(46,196,182,.12);color:#2ec4b6}
.v-agri{background:rgba(76,175,120,.12);color:#4caf78}
.v-trade{background:rgba(74,127,232,.12);color:#4a7fe8}
.v-markets{background:rgba(200,169,110,.12);color:#c8a96e}
.v-packaging{background:rgba(232,93,74,.12);color:#e85d4a}
.v-startups{background:rgba(155,114,232,.12);color:#9b72e8}
.days-badge{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--fog)}
.days-badge.warn{color:var(--gold)}
.days-badge.danger{color:var(--coral)}

/* Gantt timeline */
.gantt-section{background:var(--ink2);border:1px solid var(--rule2);border-radius:8px;overflow:hidden}
.section-head{padding:14px 20px;border-bottom:1px solid var(--rule);display:flex;align-items:center;justify-content:space-between}
.section-title{font-size:13px;font-weight:600;color:var(--white)}
.gantt-wrap{overflow-x:auto;padding:0}
.gantt-table{width:100%;border-collapse:collapse;min-width:900px}
.gantt-table th{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:var(--fog);padding:10px 14px;text-align:left;border-bottom:1px solid var(--rule);white-space:nowrap;position:sticky;top:0;background:var(--ink3)}
.gantt-table td{padding:10px 14px;border-bottom:1px solid var(--rule);font-size:12px;vertical-align:middle}
.gantt-table tr:last-child td{border-bottom:none}
.gantt-table tr:hover td{background:rgba(255,255,255,.018)}
.progress-cell{min-width:180px}
.progress-track{height:6px;background:rgba(255,255,255,.07);border-radius:3px;overflow:hidden;position:relative}
.progress-bar{height:100%;border-radius:3px;transition:width .3s}
.bar-draft{background:var(--ghost)}
.bar-submitted{background:var(--sapph)}
.bar-senior_review{background:#5a9af0}
.bar-senior_approved{background:var(--teal)}
.bar-head_review{background:var(--gold)}
.bar-approved{background:#8ed44a}
.bar-published{background:#4cff91}
.bar-rejected{background:var(--coral)}
.stage-label{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.5px;text-transform:uppercase;color:var(--fog);margin-top:4px}
.priority-dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:5px;flex-shrink:0}
.p-high{background:var(--coral)}
.p-med{background:var(--gold)}
.p-low{background:var(--ghost)}

/* activity feed */
.activity-section{background:var(--ink2);border:1px solid var(--rule2);border-radius:8px;overflow:hidden}
.activity-list{padding:0;max-height:320px;overflow-y:auto}
.activity-row{display:flex;align-items:flex-start;gap:12px;padding:11px 20px;border-bottom:1px solid var(--rule)}
.activity-row:last-child{border-bottom:none}
.activity-icon{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-top:1px}
.icon-submit{background:rgba(74,127,232,.15)}
.icon-approve{background:rgba(46,196,182,.15)}
.icon-reject{background:rgba(232,93,74,.15)}
.icon-publish{background:rgba(76,175,120,.15)}
.icon-update{background:rgba(155,114,232,.15)}
.activity-body{flex:1;min-width:0}
.activity-desc{font-size:12px;color:var(--white);line-height:1.5}
.activity-desc strong{font-weight:600}
.activity-meta{font-size:10.5px;color:var(--fog);margin-top:2px;font-family:'JetBrains Mono',monospace}

/* modal */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:100;padding:20px}
.modal-overlay.open{display:flex}
.modal{background:var(--ink2);border:1px solid var(--rule2);border-radius:12px;width:100%;max-width:520px;overflow:hidden}
.modal-head{padding:18px 24px;border-bottom:1px solid var(--rule);display:flex;align-items:center;justify-content:space-between}
.modal-title{font-size:14px;font-weight:600;color:var(--white)}
.modal-close{background:none;border:none;color:var(--fog);font-size:18px;cursor:pointer;padding:2px 6px}
.modal-body{padding:20px 24px;display:flex;flex-direction:column;gap:12px}
.history-row{display:flex;gap:12px;align-items:flex-start}
.history-dot{width:8px;height:8px;border-radius:50%;background:var(--teal);flex-shrink:0;margin-top:5px}
.history-dot.reject{background:var(--coral)}
.history-content{flex:1}
.history-stage{font-size:12px;font-weight:500;color:var(--white)}
.history-meta{font-size:11px;color:var(--fog);margin-top:2px}
.empty-msg{text-align:center;padding:28px;color:var(--fog);font-style:italic;font-size:13px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(10px);background:var(--ink4);border:1px solid var(--rule2);border-radius:20px;padding:9px 18px;font-size:12px;color:var(--white);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;z-index:999}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
@media(max-width:900px){.stats-row{grid-template-columns:repeat(3,1fr)}.swimlane-wrap{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">
  <div class="topbar">
    <div class="topbar-left">
      <div class="logo">Intelligence Platform <span>MASTER WORKFLOW</span></div>
      <a href="/master" class="nav-link">← Console</a>
    </div>
    <div class="topbar-right">
      <div class="filter-bar">
        <select class="filter-select" id="filterVertical" onchange="applyFilters()">
          <option value="">All verticals</option>
          <option value="epi">Epidemiology</option>
          <option value="agri">Agriculture</option>
          <option value="pharma">Pharma Intelligence</option>
          <option value="markets">Markets</option>
          <option value="packaging">Packaging</option>
          <option value="startups">Startups</option>
        </select>
        <select class="filter-select" id="filterPriority" onchange="applyFilters()">
          <option value="">All priorities</option>
          <option value="high">High</option>
          <option value="med">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>
      <button class="refresh-btn" onclick="loadAll()">↻ Refresh</button>
    </div>
  </div>

  <div class="main">
    <!-- Stat cards -->
    <div class="stats-row">
      <div class="stat"><div class="stat-val" id="sTotal">—</div><div class="stat-label">Total reports</div></div>
      <div class="stat"><div class="stat-val" id="sDraft">—</div><div class="stat-label">In draft</div></div>
      <div class="stat"><div class="stat-val" id="sReview">—</div><div class="stat-label">In review</div></div>
      <div class="stat on-track"><div class="stat-val on-track" id="sPublished">—</div><div class="stat-label">Published</div></div>
      <div class="stat"><div class="stat-val at-risk" id="sAtRisk">—</div><div class="stat-label">At risk</div></div>
      <div class="stat"><div class="stat-val overdue" id="sOverdue">—</div><div class="stat-label">Overdue / stuck</div></div>
    </div>

    <!-- Swimlane pipeline -->
    <div class="swimlane-wrap" id="swimlanes">
      <!-- filled by JS -->
    </div>

    <!-- Gantt table -->
    <div class="gantt-section">
      <div class="section-head">
        <div class="section-title">Report Pipeline — Detail View</div>
      </div>
      <div class="gantt-wrap">
        <table class="gantt-table">
          <thead><tr>
            <th>Report</th><th>Vertical</th><th>Author</th>
            <th>Priority</th><th>Stage progress</th><th>Days in stage</th><th>Due date</th>
          </tr></thead>
          <tbody id="ganttBody"></tbody>
        </table>
      </div>
    </div>

    <!-- Activity feed -->
    <div class="activity-section">
      <div class="section-head">
        <div class="section-title">Activity Log</div>
      </div>
      <div class="activity-list" id="activityList"></div>
    </div>
  </div>
</div>

<!-- Report detail modal -->
<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-head">
      <div class="modal-title" id="modalTitle">Report history</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modalBody"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
(function(){
  const MT = sessionStorage.getItem('_mt') || '';
  if(!MT){ window.location.href='/master'; return; }

  const STAGES = ['draft','submitted','senior_review','senior_approved','head_review','approved','published','rejected'];
  const STAGE_LABELS = {
    draft:'Draft', submitted:'Submitted', senior_review:'Senior Review',
    senior_approved:'Sr. Approved', head_review:'Head Review',
    approved:'Approved', published:'Published', rejected:'Rejected'
  };
  const STAGE_PCT = {
    draft:5, submitted:20, senior_review:35, senior_approved:55,
    head_review:72, approved:88, published:100, rejected:0
  };
  const V_CLASS = {epi:'v-epi',agri:'v-agri',markets:'v-markets',packaging:'v-packaging',startups:'v-startups',pharma:'v-pharma'};

  let allReports = [], allActivity = [];

  async function apiFetch(path){
    const r = await fetch(path, {headers:{'Authorization':'Bearer '+MT}});
    if(r.status===401){ window.location.href='/master'; throw new Error('unauth'); }
    return r.json();
  }

  async function loadAll(){
    try {
      const [rr, aa] = await Promise.all([
        apiFetch('/api/master/reports'),
        apiFetch('/api/master/activity')
      ]);
      allReports   = rr.reports   || [];
      allActivity  = aa.activity  || [];
      applyFilters();
      renderActivity(allActivity);
    } catch(e){ if(e.message!=='unauth') showToast('Failed to load data'); }
  }

  function applyFilters(){
    const v = document.getElementById('filterVertical').value;
    const p = document.getElementById('filterPriority').value;
    let reports = allReports;
    if(v) reports = reports.filter(r=>r.vertical===v);
    if(p) reports = reports.filter(r=>r.priority===p);
    renderStats(reports);
    renderSwimlanes(reports);
    renderGantt(reports);
  }

  function daysInStage(r){
    if(!r.stage_entered_at) return 0;
    return Math.floor((Date.now()-new Date(r.stage_entered_at))/(1000*60*60*24));
  }

  function statusClass(r){
    const days = daysInStage(r);
    if(r.stage==='rejected') return 'overdue';
    if(r.due_date && new Date(r.due_date)<new Date()) return 'overdue';
    if(days>5) return 'at-risk';
    return 'on-track';
  }

  function renderStats(reports){
    const inReview = ['submitted','senior_review','senior_approved','head_review','approved'];
    document.getElementById('sTotal').textContent     = reports.length;
    document.getElementById('sDraft').textContent     = reports.filter(r=>r.stage==='draft').length;
    document.getElementById('sReview').textContent    = reports.filter(r=>inReview.includes(r.stage)).length;
    document.getElementById('sPublished').textContent = reports.filter(r=>r.stage==='published').length;
    document.getElementById('sAtRisk').textContent    = reports.filter(r=>statusClass(r)==='at-risk').length;
    document.getElementById('sOverdue').textContent   = reports.filter(r=>statusClass(r)==='overdue').length;
  }

  function renderSwimlanes(reports){
    const lanes = ['draft','submitted','senior_review','senior_approved','head_review','approved','published'];
    document.getElementById('swimlanes').innerHTML = lanes.map(stage=>{
      const cards = reports.filter(r=>r.stage===stage);
      return `<div class="lane">
        <div class="lane-head"><div class="lane-title">${STAGE_LABELS[stage]}</div><div class="lane-count">${cards.length}</div></div>
        <div class="lane-body">${cards.length ? cards.map(r=>{
          const sc = statusClass(r), days=daysInStage(r);
          return `<div class="report-card ${sc}" onclick="openModal('${r.id}','${esc(r.title)}')">
            <span class="rc-vertical ${V_CLASS[r.vertical]||''}">${r.vertical}</span>
            <div class="rc-title">${esc(r.title)}</div>
            <div class="rc-meta">
              <span>${r.author_name||'Unknown'}</span>
              <span class="days-badge ${days>5?'warn':''} ${days>10?'danger':''}">${days}d in stage</span>
            </div>
          </div>`;}).join('') : '<div style="padding:12px;font-size:11px;color:#3d4a60;text-align:center">Empty</div>'}</div>
      </div>`;
    }).join('');
  }

  function renderGantt(reports){
    const sorted = [...reports].sort((a,b)=>new Date(b.updated_at)-new Date(a.updated_at));
    document.getElementById('ganttBody').innerHTML = sorted.length ? sorted.map(r=>{
      const days=daysInStage(r), sc=statusClass(r), pct=STAGE_PCT[r.stage]||0;
      const due = r.due_date ? new Date(r.due_date).toLocaleDateString('en-IN') : '—';
      const daysClass = days>10?'danger':days>5?'warn':'';
      return `<tr>
        <td style="max-width:200px"><div style="font-weight:500;font-size:12.5px">${esc(r.title)}</div></td>
        <td><span class="rc-vertical ${V_CLASS[r.vertical]||''}">${r.vertical}</span></td>
        <td style="font-size:11.5px;color:#7a8599">${r.author_name||'—'}</td>
        <td><span class="priority-dot p-${r.priority||'med'}"></span>${r.priority||'med'}</td>
        <td class="progress-cell">
          <div class="progress-track"><div class="progress-bar bar-${r.stage}" style="width:${pct}%"></div></div>
          <div class="stage-label">${STAGE_LABELS[r.stage]||r.stage}</div>
        </td>
        <td><span class="days-badge ${daysClass}">${days}d</span></td>
        <td style="font-size:11px;font-family:monospace">${due}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="7" class="empty-msg">No reports found.</td></tr>';
  }

  function renderActivity(activity){
    const icons = {submit:'📤',approve:'✅',reject:'❌',publish:'🚀',update:'✏️',create:'➕',delete:'🗑️'};
    document.getElementById('activityList').innerHTML = activity.length ? activity.slice(0,50).map(a=>{
      const when = a.created_at ? new Date(a.created_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour12:true}) : '';
      let desc = `<strong>${a.actor_name||'Someone'}</strong> ${a.action}d`;
      if(a.field_name) desc += ` <em>${a.field_name}</em>`;
      if(a.old_value && a.new_value) desc += ` from <code style="font-family:monospace;font-size:10.5px;color:#9b72e8">${esc(a.old_value)}</code> → <code style="font-family:monospace;font-size:10.5px;color:#2ec4b6">${esc(a.new_value)}</code>`;
      if(a.note) desc += ` <span style="color:#7a8599">— "${esc(a.note)}"</span>`;
      return `<div class="activity-row">
        <div class="activity-icon icon-${a.action}">${icons[a.action]||'•'}</div>
        <div class="activity-body">
          <div class="activity-desc">${desc}</div>
          <div class="activity-meta">${when}${a.vertical?' · '+a.vertical:''}</div>
        </div>
      </div>`;
    }).join('') : '<div class="empty-msg">No activity yet.</div>';
  }

  async function openModal(id, title){
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = '<div class="empty-msg">Loading…</div>';
    document.getElementById('modalOverlay').classList.add('open');
    try {
      const data = await apiFetch('/api/reports/'+id+'/history');
      const h = data.history||[];
      document.getElementById('modalBody').innerHTML = h.length ? h.map(e=>`
        <div class="history-row">
          <div class="history-dot ${e.is_rejection?'reject':''}"></div>
          <div class="history-content">
            <div class="history-stage">${STAGE_LABELS[e.from_stage]||e.from_stage} → ${STAGE_LABELS[e.to_stage]||e.to_stage}</div>
            <div class="history-meta">${e.actor_name||'Unknown'} · ${e.created_at?new Date(e.created_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour12:true}):''}</div>
            ${e.note?`<div style="font-size:11px;color:#c8a96e;margin-top:3px">"${esc(e.note)}"</div>`:''}
          </div>
        </div>`).join('') : '<div class="empty-msg">No workflow events yet.</div>';
    } catch(_){ document.getElementById('modalBody').innerHTML='<div class="empty-msg">Failed to load history.</div>'; }
  }
  window.openModal=openModal;

  function closeModal(){ document.getElementById('modalOverlay').classList.remove('open'); }
  window.closeModal=closeModal;

  function esc(s){ const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

  let _tt;
  function showToast(msg){ const t=document.getElementById('toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(_tt); _tt=setTimeout(()=>t.classList.remove('show'),2800); }

  loadAll();
  setInterval(loadAll, 60000); // auto-refresh every minute
}());
</script>
</body>
</html>"""


# ── Master reports + activity endpoints (service-role reads) ──────────────────
@app.get("/api/master/reports", tags=["master"])
async def master_reports(request: Request, vertical: str = None, stage: str = None):
    """All reports across all verticals — master only."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    q = supa.table("reports").select(
        "id, title, vertical, stage, priority, author_name, author_id, "
        "due_date, stage_entered_at, submitted_at, rejection_note, "
        "created_at, updated_at, version"
    )
    if vertical:
        q = q.eq("vertical", vertical)
    if stage:
        q = q.eq("stage", stage)
    q = q.order("updated_at", desc=True)
    resp = q.execute()
    return {"reports": resp.data or []}


@app.get("/api/master/activity", tags=["master"])
async def master_activity(request: Request, limit: int = 100):
    """Full activity log across all verticals — master only."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    resp = supa.table("activity_log")\
        .select("id, table_name, action, field_name, old_value, new_value, actor_name, actor_role, note, vertical, created_at")\
        .order("created_at", desc=True)\
        .limit(min(limit, 500))\
        .execute()
    return {"activity": resp.data or []}


@app.patch("/api/master/reports/{report_id}", tags=["master"])
async def master_update_report(request: Request, report_id: str):
    """Edit report fields — master only."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    allowed = {"title", "abstract", "stage", "priority", "due_date", "version", "author_name"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="No valid fields")
    if "stage" in update:
        update["stage_entered_at"] = __import__("datetime").datetime.utcnow().isoformat()
    supa.table("reports").update(update).eq("id", report_id).execute()
    return {"status": "updated", "report_id": report_id, "changes": update}


@app.delete("/api/master/reports/{report_id}", tags=["master"])
async def master_delete_report(request: Request, report_id: str):
    """Hard-delete a report — master only."""
    _require_master(request)
    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    supa.table("reports").delete().eq("id", report_id).execute()
    return {"status": "deleted", "report_id": report_id}


# ── /api/upload/{deliverable_type} ───────────────────────────────────────────
VALID_DELIVERABLE_TYPES = {"report", "model", "deck", "data"}
VALID_VERTICALS = {"epi", "agri", "markets", "packaging", "startups", "pharma"}
ALLOWED_EXTENSIONS = {
    "report": {"docx", "pdf"},
    "model":  {"xlsx", "xlsm"},
    "deck":   {"pptx"},
    "data":   {"csv", "json"},
}

def _get_supa_service():
    """Service-role Supabase client for Storage operations (bypasses RLS)."""
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None


@app.post("/api/upload/{deliverable_type}", tags=["deliverables"])
async def upload_deliverable(
    request: Request,
    deliverable_type: str,
    file: UploadFile = File(...),
    vertical:    str = Form(...),
    report_id:   str = Form(""),
    model_title: str = Form(""),
    asof:        str = Form(""),
    # optional metadata fields — stored in platform_tabs JSONB
    version:     str = Form(""),
    coverage:    str = Form(""),
    notes:       str = Form(""),
    vis:         str = Form("public"),
    # model-specific
    baseyear:    str = Form(""),
    model_type:  str = Form(""),
    sheets:      str = Form(""),
    sources:     str = Form(""),
    # deck-specific
    slides:      str = Form(""),
    presdate:    str = Form(""),
    audience:    str = Form(""),
    brand:       str = Form(""),
    # data-specific
    period:      str = Form(""),
    geo:         str = Form(""),
    nextupdate:  str = Form(""),
    publish:     str = Form("public"),
    # report-specific
    pages:       str = Form(""),
):
    """
    Upload a deliverable file (report/model/deck/data) for a vertical.
    Requires senior or head role. Stores bytes in Supabase Storage bucket
    'deliverables' and inserts a row into model_uploads.
    """
    # ── auth: resolve profile ──────────────────────────────────────────────────
    profile = await _resolve_profile(request)
    if profile["role"] not in ("senior", "head"):
        raise HTTPException(status_code=403, detail="Upload requires senior or head role")

    # ── validate deliverable_type ──────────────────────────────────────────────
    if deliverable_type not in VALID_DELIVERABLE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid deliverable type. Must be one of: {sorted(VALID_DELIVERABLE_TYPES)}")

    # ── validate vertical ──────────────────────────────────────────────────────
    if vertical not in VALID_VERTICALS:
        raise HTTPException(status_code=400, detail=f"Invalid vertical. Must be one of: {sorted(VALID_VERTICALS)}")

    # ── vertical access check (analysts can only upload to their own vertical) ─
    profile_vertical = profile.get("vertical", "")
    if profile_vertical != "all" and profile_vertical != vertical:
        raise HTTPException(status_code=403, detail=f"You are assigned to '{profile_vertical}' and cannot upload to '{vertical}'")

    # ── validate file extension ────────────────────────────────────────────────
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = ALLOWED_EXTENSIONS.get(deliverable_type, set())
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid file type '.{ext}' for {deliverable_type}. Allowed: {sorted(allowed)}")

    # ── read file bytes ────────────────────────────────────────────────────────
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}")

    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 50 MB")

    # ── build storage path ─────────────────────────────────────────────────────
    file_id = str(uuid.uuid4())
    safe_name = filename.replace(" ", "_")
    storage_path = f"{vertical}/{deliverable_type}/{file_id}/{safe_name}"

    # ── upload to Supabase Storage ─────────────────────────────────────────────
    supa = _get_supa_service()
    if not supa:
        raise HTTPException(status_code=503, detail="Storage service not configured")

    try:
        supa.storage.from_("deliverables").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {exc}")

    # ── build signed URL (1 week TTL) ──────────────────────────────────────────
    try:
        signed = supa.storage.from_("deliverables").create_signed_url(storage_path, 604800)
        signed_url = signed.get("signedURL") or signed.get("signedUrl") or ""
    except Exception:
        signed_url = ""

    # ── build platform_tabs JSONB payload ─────────────────────────────────────
    platform_tabs: dict = {}
    if asof:
        platform_tabs["asof"] = asof
    if version:
        platform_tabs["version"] = version
    if coverage:
        platform_tabs["coverage"] = coverage
    if notes:
        platform_tabs["notes"] = notes
    if vis:
        platform_tabs["vis"] = vis
    # type-specific fields
    if deliverable_type == "model":
        for k, v in [("baseyear", baseyear), ("model_type", model_type), ("sheets", sheets), ("sources", sources)]:
            if v: platform_tabs[k] = v
    elif deliverable_type == "deck":
        for k, v in [("slides", slides), ("presdate", presdate), ("audience", audience), ("brand", brand)]:
            if v: platform_tabs[k] = v
    elif deliverable_type == "data":
        for k, v in [("period", period), ("geo", geo), ("nextupdate", nextupdate), ("publish", publish)]:
            if v: platform_tabs[k] = v
    elif deliverable_type == "report":
        for k, v in [("pages", pages)]:
            if v: platform_tabs[k] = v

    # ── insert row into model_uploads ──────────────────────────────────────────
    row = {
        "id":           file_id,
        "file_type":    deliverable_type,
        "model_title":  model_title or filename,
        "vertical":     vertical,
        "status":       "submitted",
        "visibility":   vis or "public",
        "platform_tabs": platform_tabs,
        "storage_path": storage_path,
        "created_at":   datetime.datetime.utcnow().isoformat(),
    }
    if report_id:
        row["report_id"] = report_id

    try:
        supa.table("model_uploads").insert(row).execute()
    except Exception as exc:
        # Storage file is already uploaded — log but don't fail silently
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}")

    # Activity log
    _log_activity(supa,
        table_name="model_uploads",
        record_id=file_id,
        actor=profile,
        action="upload",
        field_name="file_type",
        new_value=deliverable_type,
        note=f"Uploaded {filename} ({deliverable_type}) for {vertical}",
        vertical=vertical,
    )

    return {
        "id":           file_id,
        "storage_path": storage_path,
        "signed_url":   signed_url,
        "status":       "submitted",
        "deliverable_type": deliverable_type,
        "vertical":     vertical,
    }


# ── /api/deliverables/{vertical} ──────────────────────────────────────────────
@app.get("/api/deliverables/{vertical}", tags=["deliverables"])
async def get_deliverables(request: Request, vertical: str, limit: int = 20):
    """
    Returns all deliverable uploads for a vertical, newest first.
    Requires valid Supabase auth. Users can only view their own vertical
    (or all verticals if vertical=='all').
    """
    profile = await _resolve_profile(request)

    if vertical not in VALID_VERTICALS:
        raise HTTPException(status_code=400, detail=f"Invalid vertical: {vertical}")

    profile_vertical = profile.get("vertical", "")
    if profile_vertical != "all" and profile_vertical != vertical:
        raise HTTPException(status_code=403, detail=f"Access denied for vertical '{vertical}'")

    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    try:
        resp = (
            supa.table("model_uploads")
            .select("id, file_type, model_title, status, created_at, platform_tabs, storage_path, visibility")
            .eq("vertical", vertical)
            .order("created_at", desc=True)
            .limit(min(limit, 100))
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")

    rows = resp.data or []

    # Enrich each row with a fresh signed URL and age info
    supa_svc = _get_supa_service()
    now_ts = datetime.datetime.utcnow()
    enriched = []
    for r in rows:
        # Compute data age in days from asof date in platform_tabs
        asof_val = (r.get("platform_tabs") or {}).get("asof", "")
        age_days: Optional[int] = None
        if asof_val:
            try:
                asof_dt = datetime.datetime.fromisoformat(asof_val)
                age_days = (now_ts - asof_dt).days
            except Exception:
                pass

        # Fresh signed URL (1 week TTL) if storage_path present
        signed_url = ""
        if supa_svc and r.get("storage_path"):
            try:
                signed = supa_svc.storage.from_("deliverables").create_signed_url(r["storage_path"], 604800)
                signed_url = signed.get("signedURL") or signed.get("signedUrl") or ""
            except Exception:
                pass

        enriched.append({
            **r,
            "age_days":  age_days,
            "signed_url": signed_url,
        })

    return {"vertical": vertical, "deliverables": enriched, "count": len(enriched)}


# ── /api/deliverables/{id}/status ────────────────────────────────────────────
# Workflow state machine for deliverable approval pipeline:
#   submitted → senior_approved → approved → published
#   any stage → rejected  (with optional note)
#
# Role permissions:
#   senior : submitted → senior_approved | submitted → rejected
#   head   : senior_approved → approved | approved → published | any → rejected

WORKFLOW_TRANSITIONS = {
    # (current_status, role) → allowed next statuses
    ("submitted",       "senior"): {"senior_approved", "rejected"},
    ("submitted",       "head"):   {"senior_approved", "approved", "rejected"},
    ("senior_approved", "head"):   {"approved", "rejected"},
    ("approved",        "head"):   {"published", "rejected"},
}


@app.patch("/api/deliverables/{deliverable_id}/status", tags=["deliverables"])
async def update_deliverable_status(request: Request, deliverable_id: str):
    """
    Advance or reject a deliverable through the approval pipeline.
    Body: { "status": "approved"|"rejected"|..., "note": "optional reason" }
    """
    profile = await _resolve_profile(request)
    role = profile.get("role", "")
    if role not in ("senior", "head"):
        raise HTTPException(status_code=403, detail="Only senior or head can update deliverable status")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    new_status = (body.get("status") or "").strip()
    note = (body.get("note") or "").strip()

    if not new_status:
        raise HTTPException(status_code=400, detail="'status' field is required")

    supa = _get_supa_service() or _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    # Fetch current row
    try:
        row_resp = (
            supa.table("model_uploads")
            .select("id, status, vertical, file_type")
            .eq("id", deliverable_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {exc}")

    if not row_resp.data:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    row = row_resp.data
    current_status = row.get("status", "")

    # Vertical access check
    profile_vertical = profile.get("vertical", "")
    if profile_vertical != "all" and profile_vertical != row.get("vertical", ""):
        raise HTTPException(status_code=403, detail="Access denied for this vertical")

    # Validate transition
    allowed = WORKFLOW_TRANSITIONS.get((current_status, role), set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Role '{role}' cannot move status from '{current_status}' to '{new_status}'. "
                   f"Allowed transitions: {sorted(allowed) or 'none'}"
        )

    # Build update payload
    update: dict = {"status": new_status}
    if note:
        update["reviewer_notes"] = note

    try:
        supa.table("model_uploads").update(update).eq("id", deliverable_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Update failed: {exc}")

    # Activity log
    _log_activity(supa,
        table_name="model_uploads",
        record_id=deliverable_id,
        actor=profile,
        action="status_change",
        field_name="status",
        old_value=current_status,
        new_value=new_status,
        note=note or None,
        vertical=row.get("vertical"),
    )

    return {
        "id":         deliverable_id,
        "status":     new_status,
        "prev_status": current_status,
        "note":       note or None,
        "updated_by": profile.get("email", ""),
        "role":       role,
    }


# ── /api/ingest/{deliverable_id} ──────────────────────────────────────────────
# Parses an uploaded data file (CSV / JSON) from Supabase Storage and
# upserts structured rows into the topline_data table.
# Called automatically after a data file upload, or manually by senior/head.

@app.post("/api/ingest/{deliverable_id}", tags=["deliverables"])
async def ingest_topline(request: Request, deliverable_id: str):
    """
    Download a data deliverable from Storage, parse CSV/JSON rows,
    upsert into topline_data. Requires senior or head role.
    """
    profile = await _resolve_profile(request)
    if profile.get("role") not in ("senior", "head"):
        raise HTTPException(status_code=403, detail="Ingest requires senior or head role")

    supa = _get_supa_service() or _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    # Fetch the deliverable row
    try:
        row_resp = (
            supa.table("model_uploads")
            .select("id, file_type, vertical, storage_path, platform_tabs, report_id, status")
            .eq("id", deliverable_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {exc}")

    if not row_resp.data:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    row = row_resp.data
    if row.get("file_type") not in ("data", "csv", "json"):
        raise HTTPException(status_code=400, detail="Only data deliverables (CSV/JSON) can be ingested")

    storage_path = row.get("storage_path", "")
    if not storage_path:
        raise HTTPException(status_code=400, detail="No storage_path on this deliverable")

    # Vertical access check
    profile_vertical = profile.get("vertical", "")
    if profile_vertical != "all" and profile_vertical != row.get("vertical", ""):
        raise HTTPException(status_code=403, detail="Access denied for this vertical")

    # Download file bytes from Supabase Storage
    try:
        file_bytes = supa.storage.from_("deliverables").download(storage_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Storage download failed: {exc}")

    # Parse CSV or JSON
    import io
    import csv as csv_mod
    import json as json_mod

    rows_parsed = []
    ext = storage_path.rsplit(".", 1)[-1].lower() if "." in storage_path else ""
    asof_str = (row.get("platform_tabs") or {}).get("asof", "")

    try:
        if ext == "json":
            payload = json_mod.loads(file_bytes)
            if isinstance(payload, list):
                data_rows = payload
            elif isinstance(payload, dict) and "rows" in payload:
                data_rows = payload["rows"]
            elif isinstance(payload, dict) and "data" in payload:
                data_rows = payload["data"]
            else:
                data_rows = [payload]
            for dr in data_rows:
                if not isinstance(dr, dict):
                    continue
                rows_parsed.append({
                    "vertical":   row["vertical"],
                    "upload_id":  deliverable_id,
                    "report_id":  row.get("report_id"),
                    "metric":     str(dr.get("metric", dr.get("name", "Unknown"))),
                    "geography":  str(dr.get("geography", dr.get("geo", "")) or ""),
                    "period":     str(dr.get("period", "") or ""),
                    "value":      _safe_float(dr.get("value")),
                    "unit":       str(dr.get("unit", "") or ""),
                    "delta":      str(dr.get("delta", "") or ""),
                    "dir":        _clean_dir(dr.get("dir", "")),
                    "asof":       asof_str or None,
                })
        else:
            # CSV — expected columns: metric, geography, period, value, unit, delta, dir
            text = file_bytes.decode("utf-8", errors="replace")
            reader = csv_mod.DictReader(io.StringIO(text))
            for dr in reader:
                rows_parsed.append({
                    "vertical":   row["vertical"],
                    "upload_id":  deliverable_id,
                    "report_id":  row.get("report_id"),
                    "metric":     str(dr.get("metric", dr.get("name", "Unknown"))),
                    "geography":  str(dr.get("geography", dr.get("geo", "")) or ""),
                    "period":     str(dr.get("period", "") or ""),
                    "value":      _safe_float(dr.get("value")),
                    "unit":       str(dr.get("unit", "") or ""),
                    "delta":      str(dr.get("delta", "") or ""),
                    "dir":        _clean_dir(dr.get("dir", "")),
                    "asof":       asof_str or None,
                })
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Parse failed: {exc}")

    if not rows_parsed:
        raise HTTPException(status_code=422, detail="No data rows found in file")

    # Limit to 500 rows per upload
    rows_parsed = rows_parsed[:500]

    # Delete old rows for this upload_id, then insert fresh
    try:
        supa.table("topline_data").delete().eq("upload_id", deliverable_id).execute()
        supa.table("topline_data").insert(rows_parsed).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database write failed: {exc}")

    # Activity log
    _log_activity(supa,
        table_name="topline_data",
        record_id=deliverable_id,
        actor=profile,
        action="ingest",
        field_name="rows_ingested",
        new_value=str(len(rows_parsed)),
        note=f"Ingested {len(rows_parsed)} topline rows from {storage_path.split('/')[-1]}",
        vertical=row["vertical"],
    )

    return {
        "deliverable_id": deliverable_id,
        "rows_ingested":  len(rows_parsed),
        "vertical":       row["vertical"],
        "asof":           asof_str or None,
    }


def _safe_float(v) -> Optional[float]:
    """Convert value to float, return None if not parseable."""
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _clean_dir(v) -> str:
    """Normalise direction field to 'up'|'down'|'flat'|''."""
    s = str(v or "").strip().lower()
    if s in ("up", "↑", "+", "increase", "rise"):
        return "up"
    if s in ("down", "↓", "-", "decrease", "fall"):
        return "down"
    if s in ("flat", "→", "0", "stable", "neutral"):
        return "flat"
    return ""


# ── /api/topline/{vertical} ───────────────────────────────────────────────────
@app.get("/api/topline/{vertical}", tags=["deliverables"])
async def get_topline(request: Request, vertical: str, limit: int = 50):
    """Return the latest ingested topline rows for a vertical."""
    profile = await _resolve_profile(request)

    if vertical not in VALID_VERTICALS:
        raise HTTPException(status_code=400, detail=f"Invalid vertical: {vertical}")

    profile_vertical = profile.get("vertical", "")
    if profile_vertical != "all" and profile_vertical != vertical:
        raise HTTPException(status_code=403, detail="Access denied")

    supa = _get_supa()
    if not supa:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    try:
        resp = (
            supa.table("topline_data")
            .select("id, metric, geography, period, value, unit, delta, dir, asof, created_at, upload_id")
            .eq("vertical", vertical)
            .order("created_at", desc=True)
            .limit(min(limit, 500))
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")

    return {"vertical": vertical, "rows": resp.data or [], "count": len(resp.data or [])}


# ── Research Requests ────────────────────────────────────────────────────────

VALID_RR_STATUSES = {
    "draft", "pending_approval", "approved",
    "in_progress", "review", "published", "delivered"
}

# Status transitions: (current_status, role) → allowed next statuses
RR_TRANSITIONS = {
    ("draft",            "senior"): {"pending_approval"},
    ("draft",            "head"):   {"pending_approval", "approved"},
    ("draft",            "master"): VALID_RR_STATUSES,
    ("pending_approval", "head"):   {"approved", "draft"},
    ("pending_approval", "master"): VALID_RR_STATUSES,
    ("approved",         "head"):   {"in_progress", "draft"},
    ("approved",         "master"): VALID_RR_STATUSES,
    ("in_progress",      "head"):   {"review", "approved"},
    ("in_progress",      "master"): VALID_RR_STATUSES,
    ("review",           "head"):   {"published", "in_progress"},
    ("review",           "master"): VALID_RR_STATUSES,
    ("published",        "head"):   {"delivered"},
    ("published",        "master"): VALID_RR_STATUSES,
    ("delivered",        "master"): VALID_RR_STATUSES,
}


@app.post("/api/research-requests", tags=["research-requests"])
async def create_research_request(request: Request):
    """Create a research request. head or senior only."""
    profile = _resolve_profile(request)
    if profile["role"] not in ("head", "senior", "master"):
        raise HTTPException(status_code=403, detail="head, senior, or master role required")

    body = await request.json()

    vertical = body.get("vertical", "").strip()
    if not vertical:
        raise HTTPException(status_code=400, detail="vertical is required")

    # senior can only create for their own vertical
    if profile["role"] == "senior" and profile.get("vertical") != vertical:
        raise HTTPException(status_code=403, detail="senior can only create requests for their own vertical")

    title          = body.get("title", "").strip()
    indicator_name = body.get("indicator_name", "").strip()
    if not title or not indicator_name:
        raise HTTPException(status_code=400, detail="title and indicator_name are required")

    # senior starts as pending_approval; head/master can start as approved
    initial_status = "pending_approval" if profile["role"] == "senior" else "approved"

    payload = {
        "vertical":           vertical,
        "title":              title,
        "indicator_name":     indicator_name,
        "scope_geographies":  body.get("scope_geographies", []),
        "period":             body.get("period", ""),
        "client_name":        body.get("client_name", ""),
        "contract_value":     body.get("contract_value"),
        "currency":           body.get("currency", "INR"),
        "crm_deal_id":        body.get("crm_deal_id"),
        "due_date":           body.get("due_date"),
        "notes":              body.get("notes", ""),
        "status":             initial_status,
        "raised_by":          profile["id"],
        "assigned_analyst":   body.get("assigned_analyst"),
        "assigned_senior":    body.get("assigned_senior"),
    }

    # head/master can directly approve — record approver
    if initial_status == "approved":
        payload["approved_by"] = profile["id"]

    supa = _get_supa_service()
    try:
        resp = supa.table("research_requests").insert(payload).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Insert failed: {exc}")

    rr = resp.data[0] if resp.data else payload
    _log_activity(supa,
        table_name="research_requests",
        record_id=rr.get("id"),
        actor=profile,
        action="create",
        new_value=initial_status,
        note=f"Research request created: {title}",
        vertical=vertical,
    )
    return rr


@app.get("/api/research-requests/{vertical}", tags=["research-requests"])
async def list_research_requests(vertical: str, request: Request):
    """List research requests for a vertical (or 'all' for master)."""
    profile = _resolve_profile(request)
    role = profile["role"]

    supa = _get_supa_service()

    # master sees everything; others see their vertical only
    if role == "master":
        if vertical == "all":
            query = supa.table("research_requests").select("*").order("created_at", desc=True)
        else:
            query = supa.table("research_requests").select("*").eq("vertical", vertical).order("created_at", desc=True)
    else:
        if profile.get("vertical") != vertical:
            raise HTTPException(status_code=403, detail="Access denied for this vertical")
        query = supa.table("research_requests").select("*").eq("vertical", vertical).order("created_at", desc=True)

    try:
        resp = query.execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")

    return {"vertical": vertical, "requests": resp.data or [], "count": len(resp.data or [])}


@app.patch("/api/research-requests/{rr_id}/status", tags=["research-requests"])
async def update_research_request_status(rr_id: str, request: Request):
    """Update research request status or fields. Role-gated transitions."""
    profile = _resolve_profile(request)
    role = profile["role"]

    if role not in ("head", "master"):
        # senior can only retract their own draft
        body = await request.json()
        new_status = body.get("status", "")
        if role != "senior" or new_status not in ("draft",):
            raise HTTPException(status_code=403, detail="Insufficient role for this transition")

    body = await request.json() if not locals().get("body") else body
    new_status = body.get("status", "").strip()

    if new_status and new_status not in VALID_RR_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    supa = _get_supa_service()
    try:
        row_resp = supa.table("research_requests").select("*").eq("id", rr_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Research request not found")

    rr = row_resp.data
    if not rr:
        raise HTTPException(status_code=404, detail="Research request not found")

    # Vertical access check
    if role != "master" and rr["vertical"] != profile.get("vertical"):
        raise HTTPException(status_code=403, detail="Access denied for this vertical")

    update_payload = {}

    if new_status and new_status != rr["status"]:
        allowed = RR_TRANSITIONS.get((rr["status"], role), set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot transition from '{rr['status']}' to '{new_status}' as {role}"
            )
        update_payload["status"] = new_status
        if new_status == "approved":
            update_payload["approved_by"] = profile["id"]

    # Allow updating assignment fields
    for field in ("assigned_analyst", "assigned_senior", "due_date", "notes",
                  "contract_value", "client_name", "scope_geographies", "period"):
        if field in body:
            update_payload[field] = body[field]

    if not update_payload:
        return rr

    update_payload["updated_at"] = datetime.datetime.utcnow().isoformat()

    try:
        up_resp = supa.table("research_requests").update(update_payload).eq("id", rr_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Update failed: {exc}")

    updated = up_resp.data[0] if up_resp.data else {**rr, **update_payload}

    if new_status and new_status != rr["status"]:
        _log_activity(supa,
            table_name="research_requests",
            record_id=rr_id,
            actor=profile,
            action="status_change",
            field_name="status",
            old_value=rr["status"],
            new_value=new_status,
            note=body.get("note", ""),
            vertical=rr["vertical"],
        )

    return updated


@app.get("/api/research-requests-all", tags=["research-requests"])
async def list_all_research_requests(request: Request):
    """Master-only: list all research requests across all verticals with revenue aggregates."""
    profile = _resolve_profile(request)
    if profile["role"] != "master":
        raise HTTPException(status_code=403, detail="master role required")

    supa = _get_supa_service()
    try:
        resp = supa.table("research_requests").select("*").order("created_at", desc=True).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")

    rows = resp.data or []

    # Aggregate revenue by status
    revenue = {}
    for r in rows:
        s = r.get("status", "unknown")
        cv = r.get("contract_value") or 0
        revenue[s] = revenue.get(s, 0) + float(cv)

    # Count by vertical
    by_vertical = {}
    for r in rows:
        v = r.get("vertical", "unknown")
        by_vertical[v] = by_vertical.get(v, 0) + 1

    return {
        "requests":    rows,
        "count":       len(rows),
        "revenue_by_status": revenue,
        "count_by_vertical": by_vertical,
    }


# ── Template Generation ───────────────────────────────────────────────────────

# Vertical-specific topline column schemas
VERTICAL_TOPLINE_COLS = {
    "epi":       ["disease", "pathogen", "age_group", "metric", "geography", "period", "value", "unit", "delta", "dir"],
    "agri":      ["crop", "season", "metric", "geography", "period", "value", "unit", "delta", "dir"],
    "trade":     ["hs_code", "trade_flow", "metric", "geography", "period", "value", "unit", "delta", "dir"],
    "markets":   ["asset_class", "instrument", "metric", "geography", "period", "value", "unit", "delta", "dir"],
    "packaging": ["material", "end_use", "metric", "geography", "period", "value", "unit", "delta", "dir"],
    "startups":  ["sector", "stage", "metric", "geography", "period", "value", "unit", "delta", "dir"],
    "pharma":    ["drug", "therapy_area", "brand_generic", "metric", "geography", "period", "value", "unit", "delta", "dir"],
}

VERTICAL_LABEL = {
    "epi": "Epidemiology", "agri": "Agriculture", "trade": "Trade",
    "markets": "Markets", "packaging": "Packaging", "startups": "Startups",
    "pharma": "Pharma Intelligence",
}

VERTICAL_INDICATOR_LABEL = {
    "epi":       "Disease / Indicator",
    "agri":      "Crop / Category",
    "trade":     "Trade Category / HS Code",
    "markets":   "Market Segment / Asset Class",
    "packaging": "Material Type",
    "startups":  "Sector Focus",
    "pharma":    "Drug / Therapy Area",
}

VERTICAL_SECTION_HEADINGS = {
    "epi": ["Executive Summary", "Epidemiological Context", "Surveillance & Methodology",
            "Country Profiles", "Trend Analysis", "Policy Implications", "Data Sources & References"],
    "agri": ["Executive Summary", "Agricultural Overview", "Crop & Season Analysis",
             "Country Profiles", "Supply & Demand Dynamics", "Price & Trade Outlook", "Data Sources & References"],
    "trade": ["Executive Summary", "Trade Environment", "HS Code Breakdown",
              "Country Profiles", "Import & Export Flows", "Policy & Tariff Notes", "Data Sources & References"],
    "markets": ["Executive Summary", "Market Overview", "Asset Class Analysis",
                "Country Profiles", "Valuation & Pricing", "Macro & Risk Factors", "Data Sources & References"],
    "packaging": ["Executive Summary", "Industry Overview", "Material Analysis",
                  "Country Profiles", "Supply Chain Dynamics", "Sustainability Trends", "Data Sources & References"],
    "startups": ["Executive Summary", "Ecosystem Overview", "Sector & Stage Analysis",
                 "Country Profiles", "Funding Landscape", "Key Players & Trends", "Data Sources & References"],
    "pharma":  ["Executive Summary", "Therapy Area Overview", "Drug & Brand Analysis",
                "Country Profiles", "Market Share & Sales Trends", "Regulatory & Access Landscape",
                "Pipeline Highlights", "Data Sources & References"],
}


def _generate_report_docx(rr: dict) -> bytes:
    """Generate a pre-structured DOCX report template for a research request."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import io, datetime

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin   = Inches(1.2)
        section.right_margin  = Inches(1.2)

    # Styles
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    def add_heading(text, level=1):
        p = doc.add_heading(text, level=level)
        run = p.runs[0] if p.runs else p.add_run(text)
        run.font.name = "Calibri"
        if level == 1:
            run.font.size = Pt(16)
            run.font.color.rgb = RGBColor(0x2e, 0xc4, 0xb6)
        elif level == 2:
            run.font.size = Pt(13)
            run.font.color.rgb = RGBColor(0x20, 0x20, 0x20)
        return p

    def add_meta_line(label, value):
        p = doc.add_paragraph()
        run_label = p.add_run(f"{label}: ")
        run_label.bold = True
        run_label.font.size = Pt(10)
        run_label.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        run_value = p.add_run(str(value or ""))
        run_value.font.size = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        return p

    def add_placeholder(text):
        p = doc.add_paragraph()
        run = p.add_run(f"[{text}]")
        run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
        run.font.italic = True
        run.font.size = Pt(10)
        p.paragraph_format.space_before = Pt(4)
        return p

    vertical      = rr.get("vertical", "")
    title         = rr.get("title", "Research Report")
    indicator     = rr.get("indicator_name", "")
    geos          = rr.get("scope_geographies", [])
    geos_str      = ", ".join(geos) if isinstance(geos, list) else str(geos)
    period        = rr.get("period", "")
    client        = rr.get("client_name", "")
    vlabel        = VERTICAL_LABEL.get(vertical, vertical.title())
    ind_label     = VERTICAL_INDICATOR_LABEL.get(vertical, "Indicator")
    headings      = VERTICAL_SECTION_HEADINGS.get(vertical, VERTICAL_SECTION_HEADINGS["epi"])
    today         = datetime.date.today().strftime("%d %B %Y")

    # ── Cover ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(22)
    run.font.name = "Calibri"

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(f"{vlabel} Intelligence Report")
    run2.font.size = Pt(13)
    run2.font.color.rgb = RGBColor(0x2e, 0xc4, 0xb6)

    doc.add_paragraph()

    add_meta_line("Prepared for",    client or "[Client Name]")
    add_meta_line(ind_label,         indicator)
    add_meta_line("Geography Scope", geos_str or "[Specify geographies]")
    add_meta_line("Period",          period or "[Specify period]")
    add_meta_line("Date",            today)
    add_meta_line("Classification",  "CONFIDENTIAL — FOR CLIENT USE ONLY")

    doc.add_page_break()

    # ── Sections ──
    for heading in headings:
        add_heading(heading, level=1)

        if heading == "Country Profiles":
            if geos:
                for geo in geos:
                    add_heading(geo, level=2)
                    add_placeholder(f"Key indicators for {geo} — populate from model")
                    add_placeholder("Trend narrative")
                    add_placeholder("Source references")
            else:
                add_heading("[Country Name]", level=2)
                add_placeholder("Key indicators — populate from model")
        else:
            add_placeholder(f"Write {heading.lower()} here — refer to model for data points")
            add_placeholder("Supporting charts and tables to be inserted")

        doc.add_paragraph()

    # ── Footer note ──
    doc.add_page_break()
    p = doc.add_paragraph()
    run = p.add_run("TEMPLATE NOTICE")
    run.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
    p2 = doc.add_paragraph(
        "This document is a pre-structured template generated from the research request scope. "
        "All [placeholder] sections must be replaced with researched content before submission. "
        "Data should be sourced from the linked Excel model."
    )
    p2.runs[0].font.size = Pt(9)
    p2.runs[0].font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _generate_model_xlsx(rr: dict) -> bytes:
    """Generate a pre-structured XLSX model template for a research request."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
    from openpyxl.utils import get_column_letter
    import io, datetime

    wb = Workbook()

    vertical  = rr.get("vertical", "")
    title     = rr.get("title", "Research Model")
    indicator = rr.get("indicator_name", "")
    geos      = rr.get("scope_geographies", [])
    geos_list = geos if isinstance(geos, list) else []
    period    = rr.get("period", "")
    vlabel    = VERTICAL_LABEL.get(vertical, vertical.title())
    tl_cols   = VERTICAL_TOPLINE_COLS.get(vertical, VERTICAL_TOPLINE_COLS["epi"])
    today     = datetime.date.today().isoformat()

    DARK  = "1A2030"
    TEAL  = "2EC4B6"
    GOLD  = "C8A96E"
    WHITE = "F0F2F7"
    FOG   = "8A95A8"
    LIGHT = "F5F7FA"
    HEADER_FILL = PatternFill("solid", fgColor=DARK)
    TEAL_FILL   = PatternFill("solid", fgColor=TEAL)
    GOLD_FILL   = PatternFill("solid", fgColor=GOLD)
    LIGHT_FILL  = PatternFill("solid", fgColor=LIGHT)

    def header_font(color="FFFFFF", bold=True, size=10):
        return Font(name="Calibri", bold=bold, color=color, size=size)

    def body_font(color="000000", bold=False, size=10):
        return Font(name="Calibri", bold=bold, color=color, size=size)

    thin = Side(border_style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def set_cell(ws, row, col, value, font=None, fill=None, align=None, num_fmt=None):
        c = ws.cell(row=row, column=col, value=value)
        if font:    c.font = font
        if fill:    c.fill = fill
        if align:   c.alignment = align
        if num_fmt: c.number_format = num_fmt
        c.border = border
        return c

    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left   = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    # ── README sheet ──
    ws_readme = wb.active
    ws_readme.title = "README"
    ws_readme.sheet_properties.tabColor = "2EC4B6"
    ws_readme.column_dimensions["A"].width = 22
    ws_readme.column_dimensions["B"].width = 50

    meta = [
        ("Report Title",    title),
        ("Vertical",        vlabel),
        ("Indicator",       indicator),
        ("Period",          period),
        ("Geographies",     ", ".join(geos_list) if geos_list else ""),
        ("Generated",       today),
        ("Status",          "TEMPLATE — Fill in data from approved sources"),
    ]
    ws_readme.merge_cells("A1:B1")
    c = ws_readme.cell(1, 1, "MODEL README")
    c.font = Font(name="Calibri", bold=True, size=14, color=WHITE)
    c.fill = HEADER_FILL
    c.alignment = center
    ws_readme.row_dimensions[1].height = 30

    for i, (k, v) in enumerate(meta, start=2):
        set_cell(ws_readme, i, 1, k, font=header_font(color="000000"), fill=LIGHT_FILL, align=left)
        set_cell(ws_readme, i, 2, v, font=body_font(), align=left)

    # ── Topline sheet ──
    ws_tl = wb.create_sheet("Topline")
    ws_tl.sheet_properties.tabColor = "C8A96E"
    ws_tl.freeze_panes = "A2"

    ws_tl.merge_cells(f"A1:{get_column_letter(len(tl_cols))}1")
    c = ws_tl.cell(1, 1, f"TOPLINE METRICS — {title.upper()}")
    c.font = Font(name="Calibri", bold=True, size=12, color=WHITE)
    c.fill = HEADER_FILL
    c.alignment = center
    ws_tl.row_dimensions[1].height = 28

    for ci, col_name in enumerate(tl_cols, start=1):
        c = ws_tl.cell(2, ci, col_name.upper().replace("_", " "))
        c.font = Font(name="Calibri", bold=True, size=9, color=WHITE)
        c.fill = TEAL_FILL
        c.alignment = center
        c.border = border
        ws_tl.column_dimensions[get_column_letter(ci)].width = 16

    # Seed rows — one per geography
    for gi, geo in enumerate(geos_list, start=3):
        for ci, col_name in enumerate(tl_cols, start=1):
            default = ""
            if col_name == "geography": default = geo
            elif col_name == "period":  default = period
            elif col_name in ("disease", "crop", "sector", "material", "asset_class"): default = indicator
            elif col_name == "dir":     default = "flat"
            elif col_name == "value":   default = 0
            c = ws_tl.cell(gi, ci, default)
            c.font = body_font(color="333333")
            c.alignment = left
            c.border = border
            if col_name == "value":
                c.number_format = "#,##0.00"

    # ── Country sheets ──
    for geo in geos_list:
        ws_geo = wb.create_sheet(geo[:31])  # sheet name max 31 chars
        ws_geo.sheet_properties.tabColor = "4A7FE8"
        ws_geo.freeze_panes = "A3"

        ws_geo.merge_cells("A1:F1")
        c = ws_geo.cell(1, 1, f"{geo} — {indicator}")
        c.font = Font(name="Calibri", bold=True, size=12, color=WHITE)
        c.fill = HEADER_FILL
        c.alignment = center
        ws_geo.row_dimensions[1].height = 26

        col_headers = ["Metric", "Period", "Value", "Unit", "Source", "Notes"]
        for ci, h in enumerate(col_headers, start=1):
            c = ws_geo.cell(2, ci, h.upper())
            c.font = Font(name="Calibri", bold=True, size=9, color=WHITE)
            c.fill = TEAL_FILL
            c.alignment = center
            c.border = border
            ws_geo.column_dimensions[get_column_letter(ci)].width = 18

        # 10 blank input rows
        for ri in range(3, 13):
            for ci in range(1, 7):
                c = ws_geo.cell(ri, ci, "")
                c.border = border
                c.fill = LIGHT_FILL if ri % 2 == 0 else PatternFill()

    # ── Sources sheet ──
    ws_src = wb.create_sheet("Sources")
    ws_src.sheet_properties.tabColor = "9B72E8"
    ws_src.merge_cells("A1:D1")
    c = ws_src.cell(1, 1, "DATA SOURCES & REFERENCES")
    c.font = Font(name="Calibri", bold=True, size=12, color=WHITE)
    c.fill = HEADER_FILL
    c.alignment = center
    ws_src.row_dimensions[1].height = 26

    src_headers = ["Source Name", "URL / Reference", "Data Type", "Date Accessed"]
    for ci, h in enumerate(src_headers, start=1):
        c = ws_src.cell(2, ci, h.upper())
        c.font = Font(name="Calibri", bold=True, size=9, color=WHITE)
        c.fill = TEAL_FILL
        c.alignment = center
        c.border = border
        ws_src.column_dimensions[get_column_letter(ci)].width = 28

    for ri in range(3, 13):
        for ci in range(1, 5):
            c = ws_src.cell(ri, ci, "")
            c.border = border
            c.fill = LIGHT_FILL if ri % 2 == 0 else PatternFill()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _generate_topline_csv(rr: dict) -> bytes:
    """Generate topline CSV template with correct column headers for the vertical."""
    import csv, io

    vertical = rr.get("vertical", "epi")
    geos     = rr.get("scope_geographies", [])
    geos_list = geos if isinstance(geos, list) else []
    period   = rr.get("period", "")
    indicator = rr.get("indicator_name", "")
    tl_cols  = VERTICAL_TOPLINE_COLS.get(vertical, VERTICAL_TOPLINE_COLS["epi"])

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=tl_cols)
    writer.writeheader()

    # Seed one row per geography
    for geo in geos_list:
        row = {c: "" for c in tl_cols}
        row["geography"] = geo
        row["period"]    = period
        row["dir"]       = "flat"
        row["value"]     = "0"
        # Set vertical-specific indicator field
        for field in ("disease", "crop", "sector", "material", "asset_class", "hs_code"):
            if field in row:
                row[field] = indicator
                break
        writer.writerow(row)

    return buf.getvalue().encode("utf-8")


def _generate_deck_pptx(rr: dict) -> bytes:
    """Generate a client deck PPTX template for a research request."""
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    import io

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)

    vertical  = rr.get("vertical", "")
    title     = rr.get("title", "Research Overview")
    indicator = rr.get("indicator_name", "")
    geos      = rr.get("scope_geographies", [])
    geos_list = geos if isinstance(geos, list) else []
    period    = rr.get("period", "")
    client    = rr.get("client_name", "")
    vlabel    = VERTICAL_LABEL.get(vertical, vertical.title())

    C_DARK  = RGBColor(0x0D, 0x10, 0x17)
    C_TEAL  = RGBColor(0x2E, 0xC4, 0xB6)
    C_GOLD  = RGBColor(0xC8, 0xA9, 0x6E)
    C_WHITE = RGBColor(0xF0, 0xF2, 0xF7)
    C_FOG   = RGBColor(0x8A, 0x95, 0xA8)

    blank_layout = prs.slide_layouts[6]  # completely blank

    def add_rect(slide, l, t, w, h, color):
        from pptx.util import Emu
        shape = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        return shape

    def add_text(slide, text, l, t, w, h, size=24, bold=False, color=None, align=PP_ALIGN.LEFT, italic=False):
        txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
        tf  = txb.text_frame
        tf.word_wrap = True
        p   = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        if color:
            run.font.color.rgb = color
        return txb

    # ── Slide 1: Cover ──
    s1 = prs.slides.add_slide(blank_layout)
    add_rect(s1, 0, 0, 13.33, 7.5, C_DARK)
    add_rect(s1, 0, 0, 0.3,   7.5, C_TEAL)   # accent bar
    add_text(s1, vlabel.upper(), 0.6, 0.6, 10, 0.4, size=9, color=C_TEAL, bold=True)
    add_text(s1, title,          0.6, 1.2, 11, 2.2, size=32, bold=True, color=C_WHITE)
    add_text(s1, indicator,      0.6, 3.5, 10, 0.5, size=14, color=C_GOLD)
    if period:
        add_text(s1, period,     0.6, 4.1, 6,  0.4, size=12, color=C_FOG)
    if client:
        add_text(s1, f"Prepared for {client}", 0.6, 6.5, 10, 0.5, size=11, color=C_FOG)
    add_text(s1, "CONFIDENTIAL", 10, 6.8, 3, 0.4, size=9, color=C_FOG, align=PP_ALIGN.RIGHT)

    # ── Slide 2: Scope ──
    s2 = prs.slides.add_slide(blank_layout)
    add_rect(s2, 0, 0, 13.33, 7.5, C_DARK)
    add_rect(s2, 0, 0, 13.33, 0.08, C_TEAL)
    add_text(s2, "RESEARCH SCOPE", 0.6, 0.3, 12, 0.4, size=9, color=C_TEAL, bold=True)
    add_text(s2, "What we studied and how", 0.6, 0.7, 10, 0.7, size=22, bold=True, color=C_WHITE)
    add_text(s2, f"Indicator:   {indicator}", 0.6, 1.8, 10, 0.4, size=12, color=C_FOG)
    add_text(s2, f"Period:       {period or '[Period]'}", 0.6, 2.3, 10, 0.4, size=12, color=C_FOG)
    geos_display = " · ".join(geos_list) if geos_list else "[Geographies]"
    add_text(s2, f"Geographies: {geos_display}", 0.6, 2.8, 12, 0.5, size=12, color=C_FOG)
    add_text(s2, "Methodology", 0.6, 3.6, 10, 0.4, size=13, bold=True, color=C_WHITE)
    add_text(s2, "[Describe data sources, collection method, and analytical framework here]",
             0.6, 4.1, 11, 1.2, size=11, color=C_FOG, italic=True)

    # ── Slide 3: Key Findings ──
    s3 = prs.slides.add_slide(blank_layout)
    add_rect(s3, 0, 0, 13.33, 7.5, C_DARK)
    add_rect(s3, 0, 0, 13.33, 0.08, C_GOLD)
    add_text(s3, "KEY FINDINGS", 0.6, 0.3, 12, 0.4, size=9, color=C_GOLD, bold=True)
    add_text(s3, "Topline numbers at a glance", 0.6, 0.7, 10, 0.7, size=22, bold=True, color=C_WHITE)

    # 3 KPI boxes
    kpi_labels = ["[Metric 1]", "[Metric 2]", "[Metric 3]"]
    for ki, label in enumerate(kpi_labels):
        x = 0.6 + ki * 4.2
        add_rect(s3, x, 1.7, 3.8, 1.8, RGBColor(0x17, 0x1C, 0x28))
        add_text(s3, "[VALUE]", x + 0.2, 1.9, 3.4, 0.7, size=28, bold=True, color=C_TEAL, align=PP_ALIGN.CENTER)
        add_text(s3, label,     x + 0.2, 2.6, 3.4, 0.5, size=11, color=C_FOG, align=PP_ALIGN.CENTER)

    add_text(s3, "Summary narrative — 3–4 sentences covering the most important findings across all geographies. "
                 "Draw from the topline sheet of the model.",
             0.6, 3.8, 12, 1.4, size=11, color=C_FOG, italic=True)

    # ── Slides 4+: One per geography ──
    for geo in geos_list:
        sg = prs.slides.add_slide(blank_layout)
        add_rect(sg, 0, 0, 13.33, 7.5, C_DARK)
        add_rect(sg, 0, 0, 0.3, 7.5, C_TEAL)
        add_text(sg, vlabel.upper(), 0.6, 0.3, 10, 0.4, size=9, color=C_TEAL, bold=True)
        add_text(sg, geo, 0.6, 0.7, 10, 0.8, size=26, bold=True, color=C_WHITE)
        add_text(sg, f"{indicator} · {period}", 0.6, 1.5, 10, 0.4, size=11, color=C_FOG)

        # 2 KPI boxes
        for ki in range(2):
            x = 0.6 + ki * 5.5
            add_rect(sg, x, 2.1, 5.0, 1.5, RGBColor(0x17, 0x1C, 0x28))
            add_text(sg, "[VALUE]",  x+0.2, 2.2, 4.6, 0.6, size=24, bold=True, color=C_TEAL, align=PP_ALIGN.CENTER)
            add_text(sg, "[Metric]", x+0.2, 2.8, 4.6, 0.4, size=10, color=C_FOG, align=PP_ALIGN.CENTER)

        add_text(sg, "Analysis",          0.6, 3.9, 11.7, 0.4, size=12, bold=True, color=C_WHITE)
        add_text(sg, f"[Write 3–4 sentences on {geo}'s {indicator} trends, citing model data]",
                 0.6, 4.4, 11.7, 1.4, size=11, color=C_FOG, italic=True)

    # ── Final slide: Sources ──
    sf = prs.slides.add_slide(blank_layout)
    add_rect(sf, 0, 0, 13.33, 7.5, C_DARK)
    add_rect(sf, 0, 0, 13.33, 0.08, C_TEAL)
    add_text(sf, "SOURCES & METHODOLOGY", 0.6, 0.3, 12, 0.4, size=9, color=C_TEAL, bold=True)
    add_text(sf, "Data references", 0.6, 0.7, 10, 0.7, size=22, bold=True, color=C_WHITE)
    add_text(sf, "[List primary data sources, databases, official publications and URLs referenced in this report]",
             0.6, 1.8, 11.7, 3.5, size=11, color=C_FOG, italic=True)
    add_text(sf, "CONFIDENTIAL — FOR CLIENT USE ONLY", 0.6, 6.7, 12, 0.4, size=9, color=C_FOG, align=PP_ALIGN.CENTER)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@app.post("/api/research-requests/{rr_id}/generate-templates", tags=["research-requests"])
async def generate_templates(rr_id: str, request: Request):
    """
    Generate all 4 template files for an approved research request and store
    them in Supabase Storage under templates/{rr_id}/.
    Returns signed URLs for each file.
    head or master role required.
    """
    profile = _resolve_profile(request)
    if profile["role"] not in ("head", "master"):
        raise HTTPException(status_code=403, detail="head or master role required")

    supa = _get_supa_service()

    # Fetch research request
    try:
        rr_resp = supa.table("research_requests").select("*").eq("id", rr_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Research request not found")
    rr = rr_resp.data
    if not rr:
        raise HTTPException(status_code=404, detail="Research request not found")

    # Vertical access check
    if profile["role"] != "master" and rr["vertical"] != profile.get("vertical"):
        raise HTTPException(status_code=403, detail="Access denied for this vertical")

    if rr["status"] not in ("approved", "in_progress", "review"):
        raise HTTPException(
            status_code=422,
            detail=f"Templates can only be generated for approved/in-progress requests (current: {rr['status']})"
        )

    # Generate files
    import tempfile, os as _os
    errors = []
    urls   = {}

    files_to_generate = [
        ("report",   f"report_{rr_id[:8]}.docx",   "application/vnd.openxmlformats-officedocument.wordprocessingml.document",   _generate_report_docx),
        ("model",    f"model_{rr_id[:8]}.xlsx",     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",          _generate_model_xlsx),
        ("topline",  f"topline_{rr_id[:8]}.csv",    "text/csv",                                                                   _generate_topline_csv),
        ("deck",     f"deck_{rr_id[:8]}.pptx",      "application/vnd.openxmlformats-officedocument.presentationml.presentation",  _generate_deck_pptx),
    ]

    generated_paths = {}
    for file_key, filename, content_type, generator in files_to_generate:
        try:
            file_bytes = generator(rr)
            storage_path = f"templates/{rr_id}/{filename}"

            # Upload to Supabase Storage (templates bucket)
            supa.storage.from_("templates").upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            generated_paths[file_key] = storage_path
        except Exception as exc:
            errors.append(f"{file_key}: {exc}")

    # Store generated paths on the research request
    if generated_paths:
        update_payload = {
            "template_report_path":  generated_paths.get("report"),
            "template_model_path":   generated_paths.get("model"),
            "template_topline_path": generated_paths.get("topline"),
            "template_deck_path":    generated_paths.get("deck"),
            "updated_at":            datetime.datetime.utcnow().isoformat(),
        }
        # Only update fields that exist in the table (add columns via migration)
        try:
            supa.table("research_requests").update(update_payload).eq("id", rr_id).execute()
        except Exception:
            pass  # column may not exist yet — migration adds them

    # Generate signed URLs (1 week)
    for file_key, storage_path in generated_paths.items():
        try:
            signed = supa.storage.from_("templates").create_signed_url(storage_path, 604800)
            urls[file_key] = signed.get("signedURL") or signed.get("signedUrl") or ""
        except Exception as exc:
            urls[file_key] = ""
            errors.append(f"{file_key} signed URL: {exc}")

    _log_activity(supa,
        table_name="research_requests",
        record_id=rr_id,
        actor=profile,
        action="generate_templates",
        new_value=str(list(generated_paths.keys())),
        note=f"Templates generated for: {rr.get('title','')}",
        vertical=rr["vertical"],
    )

    return {
        "rr_id":   rr_id,
        "urls":    urls,
        "paths":   generated_paths,
        "errors":  errors,
        "count":   len(generated_paths),
    }


@app.get("/api/research-requests/{rr_id}/templates", tags=["research-requests"])
async def get_template_urls(rr_id: str, request: Request):
    """Get signed download URLs for existing templates of a research request."""
    profile = _resolve_profile(request)

    supa = _get_supa_service()
    try:
        rr_resp = supa.table("research_requests").select("*").eq("id", rr_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Research request not found")
    rr = rr_resp.data
    if not rr:
        raise HTTPException(status_code=404, detail="Research request not found")

    if profile["role"] != "master" and rr["vertical"] != profile.get("vertical"):
        raise HTTPException(status_code=403, detail="Access denied for this vertical")

    # Try to list files in this request's template folder
    try:
        files = supa.storage.from_("templates").list(f"templates/{rr_id}")
    except Exception:
        files = []

    urls = {}
    for f in (files or []):
        name = f.get("name", "")
        storage_path = f"templates/{rr_id}/{name}"
        file_key = name.split("_")[0]  # "report", "model", "topline", "deck"
        try:
            signed = supa.storage.from_("templates").create_signed_url(storage_path, 604800)
            urls[file_key] = {
                "url":      signed.get("signedURL") or signed.get("signedUrl") or "",
                "filename": name,
            }
        except Exception:
            pass

    return {"rr_id": rr_id, "templates": urls, "count": len(urls)}


# ── /workflow — Gantt dashboard page ─────────────────────────────────────────
@app.get("/workflow", response_class=HTMLResponse, include_in_schema=False)
async def workflow_page():
    """Master Gantt workflow dashboard — requires master session in sessionStorage."""
    return HTMLResponse(content=_GANTT_HTML)


# ── Intelligence platform pages ───────────────────────────────────────────────
def _inject_supa(html: str) -> str:
    """Inject Supabase credentials into a page at request time."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")   # strip trailing slash — prevents "Invalid path" error
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    return html.replace("'{SUPA_URL}'", f"'{url}'").replace("'{SUPA_KEY}'", f"'{key}'")\
               .replace("window.__SUPA_URL__ = ''", f"window.__SUPA_URL__ = '{url}'")\
               .replace("window.__SUPA_KEY__ = ''", f"window.__SUPA_KEY__ = '{key}'")\
               .replace("{SUPA_URL}", url).replace("{SUPA_KEY}", key)


@app.get("/epi-intelligence", response_class=HTMLResponse, include_in_schema=False)
@app.get("/epi-intelligence/", response_class=HTMLResponse, include_in_schema=False)
async def epi_page():
    """Epidemiology analyst workspace — requires Supabase auth (epi or all vertical)."""
    return HTMLResponse(content=_inject_supa(_EPI_HTML))


@app.get("/agri-intelligence", response_class=HTMLResponse, include_in_schema=False)
@app.get("/agri-intelligence/", response_class=HTMLResponse, include_in_schema=False)
async def agri_page():
    """Agriculture analyst workspace — requires Supabase auth (agri or all vertical)."""
    return HTMLResponse(content=_inject_supa(_AGRI_HTML))


@app.get("/markets-intelligence", response_class=HTMLResponse, include_in_schema=False)
@app.get("/markets-intelligence/", response_class=HTMLResponse, include_in_schema=False)
async def markets_page():
    """Markets analyst workspace — requires Supabase auth (markets or all vertical)."""
    return HTMLResponse(content=_inject_supa(_MARKETS_HTML))


@app.get("/packaging-intelligence", response_class=HTMLResponse, include_in_schema=False)
@app.get("/packaging-intelligence/", response_class=HTMLResponse, include_in_schema=False)
async def packaging_page():
    """Packaging analyst workspace — requires Supabase auth (packaging or all vertical)."""
    return HTMLResponse(content=_inject_supa(_PACKAGING_HTML))


@app.get("/startup-intelligence", response_class=HTMLResponse, include_in_schema=False)
@app.get("/startup-intelligence/", response_class=HTMLResponse, include_in_schema=False)
async def startups_page():
    """Startups analyst workspace — requires Supabase auth (startups or all vertical)."""
    return HTMLResponse(content=_inject_supa(_STARTUPS_HTML))


@app.get("/pharma-intelligence", response_class=HTMLResponse, include_in_schema=False)
@app.get("/pharma-intelligence/", response_class=HTMLResponse, include_in_schema=False)
async def pharma_page():
    """Pharma Intelligence analyst workspace — requires Supabase auth (pharma or all vertical)."""
    return HTMLResponse(content=_inject_supa(_PHARMA_HTML))


@app.get("/preview", response_class=HTMLResponse, include_in_schema=False)
@app.get("/preview/", response_class=HTMLResponse, include_in_schema=False)
async def preview_page():
    """Read-only preview of all 6 intelligence workspaces — no login required."""
    return HTMLResponse(content=_PREVIEW_HTML)


@app.get("/master", response_class=HTMLResponse, include_in_schema=False)
@app.get("/master/", response_class=HTMLResponse, include_in_schema=False)
async def master_dashboard_page():
    """Master command centre — master role only (enforced client-side + API)."""
    return HTMLResponse(content=_inject_supa(_MASTER_HTML))
