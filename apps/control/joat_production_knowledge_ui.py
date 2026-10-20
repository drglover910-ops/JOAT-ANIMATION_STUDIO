"""Owner-only evidence retrieval in existing capability tools. File version: 1.0.1."""
FILE_VERSION = '1.0.1'
import os
from typing import Optional
import gradio as gr
from joat_production_knowledge import VALID_ROLES, retrieve


def lookup(query: str, role: str, project: str, style: str,
           profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken],
           request: gr.Request):
    from joat_managed_generation import owner_token
    owner_token(profile, oauth, request)
    try:
        return retrieve(query, role=role, project_id=project.strip() or None,
                        style_id=style.strip() or None)
    except (ValueError, OSError, KeyError, TypeError):
        raise gr.Error('Reviewed knowledge is unavailable or invalid; no execution was requested.') from None


def add_knowledge_tools():
    gr.Markdown('Reviewed production knowledge v1.0.1 — CPU only. Includes Studio ownership, GPU accounting and the scoped Style001 finish checkpoint. Main coordinates requests; '
                'Director owns studio creative work. These notes never replace locked '
                'packets, spending permission, or final QC. Project lessons require an explicit project ID.')
    default = 'main' if os.environ.get('SPACE_ID', '').endswith('Main-Assistant-Bot') else 'director'
    role = gr.Dropdown(choices=sorted(VALID_ROLES), value=default, label='Department for reviewed guidance')
    project = gr.Textbox(label='Project ID — optional; blank retrieves general guidance only')
    style = gr.Textbox(label='Style ID — optional')
    query = gr.Textbox(label='Find reviewed guidance')
    output = gr.JSON(label='Reviewed evidence — not execution or quality approval')
    gr.Button('Read approved production guidance — no GPU').click(
        lookup, [query, role, project, style], output,
        api_name='studio_production_knowledge', api_visibility='undocumented')
