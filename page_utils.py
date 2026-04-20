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
    """Render the full-width orange DESi Field AI header."""
    import streamlit as st
    logo_img = (
        f'<img src="data:image/png;base64,{_LOGO_B64}" '
        f'style="height:60px;width:60px;border-radius:50%;object-fit:cover;">'
        if _LOGO_B64 else ""
    )
    st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] > .main > div:first-child,
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.main .block-container,
section[data-testid="stMain"] > div:first-child {{
    padding-top: 0 !important;
    margin-top: 0 !important;
}}
[data-testid="stDecoration"] {{ display: none !important; }}
.desi-header {{
    background-color: #F7941D;
    padding: 20px 3.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-left: -3.5rem;
    margin-right: -3.5rem;
    margin-top: 0;
    margin-bottom: 1.2rem;
    font-family: 'Inter', system-ui, sans-serif;
    border-radius: 0 0 16px 16px;
}}
.desi-header-title {{
    font-size: 1.9rem;
    font-weight: 800;
    color: white;
    line-height: 1.2;
}}
.desi-header-subtitle {{
    font-size: 0.9rem;
    color: rgba(255,255,255,0.85);
    margin-top: 3px;
}}
@media (max-width: 900px) {{
    .desi-header {{ padding: 18px 1.2rem; margin-left: -1.2rem; margin-right: -1.2rem; }}
}}
@media (max-width: 640px) {{
    .desi-header {{ padding: 14px 0.75rem; margin-left: -0.75rem; margin-right: -0.75rem; }}
    .desi-header-title {{ font-size: 1.4rem; }}
    .desi-header-subtitle {{ font-size: 0.8rem; }}
}}
</style>
<div class="desi-header">
    <div>
        <div class="desi-header-title">Retail AI</div>
        <div class="desi-header-subtitle">AI-Powered Sales Intelligence</div>
    </div>
    {logo_img}
</div>
""", unsafe_allow_html=True)
