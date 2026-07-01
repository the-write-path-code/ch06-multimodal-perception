# Section 6.5: Interactive Multimodal Perception Explorer

import os
import sys
import base64
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image
import gradio as gr
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()

# Force in-memory Qdrant for demo to ensure it runs out-of-the-box
os.environ["QDRANT_URL"] = ":memory:"

from ch6.config import config
from ch6.logging import logger
from ch6.pipeline import PerceptionPipeline
from ch6.query import SearchService

# Global state for services
pipeline: Optional[PerceptionPipeline] = None
search_service: Optional[SearchService] = None

# Custom styling for clean dark mode dashboard
CSS = """
body {
    background-color: #0b0f19 !important;
}
.sidebar-container {
    background-color: #111827;
    border-radius: 12px;
    padding: 16px;
    border: 1px solid #1f2937;
}
.doc-item {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    margin-bottom: 8px;
    border-radius: 8px;
    background-color: #1f2937;
    font-size: 0.85rem;
    color: #e5e7eb;
}
.doc-item span.icon {
    font-size: 1.1rem;
    margin-right: 8px;
}
.doc-badge {
    margin-left: auto;
    font-size: 0.7rem;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}
.badge-pdf { background-color: #2563eb; color: white; }
.badge-image { background-color: #16a34a; color: white; }
.badge-audio { background-color: #ea580c; color: white; }
.badge-table { background-color: #9333ea; color: white; }

.result-card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.score-badge {
    background-color: #334155;
    color: #f1f5f9;
    font-weight: bold;
    font-size: 0.85rem;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid #475569;
}
.preview-box {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    color: #cbd5e1;
    font-family: monospace;
    font-size: 0.85rem;
    padding: 10px;
    border-radius: 8px;
    margin: 8px 0;
    white-space: pre-wrap;
    word-break: break-all;
}
.details-summary {
    color: #3b82f6;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    margin-top: 8px;
    user-select: none;
}
.details-summary:hover {
    text-decoration: underline;
}
.structured-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
    font-size: 0.8rem;
    color: #f1f5f9;
}
.structured-table th, .structured-table td {
    border: 1px solid #334155;
    padding: 6px 10px;
    text-align: left;
    color: #cbd5e1 !important;
}
.structured-table td strong {
    color: #94a3b8 !important;
}
.structured-table th {
    background-color: #0f172a;
    color: #94a3b8 !important;
}
.structured-table tr:nth-child(even) {
    background-color: #1e293b;
}
"""

def detect_modality_icon_and_label(filepath: str) -> Tuple[str, str]:
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return "📄", "pdf"
    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        return "🖼️", "image"
    elif ext in [".csv", ".xlsx", ".xls"]:
        return "📊", "table"
    elif ext in [".wav", ".mp3", ".m4a"]:
        return "🔊", "audio"
    return "📝", "text"

def build_sidebar_html(files: List[str]) -> str:
    """Builds document checklist html with badges for the sidebar."""
    if not files:
        return "<div style='color:#9ca3af;font-style:italic;'>No documents ingested yet.</div>"
    
    html = "<div class='sidebar-container'>"
    html += "<h3 style='margin-top:0;color:white;font-size:1rem;margin-bottom:12px;'>Indexed Documents</h3>"
    for f in sorted(files):
        name = os.path.basename(f)
        icon, label = detect_modality_icon_and_label(f)
        html += f"""
        <div class='doc-item'>
            <span class='icon'>{icon}</span>
            <span style='text-overflow:ellipsis;overflow:hidden;white-space:nowrap;max-width:180px;'>{name}</span>
            <span class='doc-badge badge-{label}'>{label}</span>
        </div>
        """
    html += "</div>"
    return html

def render_results_html(results: List[Dict[str, Any]]) -> str:
    """Renders retrieval search hits into highly styled HTML blocks."""
    if not results:
        return """
        <div style='text-align:center;padding:40px;color:#94a3b8;'>
            <div style='font-size:1.5rem;margin-bottom:8px;'>🔍</div>
            <div>No matching segments found. Try tweaking your query or re-indexing files.</div>
        </div>
        """
    
    html = ""
    for r in results:
        modality = r["modality"]
        score = r["score"]
        source_file = os.path.basename(r["source_file"] or "unknown")
        preview = r["content_preview"] or ""
        structured = r["structured_data"]
        
        # Build structured data table if present
        structured_html = ""
        if structured and isinstance(structured, dict):
            rows = ""
            for k, v in structured.items():
                if isinstance(v, dict):
                    v_str = ", ".join(f"{sk}: {sv}" for sk, sv in v.items())
                elif isinstance(v, list):
                    v_str = ", ".join(str(item) for item in v)
                else:
                    v_str = str(v)
                rows += f"<tr><td><strong>{k}</strong></td><td>{v_str}</td></tr>"
            
            if rows:
                structured_html = f"""
                <details style="margin-top:10px;">
                    <summary class="details-summary">▸ View Extracted Schema</summary>
                    <table class="structured-table">
                        <thead>
                            <tr><th>Field</th><th>Value</th></tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </details>
                """
        
        # Build image inline preview thumbnail
        thumbnail_html = ""
        if modality == "image" and r["source_file"] and os.path.exists(r["source_file"]):
            try:
                with open(r["source_file"], "rb") as img_f:
                    b64 = base64.b64encode(img_f.read()).decode("utf-8")
                thumbnail_html = f"""
                <div style="margin-right:15px;flex-shrink:0;margin-top:4px;">
                    <img src="data:image/png;base64,{b64}" style="max-height:100px;max-width:140px;border-radius:6px;border:1px solid #475569;" />
                </div>
                """
            except Exception as e:
                logger.warn("Failed to generate inline image thumbnail", error=str(e))
                
        # Modality badge
        icon, label = detect_modality_icon_and_label(source_file)
        
        html += f"""
        <div class="result-card">
            <div class="result-header">
                <span class="modality-badge badge-{label}">{icon} {modality.upper()}</span>
                <span class="score-badge">Similarity: {score:.4f}</span>
            </div>
            <div style="display:flex;align-items:flex-start;">
                {thumbnail_html}
                <div style="flex-grow:1;min-width:0;">
                    <div style="font-weight:600;font-size:0.95rem;color:#f1f5f9;margin-bottom:4px;">{source_file}</div>
                    <div class="preview-box">{preview}</div>
                    {structured_html}
                </div>
            </div>
        </div>
        """
    return html

async def startup_ingest() -> Tuple[str, str]:
    """Auto-ingests standard sample files into vector catalog on app startup."""
    global pipeline, search_service
    if pipeline is None:
        pipeline = PerceptionPipeline()
        await pipeline.initialize()
    if search_service is None:
        search_service = SearchService()

    sample_dir = Path("data/samples")
    files_to_index = [
        sample_dir / "patient_care_protocol.pdf",
        sample_dir / "insurance_card_front.png",
        sample_dir / "home_health_visits.csv",
        sample_dir / "nurse_visit_note_001.wav"
    ]
    
    ingested_paths = []
    logger.info("Starting auto-indexing lifecycle...")
    
    for f in files_to_index:
        if f.exists():
            try:
                await pipeline.ingest_document(str(f))
                ingested_paths.append(str(f))
            except Exception as e:
                logger.error("Failed to auto-ingest file", path=str(f), error=str(e))
        else:
            logger.warn("Auto-ingest file target missing", path=str(f))
            
    sidebar = build_sidebar_html(ingested_paths)
    status = f"System initialized. Ingested {len(ingested_paths)} sample documents on startup into in-memory collection '{config.qdrant_collection}'."
    return sidebar, status

async def handle_reindex() -> Tuple[str, str]:
    """Wipes the Qdrant memory collection and rebuilds standard samples index."""
    global pipeline, search_service
    if pipeline is None or search_service is None:
        return "", "Services not initialized yet."
        
    try:
        logger.info("Wiping and re-indexing Qdrant memory vector storage...")
        # Wiping collection
        await pipeline.catalog.client.delete_collection(pipeline.catalog.collection_name)
        # Re-initializing
        await pipeline.initialize()
        
        # SQLite db remains active, override/register fresh doc paths
        sidebar, status = await startup_ingest()
        return sidebar, "Successfully wiped vector storage and re-indexed all corpus data. " + status
    except Exception as e:
        logger.error("Failed to perform complete re-indexing", error=str(e))
        return "", f"Error during re-indexing: {str(e)}"

async def generate_final_answer(question: str, results: List[Dict[str, Any]]) -> str:
    """Uses the VLM client to generate a conversational answer based on retrieved documents context."""
    global pipeline
    if not results or not pipeline:
        return "No relevant context found to answer this query."
        
    context = ""
    for idx, r in enumerate(results):
        source = os.path.basename(r["source_file"] or "unknown")
        preview = r["content_preview"] or ""
        context += f"Source [{source}]: {preview}\n\n"
        
    prompt = (
        "You are a helpful clinical perception assistant. Answer the user's question using ONLY the provided retrieved context. "
        "Formulate a direct, conversational, and precise answer. Do not add any extra conversational intros or generic commentary. "
        "If the answer cannot be determined from the context, state that clearly.\n\n"
        f"Retrieved Context:\n{context}\n"
        f"User Question: {question}\n\n"
        "Final Answer:"
    )
    
    try:
        # Access VLMClient from pipeline's dispatcher
        vlm_client = pipeline.dispatcher.image_extractor.vlm_client
        response_dict = await vlm_client.analyze_image(prompt=prompt)
        if isinstance(response_dict, dict) and "raw_text" in response_dict:
            return response_dict["raw_text"]
        elif isinstance(response_dict, dict) and "summary" in response_dict:
            return response_dict["summary"]
        return str(response_dict)
    except Exception as e:
        logger.error("Failed to generate conversational RAG answer", error=str(e))
        return f"Could not generate conversational answer (VLM Error: {str(e)})"

async def handle_search(
    text_query: str, 
    image_query: Optional[Image.Image], 
    modality_filter: str, 
    top_k: float
) -> Tuple[str, str]:
    """Runs cross-modal or dense searches through unified retrieval service."""
    global search_service
    if not search_service:
        return "", "Search service is offline."
        
    if not text_query.strip() and image_query is None:
        return """
        <div style='text-align:center;padding:40px;color:#f43f5e;'>
            <strong>Warning:</strong> Please enter a text question or upload an image crop to query vector collection.
        </div>
        """, "Query parameters missing."
        
    mapped_filter = None if modality_filter == "All" else modality_filter.lower()
    start_time = time.time()
    
    try:
        results = await search_service.search(
            text_query=text_query.strip() if text_query.strip() else None,
            image_query=image_query,
            top_k=int(top_k),
            filter_modality=mapped_filter
        )
        elapsed = time.time() - start_time
        
        # Format list results
        html_output = ""
        
        # Synthesize a final conversational answer if it's a text-based query
        if text_query.strip() and results:
            answer = await generate_final_answer(text_query.strip(), results)
            html_output += f"""
            <div style="background: linear-gradient(135deg, #1e1b4b 0%, #1e293b 100%); border: 1px solid #4f46e5; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);">
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    <span style="font-size: 1.2rem; margin-right: 8px;">✨</span>
                    <strong style="color: #a5b4fc; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.05em;">AI Conversational Answer</strong>
                </div>
                <div style="color: #e2e8f0; font-size: 1rem; line-height: 1.6; white-space: pre-wrap;">{answer}</div>
            </div>
            """
            
        html_output += render_results_html(results)
        status_msg = f"Retrieved {len(results)} matches in {elapsed:.3f} seconds."
        return html_output, status_msg
    except Exception as e:
        logger.error("Search query execution failed", error=str(e))
        err_html = f"""
        <div style='text-align:center;padding:40px;color:#f43f5e;'>
            <strong>Error executing query:</strong><br/>
            <code style='background:#1f2937;padding:4px 8px;border-radius:4px;'>{str(e)}</code>
        </div>
        """
        return err_html, f"Query failed: {str(e)}"

def main():
    # Sync async loop for Gradio startup
    logger.info("Initializing background modules for Multimodal perception web dashboard...")
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    sidebar_html_init, status_init = loop.run_until_complete(startup_ingest())

    # Build Gradio UI block structure
    with gr.Blocks(title="Multimodal Perception Explorer") as demo:
        gr.Markdown(
            """
            # Ch6 · Multimodal Perception Explorer
            Interact with the hybrid ingestion pipeline. Query clinical notes, text policies, CSV tables, and visual card models in a single vector search space.
            """
        )
        
        with gr.Row():
            # Sidebar Column
            with gr.Column(scale=1):
                sidebar = gr.HTML(value=sidebar_html_init)
                reindex_btn = gr.Button("🔄 Re-index Documents", variant="secondary")
                
            # Main Search Column
            with gr.Column(scale=3):
                with gr.Row():
                    with gr.Column(scale=2):
                        text_input = gr.Textbox(
                            label="Text Query",
                            placeholder="Type a question, entity name, or keyword...",
                            lines=3
                        )
                    with gr.Column(scale=1):
                        image_input = gr.Image(
                            label="Image Query (Visual similarity search)",
                            type="pil"
                        )
                
                with gr.Row():
                    modality_filter = gr.Radio(
                        choices=["All", "pdf", "image", "audio", "table"],
                        value="All",
                        label="Modality Filter"
                    )
                    top_k_slider = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=5,
                        step=1,
                        label="Top-K Results"
                    )
                
                search_btn = gr.Button("🔍 Search Collection", variant="primary")
                status_box = gr.Textbox(value=status_init, label="System Logs", interactive=False)
                
                gr.Markdown("### Ranked Similarity Results")
                results_display = gr.HTML(
                    value="<div style='color:#94a3b8;font-style:italic;'>Run a search above to display similarity results.</div>"
                )

        # Pre-configured queries list
        gr.Markdown("### Pre-Configured Examples")
        gr.Examples(
            examples=[
                ["What is the copay amount on the insurance card?", None, "All", 5],
                ["John Smith patient checkup visit", None, "audio", 3],
                ["Member ID HFP-98765432-01", None, "image", 2],
                ["Blood pressure reading", None, "All", 5],
                ["", "data/samples/insurance_card_front.png", "All", 3]
            ],
            inputs=[text_input, image_input, modality_filter, top_k_slider],
            outputs=[results_display, status_box],
            fn=handle_search,
            cache_examples=False
        )

        # Wire click and update actions
        search_btn.click(
            fn=handle_search,
            inputs=[text_input, image_input, modality_filter, top_k_slider],
            outputs=[results_display, status_box]
        )
        
        reindex_btn.click(
            fn=handle_reindex,
            inputs=[],
            outputs=[sidebar, status_box]
        )

    # Launch local server
    demo.launch(server_name="127.0.0.1", server_port=7860, css=CSS, inbrowser=True)

if __name__ == "__main__":
    main()
