#!/usr/bin/env python3
"""Claude Code status line renderer.

Reads the status JSON from stdin (see Claude Code statusLine docs) and prints a
multi-line status bar. Token counts and context usage are derived from the
session transcript; git state is read from the current working directory.
"""
import json
import os
import subprocess
import sys

# ---- ANSI helpers -----------------------------------------------------------
def c(code, s):
    if os.environ.get("NO_COLOR"):
        return s
    return f"\033[{code}m{s}\033[0m"

DIM = "2"
BOLD = "1"
CYAN = "36"
GREEN = "32"
YELLOW = "33"
MAGENTA = "35"
BLUE = "34"
SEP = c(DIM, " | ")

# ---- input ------------------------------------------------------------------
try:
    data = json.load(sys.stdin)
except Exception:
    data = {}

model = (data.get("model") or {})
display_name = model.get("display_name") or model.get("id") or "Claude"
model_id = model.get("id") or ""
workspace = (data.get("workspace") or {})
cwd = workspace.get("current_dir") or data.get("cwd") or os.getcwd()
project = os.path.basename(workspace.get("project_dir") or cwd) or "-"
cost = (data.get("cost") or {}).get("total_cost_usd", 0.0) or 0.0
transcript_path = data.get("transcript_path")
exceeds_200k = bool(data.get("exceeds_200k_tokens"))

# Configurable, non-derivable bits (override via env if desired).
label = os.environ.get("CLAUDE_STATUSLINE_LABEL", "claude")
effort = os.environ.get("CLAUDE_STATUSLINE_EFFORT", "high")

# Context window: 1M for models advertising it, otherwise 200k.
one_million = "1m" in model_id.lower() or exceeds_200k
ctx_limit = 1_000_000 if one_million else 200_000
ctx_label = "1M context" if one_million else "200k context"

# ---- transcript token accounting -------------------------------------------
last_input = last_output = last_cache_read = last_cache_creation = 0
ses_input = ses_output = 0
if transcript_path and os.path.exists(transcript_path):
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                msg = obj.get("message") or {}
                usage = msg.get("usage") or {}
                if not usage:
                    continue
                inp = usage.get("input_tokens", 0) or 0
                out = usage.get("output_tokens", 0) or 0
                cr = usage.get("cache_read_input_tokens", 0) or 0
                cc = usage.get("cache_creation_input_tokens", 0) or 0
                ses_input += inp + cr + cc
                ses_output += out
                # keep the most recent usage as the live context snapshot
                last_input, last_output, last_cache_read, last_cache_creation = inp, out, cr, cc
    except Exception:
        pass

ctx_used = last_input + last_cache_read + last_cache_creation
total_in = last_input + last_cache_read + last_cache_creation

def human(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)

# ---- git --------------------------------------------------------------------
def git_status():
    try:
        branch = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        if not branch:
            return None
        porcelain = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        if not porcelain:
            return f"{branch} · no changes"
        changes = len([l for l in porcelain.splitlines() if l.strip()])
        return f"{branch} · {changes} change{'s' if changes != 1 else ''}"
    except Exception:
        return None

git_info = git_status()

# ---- render -----------------------------------------------------------------
# Line 1: identity
pct = (ctx_used / ctx_limit * 100) if ctx_limit else 0
line1 = (
    c(MAGENTA, f"[{label}]") + SEP +
    c(BOLD, project) + SEP +
    c(CYAN, f"{display_name} ({ctx_label})") + SEP +
    c(DIM, "Effort:") + c(YELLOW, effort) + SEP +
    c(GREEN, f"${cost:.3f}")
)

# Line 2: context meter
BAR_W = 20
filled = min(BAR_W, int(round(pct / 100 * BAR_W)))
bar = "█" * filled + "░" * (BAR_W - filled)
pct_str = f"{pct:.0f}%" if ctx_used else "--"
cache_pct = (last_cache_read / total_in * 100) if total_in else None
cache_str = f"{cache_pct:.0f}%" if cache_pct is not None else "--"
line2 = (
    c(DIM, "ctx ") + c(BLUE, bar) + f" {pct_str}  " +
    c(DIM, f"in:{human(total_in)} out:{human(last_output)}  cache:{cache_str}")
)

# Line 3: git
line3 = c(DIM, "git ") + (c(GREEN, git_info) if git_info else c(DIM, "not a repo"))

# Line 4: session totals
line4 = c(DIM, f"ses in:{human(ses_input)} out:{human(ses_output)}")

print(line1)
print(line2)
print(line3)
print(line4)
