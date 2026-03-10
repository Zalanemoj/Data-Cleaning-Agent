import streamlit as st
import pandas as pd
import requests
import json
import io
import re

# --- HARDCODED CONFIGURATION ---
N8N_URL = "https://mesencephalic-nonunderstandingly-dara.ngrok-free.dev/webhook-test/e5bd678a-6d41-482d-b46a-5e71042bfde7"
COLAB_URL = "https://awesomely-focusable-karla.ngrok-free.dev/clean"

st.set_page_config(page_title="DataPure AI", page_icon="💎", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* Main background */
    .stApp { background-color: #0d0f12; }

    /* Title */
    h1 { font-family: 'IBM Plex Mono', monospace !important; color: #e2e8f0 !important; }

    /* Step headers */
    h4 { color: #94a3b8 !important; font-family: 'IBM Plex Mono', monospace !important; letter-spacing: 0.05em; }

    /* Buttons */
    .stButton>button {
        width: 100%; height: 3em;
        font-weight: 600;
        border-radius: 6px;
        background: #1e293b;
        color: #e2e8f0;
        border: 1px solid #334155;
        transition: all 0.2s ease;
    }
    .stButton>button:hover { background: #334155; border-color: #38bdf8; color: #38bdf8; }

    .stDownloadButton>button {
        width: 100%; height: 3em;
        background: #166534;
        color: #bbf7d0;
        border: 1px solid #166534;
        border-radius: 6px;
        font-weight: 600;
    }

    /* Column card container */
    .col-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-left: 3px solid #38bdf8;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .col-card.severity-high  { border-left-color: #ef4444; }
    .col-card.severity-medium{ border-left-color: #f59e0b; }
    .col-card.severity-low   { border-left-color: #38bdf8; }
    .col-card.severity-none  { border-left-color: #22c55e; }

    /* Severity badge */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        font-family: 'IBM Plex Mono', monospace;
        margin-left: 8px;
        vertical-align: middle;
    }
    .badge-HIGH   { background:#450a0a; color:#fca5a5; }
    .badge-MEDIUM { background:#451a03; color:#fcd34d; }
    .badge-LOW    { background:#0c1a2e; color:#7dd3fc; }
    .badge-NONE   { background:#052e16; color:#86efac; }

    /* Column name tag */
    .col-tag {
        font-family: 'IBM Plex Mono', monospace;
        background: #1e293b;
        color: #38bdf8;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    /* Anomaly text */
    .anomaly-text {
        color: #94a3b8;
        font-size: 0.82rem;
        margin-top: 4px;
        margin-bottom: 12px;
    }

    /* Affected rows pill */
    .affected-pill {
        font-size: 0.72rem;
        color: #64748b;
        font-family: 'IBM Plex Mono', monospace;
    }

    /* Warning banner */
    .skip-warning {
        background: #1c1400;
        border: 1px solid #78350f;
        border-radius: 5px;
        color: #fbbf24;
        padding: 6px 10px;
        font-size: 0.78rem;
        margin-top: 6px;
    }

    /* Selectbox */
    .stSelectbox > div > div {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 5px !important;
        color: #e2e8f0 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #0a0c10;
        border-right: 1px solid #1f2937;
    }

    /* Progress bar area */
    .step-indicator {
        display: flex;
        gap: 8px;
        margin-bottom: 1.5rem;
    }
    .step-dot {
        height: 4px;
        flex: 1;
        border-radius: 2px;
        background: #1f2937;
    }
    .step-dot.active { background: #38bdf8; }
    .step-dot.done   { background: #22c55e; }
    </style>
""", unsafe_allow_html=True)

# ── Session State Init ──────────────────────────────────────────────────────
for key, val in [("step", 1), ("df", None), ("audit", None), ("final_df", None)]:
    if key not in st.session_state:
        st.session_state[key] = val


# ── Helpers ─────────────────────────────────────────────────────────────────
def sanitize(name):
    return re.sub(r'\s+', '_', re.sub(r'[^\w\s]', '', str(name).strip().lower()))


def strip_md(text):
    if not text:
        return ""
    # Remove all code fence variants
    text = re.sub(r"```[a-zA-Z]*", "", text)
    text = text.replace("```", "")
    # FIX: n8n returns literal \n instead of real newlines — unescape them
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", "\t")
    return text.strip()


def validate_code(code: str) -> tuple[bool, str]:
    """
    Validate generated code with compile() before sending to Colab.
    Returns (is_valid, error_message).
    compile() catches syntax errors including the eval() assignment issue.
    """
    try:
        compile(code, "<string>", "exec")  # must use "exec" mode, not "eval"
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg} — `{e.text}`"
    except Exception as e:
        return False, str(e)


def sanitize_generated_code(code: str) -> str:
    """
    SAFE APPROACH: Never inject lines inline (causes double-assignment corruption).
    Instead:
      1. Scan the full code to find what columns need what conversions.
      2. Remove any existing conversion lines (deduplicate).
      3. Prepend a clean safety block at the top.
      4. Keep the rest of the code untouched.
    """

    # ── STEP 1: Find all columns that use .dt accessor ────────────────────
    dt_cols = set(re.findall(r"df\[['\"]([^'\"]+)['\"]\]\.dt\.", code))

    # ── STEP 2: Find all columns that use numeric aggregations ────────────
    num_cols = set(re.findall(
        r"df\[['\"]([^'\"]+)['\"]\]\.(mean|median|std|sum|var|quantile)\(", code))
    num_cols = {c[0] for c in num_cols}

    # ── STEP 3: Find all columns that use .str accessor ───────────────────
    str_cols = set(re.findall(r"df\[['\"]([^'\"]+)['\"]\]\.str\.", code))

    # ── STEP 4: Strip ALL conversion lines — match by content, not pattern ──
    # The AI sometimes generates corrupted lines like:
    #   df['x'] = df['x'] = pd.to_datetime(df['x'] = df['x'], errors='coerce')
    # These don't match a clean regex, so we strip ANY line that contains
    # these conversion function calls and rebuild them cleanly in the header.
    lines = code.split("\n")
    clean_lines = []
    for line in lines:
        s = line.strip()
        should_strip = (
            "pd.to_datetime("   in s or
            "pd.to_numeric("    in s or
            ".astype(str)"      in s or
            s.startswith("import pandas") or
            s.startswith("import numpy")
        )
        if should_strip:
            continue  # will be rebuilt cleanly in header
        # Patch .astype(int) → safe nullable Int64
        if re.search(r"\.astype\(int\)", line):
            line = re.sub(
                r"\.astype\(int\)",
                ".pipe(lambda s: pd.to_numeric(s, errors='coerce').astype('Int64'))",
                line
            )
        clean_lines.append(line)

    # ── STEP 5: Build safety header block ────────────────────────────────
    header_lines = [
        "import pandas as pd",
        "import numpy as np",
        "",
        "# === AUTO SAFETY CONVERSIONS ===",
    ]

    for col in sorted(dt_cols):
        header_lines.append(
            f"df['{col}'] = pd.to_datetime(df['{col}'], errors='coerce')"
        )

    for col in sorted(num_cols):
        # Don't re-add numeric conversion for cols already handled as datetime
        if col not in dt_cols:
            header_lines.append(
                f"df['{col}'] = pd.to_numeric(df['{col}'], errors='coerce')"
            )

    for col in sorted(str_cols):
        if col not in dt_cols and col not in num_cols:
            header_lines.append(
                f"df['{col}'] = df['{col}'].astype(str).str.strip()"
            )

    header_lines.append("# === END SAFETY CONVERSIONS ===")
    header_lines.append("")

    return "\n".join(header_lines) + "\n".join(clean_lines)


def get_default_action(issue_type: str, suggestions: list) -> str:
    """
    FIX: For CLEAN/NONE columns → default to 'Keep Original (Skip)'.
    For dirty columns → default to suggestions[0] (the corrective action).
    """
    clean_types = {"CLEAN", "NONE", None, ""}
    if str(issue_type).upper() in clean_types:
        # Find "Keep Original (Skip)" in suggestions
        for s in suggestions:
            if "keep original" in s.lower():
                return s
    # Dirty column: first suggestion is always corrective
    return suggestions[0] if suggestions else "Keep Original (Skip)"


def dedupe_suggestions(suggestions: list) -> list:
    """
    - Remove duplicate 'Keep Original (Skip)' entries — exactly ONE allowed.
    - Always ensure 'Custom' is present exactly once, as the last item.
    Order: [corrective actions...] + ["Keep Original (Skip)"] + ["Custom"]
    """
    keep_skip = "Keep Original (Skip)"
    # Strip both keep_skip and Custom from list to rebuild cleanly
    cleaned = [s for s in suggestions
               if s.lower() != keep_skip.lower() and s.lower() != "custom"]
    return cleaned + [keep_skip, "Custom"]


def severity_class(severity: str) -> str:
    return {
        "HIGH": "severity-high",
        "MEDIUM": "severity-medium",
        "LOW": "severity-low",
        "NONE": "severity-none",
    }.get(str(severity).upper(), "severity-low")


def render_step_indicator(current: int):
    steps = ["Upload & Audit", "Define Rules", "Export"]
    html = '<div class="step-indicator">'
    for i in range(1, 4):
        cls = "done" if i < current else ("active" if i == current else "")
        html += f'<div class="step-dot {cls}" title="Step {i}: {steps[i-1]}"></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ── APP HEADER ───────────────────────────────────────────────────────────────
st.title("💎 DataPure AI")
render_step_indicator(st.session_state.step)
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — Upload & Audit
# ════════════════════════════════════════════════════════════════════════════
if st.session_state.step == 1:
    st.markdown("#### 1. Upload Dataset")
    file = st.file_uploader("Drop your CSV or Excel file here", type=["csv", "xlsx"])

    if file:
        if st.session_state.df is None:
            df_raw = (pd.read_csv(file)
                      if file.name.endswith('.csv')
                      else pd.read_excel(file))
            st.session_state.df = df_raw.rename(columns=sanitize)
            st.success(f"✅ Loaded **{len(st.session_state.df):,} rows × "
                       f"{len(st.session_state.df.columns)} columns** — headers standardized.")

        st.dataframe(st.session_state.df.head(10), use_container_width=True)

        if st.button("🚀 Inspect with AI"):
            with st.spinner("Analyzing data anomalies..."):
                try:
                    payload = {
                        "csv_data": st.session_state.df.head(100).to_csv(index=False),
                        "columns": list(st.session_state.df.columns),
                        "action": "analyze"
                    }
                    res = requests.post(N8N_URL, json=payload).json()
                    raw = (res[0].get("output", "")
                           if isinstance(res, list)
                           else res.get("output", ""))
                    st.session_state.audit = json.loads(strip_md(raw))
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"Audit Error: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — Define Cleaning Rules
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 2:
    st.markdown("#### 2. Define Cleaning Rules")

    audit = st.session_state.audit
    fixes = {}

    # ── Per-column cards ────────────────────────────────────────────────────
    for col, data in audit.items():
        issue_type   = str(data.get("issue_type", "")).upper()
        issue_text   = data.get("issue", "No description provided.")
        severity     = str(data.get("severity", "LOW")).upper()
        affected_pct = data.get("affected_rows_pct", "—")

        # FIX 1: Deduplicate suggestions from AI response
        raw_suggestions = data.get("suggestions", ["Keep Original (Skip)", "Custom"])
        suggestions = dedupe_suggestions(raw_suggestions)

        # FIX 2: Smart default — corrective action for dirty, Keep Original for clean
        default_val = get_default_action(issue_type, suggestions)
        default_idx = suggestions.index(default_val) if default_val in suggestions else 0

        # ── Render card ──
        sev_cls = severity_class(severity)
        st.markdown(
            f"""<div class="col-card {sev_cls}">
                <span class="col-tag">{col}</span>
                <span class="badge badge-{severity}">{severity}</span>
                <span class="affected-pill" style="float:right">⚠ {affected_pct} affected</span>
                <div class="anomaly-text">Anomaly: {issue_text}</div>
            </div>""",
            unsafe_allow_html=True
        )

        # Selectbox with correct default
        choice = st.selectbox(
            "Select action",
            options=suggestions,
            index=default_idx,
            key=f"sel_{col}",
            label_visibility="collapsed"
        )

        # FIX 3: Warn if user overrides to Skip on a dirty column
        if (choice.lower() == "keep original (skip)"
                and issue_type not in {"CLEAN", "NONE", ""}):
            st.markdown(
                '<div class="skip-warning">⚠️ This column has a detected issue — '
                'skipping is not recommended. Consider a corrective action above.</div>',
                unsafe_allow_html=True
            )

        if choice == "Custom":
            fixes[col] = st.text_input(
                "Custom instruction for this column",
                placeholder=f"e.g. Fill {col} nulls with 0",
                key=f"inp_{col}"
            )
        else:
            fixes[col] = choice

        st.markdown("<div style='margin-bottom:1rem'></div>", unsafe_allow_html=True)

    # ── Action buttons ──────────────────────────────────────────────────────
    col_back, col_apply = st.columns(2)

    if col_back.button("← Back"):
        st.session_state.step = 1
        st.rerun()

    if col_apply.button("⚡ Apply Fixes on Cloud Engine"):
        with st.status("Executing Tasks...", expanded=True) as status:
            try:
                status.write("📡 Step A: Fetching Python recipe from n8n...")
                payload_n8n = {
                    "instructions": fixes,
                    "columns": list(st.session_state.df.columns),
                    "action": "fix"
                }
                res_n8n = requests.post(N8N_URL, json=payload_n8n).json()
                raw_code = strip_md(
                    res_n8n[0].get("output", "")
                    if isinstance(res_n8n, list)
                    else res_n8n.get("output", "")
                )
                code = sanitize_generated_code(raw_code)
                status.write(f"🔍 Code safety check passed ({len(code.splitlines())} lines)")

                # ── Validate syntax BEFORE sending to Colab ──────────────
                is_valid, compile_err = validate_code(code)
                if not is_valid:
                    st.error(f"❌ Generated code has a syntax error — not sent to Colab.\n\n`{compile_err}`")
                    st.code(code, language="python")
                    st.stop()

                status.write("🚀 Step B: Processing on Google Colab...")
                res_colab = requests.post(
                    COLAB_URL,
                    json={
                        "csv_data": st.session_state.df.to_csv(index=False),
                        "code": code
                    }
                ).json()

                if res_colab.get("status") == "success":
                    st.session_state.final_df = pd.read_csv(
                        io.StringIO(res_colab["csv"])
                    )
                    st.session_state.step = 3
                    status.update(label="✅ Cleaning Complete!", state="complete")
                    st.rerun()
                else:
                    st.error(f"Colab Error: {res_colab.get('message')}")

            except Exception as e:
                st.error(f"Connection Error: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 — Review & Export
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 3:
    st.markdown("#### 3. Review & Export")

    st.dataframe(st.session_state.final_df, use_container_width=True)

    csv_bytes = st.session_state.final_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Cleaned CSV",
        csv_bytes,
        "cleaned_data.csv",
        "text/csv"
    )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Start New Dataset"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💎 DataPure AI")
    st.markdown("---")
    st.markdown("""
    **Architecture**
    - 🧠 AI Audit → n8n + Claude
    - ⚡ Execution → Google Colab
    - 📦 Storage → In-session only
    """)

    st.markdown("---")
    st.markdown("**Current Step**")
    step_labels = {1: "📂 Upload & Audit", 2: "🛠 Define Rules", 3: "📥 Export"}
    st.info(step_labels.get(st.session_state.step, "—"))

    st.markdown("---")
    if st.button("🔁 Reset Session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
