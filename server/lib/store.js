"use strict";
/* シンプルで壊れにくいJSONファイル保存（外部DB不要）。
   書き込みは一時ファイル＋renameのアトミック書き込み。少人数チーム前提。 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "..", "data");
const DB_FILE = path.join(DATA_DIR, "db.json");

const db = { users: [], hearings: [], sessions: [], audit: [] };
let writeChain = Promise.resolve();

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true, mode: 0o700 });
}

function load() {
  ensureDir();
  if (fs.existsSync(DB_FILE)) {
    try {
      const parsed = JSON.parse(fs.readFileSync(DB_FILE, "utf8"));
      Object.assign(db, parsed);
    } catch (e) {
      console.error("db.json の読み込みに失敗しました。空のデータで起動します。", e.message);
    }
  }
  for (const k of ["users", "hearings", "sessions", "audit"]) if (!Array.isArray(db[k])) db[k] = [];
}

/* アトミックに永続化（直列化して競合を防ぐ） */
function persist() {
  writeChain = writeChain.then(() => {
    ensureDir();
    const tmp = DB_FILE + "." + crypto.randomBytes(4).toString("hex") + ".tmp";
    return fs.promises
      .writeFile(tmp, JSON.stringify(db), { mode: 0o600 })
      .then(() => fs.promises.rename(tmp, DB_FILE));
  }).catch((e) => console.error("保存に失敗しました:", e.message));
  return writeChain;
}

module.exports = { db, load, persist, DATA_DIR, DB_FILE };
