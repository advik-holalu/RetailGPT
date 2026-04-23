"""
page_utils.py
Shared utilities for all pages — safe to import without triggering set_page_config.
"""

import os
import base64


def get_logo_base64() -> str:
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "godesi_logo.png")
    try:
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


_LOGO_B64 = get_logo_base64()


def render_header() -> None:
    """Render the orange Retail AI header card."""
    import streamlit as st
    logo_img = (
        f'<img src="data:image/png;base64,{_LOGO_B64}" '
        f'style="height:56px;width:56px;border-radius:50%;object-fit:cover;flex-shrink:0;">'
        if _LOGO_B64 else ""
    )
    st.markdown(f"""
<style>
[data-testid="stDecoration"] {{ display: none !important; }}
.desi-header {{
    background: linear-gradient(135deg, #F7941D 0%, #e8820a 100%);
    padding: 1.6rem 2rem;
    border-radius: 14px;
    margin-bottom: 0.9rem;
    font-family: 'Inter', system-ui, sans-serif;
}}
.desi-header-title {{
    font-size: 1.9rem;
    font-weight: 800;
    color: #fff;
    line-height: 1.1;
    letter-spacing: -0.02em;
}}
.desi-header-subtitle {{
    font-size: 0.82rem;
    color: rgba(255,255,255,0.8);
    margin-top: 2px;
    font-weight: 400;
}}
@media (max-width: 640px) {{
    .desi-header {{ padding: 0.75rem 1rem; }}
    .desi-header-title {{ font-size: 1.3rem; }}
}}
</style>
<div class="desi-header">
    <div style="display:flex;align-items:center;gap:1rem;">
        {logo_img}
        <div>
            <div class="desi-header-title">Retail AI</div>
            <div class="desi-header-subtitle">AI Powered Sales Intelligence</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
