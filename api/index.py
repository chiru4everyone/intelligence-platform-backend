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

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from functools import wraps
from typing import Optional

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
      <p class="hero-desc">Your research environment spanning Epidemiology, Agriculture, Trade, Packaging, Markets, and Startup Ecosystems — India-first, globally benchmarked.</p>
    </div>
    <div class="domain-row">
      <div class="domain-chip"><span class="dot" style="background:#2ec4b6"></span>Epidemiology</div>
      <div class="domain-chip"><span class="dot" style="background:#4caf78"></span>Agriculture</div>
      <div class="domain-chip"><span class="dot" style="background:#4a7fe8"></span>Trade</div>
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
                trade:     '/trade-intelligence/',
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
    supa_url = os.environ.get("SUPABASE_URL", "")
    supa_key = os.environ.get("SUPABASE_ANON_KEY", "")
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
    "trade":     "/trade-intelligence/",
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
            .select("role, vertical, full_name, email, is_active")
            .eq("id", uid)
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Profile fetch failed: {exc}")
    if not profile_resp.data:
        raise HTTPException(status_code=403, detail="No profile found for this user")
    p = profile_resp.data
    if not p.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated — contact your Head of Research")
    return p


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
