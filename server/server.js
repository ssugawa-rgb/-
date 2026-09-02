"use strict";
/* ============================================================
   FDE初回ヒアリングシート — 社内ローカルサーバー
   ・サーバー側ログイン認証（bcryptでパスワードをハッシュ化）
   ・セッション（httpOnly / SameSite=Strict クッキー、有効期限＋無操作タイムアウト）
   ・ログイン試行のロック（連続失敗で一時ロック）
   ・CSRF対策（独自ヘッダのトークン照合）
   ・セキュリティヘッダ（CSP 等）
   ・ヒアリングはサーバーに一元保存し全スタッフで共有
   起動:  npm install && npm start
   ============================================================ */
const express = require("express");
const bcrypt = require("bcryptjs");
const crypto = require("crypto");
const path = require("path");
const fs = require("fs");
const store = require("./lib/store");

/* .env（あれば）を読み込む簡易ローダー（依存パッケージ不要） */
(function loadEnv() {
  try {
    const p = path.join(__dirname, ".env");
    if (!fs.existsSync(p)) return;
    for (const line of fs.readFileSync(p, "utf8").split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
      if (!m || line.trim().startsWith("#")) continue;
      let v = m[2].trim();
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
      if (process.env[m[1]] === undefined) process.env[m[1]] = v;
    }
  } catch (e) { /* noop */ }
})();

const PORT = parseInt(process.env.PORT || "8787", 10);
const HOST = process.env.HOST || "127.0.0.1";           // 既定は自PCのみ。LAN公開は 0.0.0.0
const TRUST_PROXY = process.env.TRUST_PROXY === "1";     // 逆プロキシ(HTTPS)の背後で動かす場合
const COOKIE_SECURE = process.env.COOKIE_SECURE === "1" || TRUST_PROXY; // HTTPS時のみ送信
const SESSION_HOURS = parseInt(process.env.SESSION_HOURS || "12", 10);
const IDLE_MINUTES = parseInt(process.env.IDLE_MINUTES || "60", 10);
const MAX_FAILS = parseInt(process.env.MAX_FAILS || "5", 10);
const LOCK_MINUTES = parseInt(process.env.LOCK_MINUTES || "15", 10);
const APP_HTML_PATH = process.env.APP_HTML || path.join(__dirname, "..", "fde_hearing_form.html");

store.load();
bootstrapAdmin();

const app = express();
if (TRUST_PROXY) app.set("trust proxy", 1);
app.disable("x-powered-by");
app.use(express.json({ limit: "4mb" }));
// 不正なJSONは400で返す
app.use((err, req, res, next) => {
  if (err && err.type === "entity.parse.failed") return res.status(400).json({ error: "リクエストが不正です" });
  next(err);
});

/* ---------- セキュリティヘッダ ---------- */
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("Permissions-Policy", "geolocation=(), microphone=(), camera=()");
  res.setHeader(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
      "img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; " +
      "form-action 'self'; frame-ancestors 'none'"
  );
  if (COOKIE_SECURE) res.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  next();
});

/* ============================================================
   セッション / 認証ヘルパ
   ============================================================ */
function newToken() { return crypto.randomBytes(32).toString("base64url"); }
function parseCookies(req) {
  const out = {}; const h = req.headers.cookie || "";
  h.split(";").forEach((p) => { const i = p.indexOf("="); if (i > 0) out[p.slice(0, i).trim()] = decodeURIComponent(p.slice(i + 1).trim()); });
  return out;
}
function setSessionCookie(res, token) {
  const parts = ["sid=" + token, "HttpOnly", "Path=/", "SameSite=Strict", "Max-Age=" + SESSION_HOURS * 3600];
  if (COOKIE_SECURE) parts.push("Secure");
  res.setHeader("Set-Cookie", parts.join("; "));
}
function clearSessionCookie(res) {
  res.setHeader("Set-Cookie", "sid=; HttpOnly; Path=/; SameSite=Strict; Max-Age=0" + (COOKIE_SECURE ? "; Secure" : ""));
}
function createSession(userId) {
  const now = Date.now();
  const s = { token: newToken(), csrf: newToken(), userId, createdAt: now, lastSeen: now, expiresAt: now + SESSION_HOURS * 3600 * 1000 };
  store.db.sessions.push(s); store.persist();
  return s;
}
function destroySession(token) {
  store.db.sessions = store.db.sessions.filter((x) => x.token !== token); store.persist();
}
function getSession(req) {
  const token = parseCookies(req).sid; if (!token) return null;
  const s = store.db.sessions.find((x) => x.token === token); if (!s) return null;
  const now = Date.now();
  if (now > s.expiresAt || (IDLE_MINUTES > 0 && now - s.lastSeen > IDLE_MINUTES * 60 * 1000)) { destroySession(token); return null; }
  s.lastSeen = now; // 無操作タイムアウトの起点を更新（保存は緩やかに）
  return s;
}
function requireAuth(req, res, next) {
  const s = getSession(req);
  if (!s) return res.status(401).json({ error: "ログインが必要です" });
  const u = store.db.users.find((x) => x.id === s.userId);
  if (!u) { destroySession(s.token); return res.status(401).json({ error: "ログインが必要です" }); }
  req.session = s; req.user = u; next();
}
function requireCsrf(req, res, next) {
  if (["GET", "HEAD", "OPTIONS"].includes(req.method)) return next();
  const h = req.get("X-CSRF-Token") || "";
  const good = req.session && h && h.length === req.session.csrf.length &&
    crypto.timingSafeEqual(Buffer.from(h), Buffer.from(req.session.csrf));
  if (!good) return res.status(403).json({ error: "CSRF検証に失敗しました。再読み込みしてください。" });
  next();
}
function requireAdmin(req, res, next) {
  if (!req.user || req.user.role !== "admin") return res.status(403).json({ error: "管理者権限が必要です" });
  next();
}

/* ---------- ログイン試行のロック ---------- */
const attempts = new Map();
function keyFor(req, username) { return (req.ip || "") + "|" + String(username || "").toLowerCase(); }
function lockedFor(key) { const a = attempts.get(key); return a && a.until && Date.now() < a.until ? Math.ceil((a.until - Date.now()) / 1000) : 0; }
function noteFail(key) { const a = attempts.get(key) || { count: 0, until: 0 }; a.count++; if (a.count >= MAX_FAILS) { a.until = Date.now() + LOCK_MINUTES * 60000; a.count = 0; } attempts.set(key, a); }
function clearFails(key) { attempts.delete(key); }

/* ---------- 共通ヘルパ ---------- */
function pubUser(u) { return { id: u.id, username: u.username, role: u.role, mustChangePassword: !!u.mustChangePassword, createdAt: u.createdAt }; }
function passwordPolicy(p) {
  p = String(p || "");
  if (p.length < 8) return "パスワードは8文字以上にしてください";
  if (!/[A-Za-z]/.test(p) || !/[0-9]/.test(p)) return "パスワードには英字と数字を含めてください";
  return "";
}
function audit(req, username, action) {
  store.db.audit.push({ t: new Date().toISOString(), ip: req.ip || "", username: username || "", action });
  if (store.db.audit.length > 5000) store.db.audit = store.db.audit.slice(-3000);
  store.persist();
}

/* ============================================================
   ページ
   ============================================================ */
let APP_RAW = "";
try { APP_RAW = fs.readFileSync(APP_HTML_PATH, "utf8"); }
catch (e) { console.error("アプリのHTMLが見つかりません:", APP_HTML_PATH); }
function appHtml() {
  // クライアントをサーバーAPIモードに切り替えるフラグを注入
  return APP_RAW.replace("<body>", "<body>\n<script>window.__FDE_API__=true;</script>");
}

app.get("/", (req, res) => {
  if (!getSession(req)) return res.redirect("/login");
  res.type("html").send(appHtml());
});
app.get("/login", (req, res) => {
  if (getSession(req)) return res.redirect("/");
  res.type("html").send(LOGIN_HTML);
});

/* ============================================================
   API: 認証
   ============================================================ */
app.post("/api/login", (req, res) => {
  const { username, password } = req.body || {};
  const key = keyFor(req, username);
  const lock = lockedFor(key);
  if (lock) return res.status(429).json({ error: "試行回数が上限に達しました。約" + Math.ceil(lock / 60) + "分後に再試行してください。" });
  const u = store.db.users.find((x) => x.username.toLowerCase() === String(username || "").toLowerCase());
  const ok = u && bcrypt.compareSync(String(password || ""), u.passHash);
  if (!ok) { noteFail(key); audit(req, username, "login_fail"); return res.status(401).json({ error: "ユーザー名またはパスワードが違います" }); }
  clearFails(key);
  const s = createSession(u.id);
  setSessionCookie(res, s.token);
  audit(req, u.username, "login_ok");
  res.json({ user: pubUser(u), csrf: s.csrf, mustChangePassword: !!u.mustChangePassword });
});
app.post("/api/logout", requireAuth, requireCsrf, (req, res) => {
  audit(req, req.user.username, "logout");
  destroySession(req.session.token); clearSessionCookie(res); res.json({ ok: true });
});
app.get("/api/me", requireAuth, (req, res) => {
  res.json({ user: pubUser(req.user), csrf: req.session.csrf, mustChangePassword: !!req.user.mustChangePassword });
});
app.post("/api/account/password", requireAuth, requireCsrf, (req, res) => {
  const { current, next } = req.body || {};
  if (!bcrypt.compareSync(String(current || ""), req.user.passHash)) return res.status(400).json({ error: "現在のパスワードが違います" });
  const err = passwordPolicy(next); if (err) return res.status(400).json({ error: err });
  req.user.passHash = bcrypt.hashSync(String(next), 12);
  req.user.mustChangePassword = false;
  // パスワード変更時は本人の他セッションを無効化（このセッションは残す）
  store.db.sessions = store.db.sessions.filter((x) => x.userId !== req.user.id || x.token === req.session.token);
  store.persist(); audit(req, req.user.username, "password_change");
  res.json({ ok: true });
});

/* ============================================================
   API: ヒアリング（全ログインユーザーで共有）
   ============================================================ */
app.get("/api/hearings", requireAuth, (req, res) => {
  res.json(store.db.hearings.map((h) => ({ id: h.id, company: h.company, dept: h.dept, date: h.date, pct: h.pct, updatedAt: h.updatedAt, updatedBy: h.updatedBy })));
});
app.get("/api/hearings/:id", requireAuth, (req, res) => {
  const h = store.db.hearings.find((x) => x.id === req.params.id);
  if (!h) return res.status(404).json({ error: "見つかりません" });
  res.json({ id: h.id, meta: { company: h.company, dept: h.dept, date: h.date, pct: h.pct }, data: h.data, updatedAt: h.updatedAt, updatedBy: h.updatedBy });
});
function applyMeta(h, meta) {
  meta = meta || {};
  h.company = String(meta.company || "").slice(0, 200);
  h.dept = String(meta.dept || "").slice(0, 200);
  h.date = String(meta.date || "").slice(0, 40);
  h.pct = String(meta.pct || "0%").slice(0, 8);
}
app.post("/api/hearings", requireAuth, requireCsrf, (req, res) => {
  const { meta, data } = req.body || {};
  const now = new Date().toISOString();
  const h = { id: crypto.randomBytes(9).toString("base64url"), data: data || {}, createdAt: now, updatedAt: now, createdBy: req.user.username, updatedBy: req.user.username };
  applyMeta(h, meta);
  store.db.hearings.push(h); store.persist();
  res.json({ id: h.id });
});
app.put("/api/hearings/:id", requireAuth, requireCsrf, (req, res) => {
  const h = store.db.hearings.find((x) => x.id === req.params.id);
  if (!h) return res.status(404).json({ error: "見つかりません" });
  const { meta, data } = req.body || {};
  applyMeta(h, meta);
  if (data !== undefined) h.data = data;
  h.updatedAt = new Date().toISOString(); h.updatedBy = req.user.username;
  store.persist(); res.json({ ok: true });
});
app.delete("/api/hearings/:id", requireAuth, requireCsrf, (req, res) => {
  const before = store.db.hearings.length;
  store.db.hearings = store.db.hearings.filter((x) => x.id !== req.params.id);
  if (store.db.hearings.length === before) return res.status(404).json({ error: "見つかりません" });
  store.persist(); audit(req, req.user.username, "hearing_delete:" + req.params.id);
  res.json({ ok: true });
});

/* ============================================================
   API: スタッフ管理（管理者のみ）
   ============================================================ */
app.get("/api/users", requireAuth, requireAdmin, (req, res) => {
  res.json(store.db.users.map(pubUser));
});
app.post("/api/users", requireAuth, requireAdmin, requireCsrf, (req, res) => {
  const { username, password, role } = req.body || {};
  const un = String(username || "").trim();
  if (!/^[A-Za-z0-9._@-]{3,40}$/.test(un)) return res.status(400).json({ error: "ユーザー名は3〜40文字（英数字 . _ @ -）で指定してください" });
  if (store.db.users.some((x) => x.username.toLowerCase() === un.toLowerCase())) return res.status(400).json({ error: "同名のユーザーが既に存在します" });
  const err = passwordPolicy(password); if (err) return res.status(400).json({ error: err });
  const u = { id: crypto.randomBytes(6).toString("base64url"), username: un, passHash: bcrypt.hashSync(String(password), 12), role: role === "admin" ? "admin" : "staff", createdAt: new Date().toISOString(), mustChangePassword: true };
  store.db.users.push(u); store.persist(); audit(req, req.user.username, "user_add:" + un);
  res.json({ user: pubUser(u) });
});
app.post("/api/users/:id/reset", requireAuth, requireAdmin, requireCsrf, (req, res) => {
  const u = store.db.users.find((x) => x.id === req.params.id);
  if (!u) return res.status(404).json({ error: "見つかりません" });
  const err = passwordPolicy(req.body && req.body.password); if (err) return res.status(400).json({ error: err });
  u.passHash = bcrypt.hashSync(String(req.body.password), 12); u.mustChangePassword = true;
  store.db.sessions = store.db.sessions.filter((x) => x.userId !== u.id); // 既存セッション失効
  store.persist(); audit(req, req.user.username, "user_reset:" + u.username);
  res.json({ ok: true });
});
app.delete("/api/users/:id", requireAuth, requireAdmin, requireCsrf, (req, res) => {
  const u = store.db.users.find((x) => x.id === req.params.id);
  if (!u) return res.status(404).json({ error: "見つかりません" });
  if (u.role === "admin" && store.db.users.filter((x) => x.role === "admin").length <= 1) return res.status(400).json({ error: "最後の管理者は削除できません" });
  store.db.users = store.db.users.filter((x) => x.id !== req.params.id);
  store.db.sessions = store.db.sessions.filter((x) => x.userId !== req.params.id);
  store.persist(); audit(req, req.user.username, "user_delete:" + u.username);
  res.json({ ok: true });
});

/* 未知の /api は JSON で 404 */
app.use("/api", (req, res) => res.status(404).json({ error: "not found" }));

/* 期限切れセッションの定期掃除 */
setInterval(() => {
  const now = Date.now();
  const before = store.db.sessions.length;
  store.db.sessions = store.db.sessions.filter((s) => now <= s.expiresAt && (IDLE_MINUTES <= 0 || now - s.lastSeen <= IDLE_MINUTES * 60000));
  if (store.db.sessions.length !== before) store.persist();
}, 10 * 60 * 1000).unref();

app.listen(PORT, HOST, () => {
  console.log("\nFDE初回ヒアリングシート（社内サーバー）が起動しました");
  console.log("  URL:  http://" + HOST + ":" + PORT + "/");
  if (!COOKIE_SECURE) console.log("  ※ 本番は HTTPS（リバースプロキシ）越しで運用し、COOKIE_SECURE=1 を設定してください。");
  console.log("");
});

/* ============================================================
   初期管理者の自動作成
   ============================================================ */
function bootstrapAdmin() {
  if (store.db.users.length > 0) return;
  const username = process.env.ADMIN_USER || "admin";
  const pw = process.env.ADMIN_PASSWORD || crypto.randomBytes(9).toString("base64url");
  store.db.users.push({ id: crypto.randomBytes(6).toString("base64url"), username, passHash: bcrypt.hashSync(pw, 12), role: "admin", createdAt: new Date().toISOString(), mustChangePassword: true });
  store.persist();
  console.log("\n=========== 初期管理者アカウントを作成しました ===========");
  console.log("  ユーザー名: " + username);
  console.log("  パスワード: " + pw);
  console.log("  ※ 初回ログイン後、必ずパスワードを変更してください。");
  console.log("  （環境変数 ADMIN_USER / ADMIN_PASSWORD で指定も可能）");
  console.log("==========================================================\n");
}

/* ============================================================
   ログインページ（自己完結HTML）
   ============================================================ */
const LOGIN_HTML = `<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ログイン — FDEヒアリングシート</title>
<style>
:root{--navy:#16294D;--navy-2:#24406F;--bg:#F3F4F6;--line:#E3E6EB;--ink:#1F2937;--muted:#6B7280}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:var(--bg);font-family:"Meiryo","Hiragino Kaku Gothic ProN","Yu Gothic UI",system-ui,sans-serif;color:var(--ink)}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 8px 30px rgba(22,41,77,.12);width:100%;max-width:380px;overflow:hidden}
.hd{background:var(--navy);color:#fff;padding:20px 24px}
.hd h1{margin:0;font-size:16px;letter-spacing:.05em}.hd p{margin:4px 0 0;font-size:11px;color:#A9B7CE;letter-spacing:.12em;font-family:Consolas,monospace}
.bd{padding:22px 24px}
label{display:block;font-size:12px;color:var(--muted);margin:0 0 5px}
input{width:100%;padding:10px 11px;border:1px solid var(--line);border-radius:6px;background:#FCFCFD;font-size:14px;margin-bottom:14px;color:inherit}
input:focus{outline:none;border-color:var(--navy-2);box-shadow:0 0 0 2px rgba(36,64,111,.12);background:#fff}
button{width:100%;padding:11px;border:none;border-radius:6px;background:var(--navy);color:#fff;font-weight:700;font-size:14px;cursor:pointer}
button:hover{background:var(--navy-2)}button:disabled{opacity:.6;cursor:default}
.err{color:#B4453A;font-size:12.5px;min-height:18px;margin:0 0 10px}
.foot{font-size:11px;color:var(--muted);text-align:center;padding:0 24px 18px}
</style></head><body>
<form class="card" id="f" autocomplete="on">
  <div class="hd"><h1>FDE初回ヒアリングシート</h1><p>SIGN IN</p></div>
  <div class="bd">
    <p class="err" id="err"></p>
    <label for="u">ユーザー名</label>
    <input id="u" name="username" autocomplete="username" autofocus required>
    <label for="p">パスワード</label>
    <input id="p" name="password" type="password" autocomplete="current-password" required>
    <button id="b" type="submit">ログイン</button>
  </div>
  <div class="foot">社内利用専用 / このページはブックマーク可能です</div>
</form>
<script>
const f=document.getElementById("f"),err=document.getElementById("err"),b=document.getElementById("b");
f.addEventListener("submit",async(e)=>{
  e.preventDefault(); err.textContent=""; b.disabled=true;
  try{
    const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",
      body:JSON.stringify({username:document.getElementById("u").value,password:document.getElementById("p").value})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok){ err.textContent=j.error||("エラー ("+r.status+")"); b.disabled=false; return; }
    location.href="/";
  }catch(_){ err.textContent="通信に失敗しました"; b.disabled=false; }
});
</script>
</body></html>`;
