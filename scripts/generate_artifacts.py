# Section 6.5: Book Visual Artifacts Generator

import os
import sys
import csv
import base64
import asyncio
import re
import hashlib
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pypdfium2 as pdfium
import matplotlib.pyplot as plt

# Ensure PYTHONPATH includes src
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

# Force memory URL for database safety
os.environ["QDRANT_URL"] = ":memory:"

from ch6.config import config
from ch6.logging import logger
from ch6.pipeline import PerceptionPipeline
from ch6.perception.pdf import PDFExtractor
from ch6.perception.sensitivity import SensitivityScanner
from ch6.embedding.dense import DenseEncoder

# Color maps for visualization
LAYOUT_COLORS = {
    "Text": "#3b82f6",         # blue
    "Paragraph": "#3b82f6",    # blue
    "Table": "#9333ea",        # purple
    "Picture": "#16a34a",      # green
    "Image": "#16a34a",        # green
    "Figure": "#16a34a",       # green
    "Title": "#f59e0b",        # amber
    "Heading": "#f59e0b",      # amber
    "Section": "#f59e0b",      # amber
    "List": "#06b6d4",         # cyan
    "ListItem": "#06b6d4"      # cyan
}

def hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def draw_layout_boundaries(pdf_path: Path, output_dir: Path):
    """Artifact 1: Docling Layout Detection Bounding Boxes."""
    logger.info("Generating Artifact 1: Docling Layout Boundaries...")
    from docling.document_converter import DocumentConverter
    
    # 1. Run Docling Layout Analysis
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    # 2. Open PDF with pdfium
    pdf_doc = pdfium.PdfDocument(str(pdf_path))
    
    # Draw page by page
    for page_idx in range(len(pdf_doc)):
        page_num = page_idx + 1
        pdfium_page = pdf_doc[page_idx]
        
        # Render at high resolution (scale 3.0 = 216 DPI)
        pil_image = pdfium_page.render(scale=3.0).to_pil()
        img_w, img_h = pil_image.size
        
        # Get page sizes
        page_size = doc.pages.get(page_num)
        page_width = page_size.size.width if page_size else 612.0
        page_height = page_size.size.height if page_size else 792.0
        
        scale_x = img_w / page_width
        scale_y = img_h / page_height
        
        # Create alpha transparency overlay
        overlay = Image.new("RGBA", pil_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Draw bounding boxes
        for element, level in doc.iterate_items():
            prov = getattr(element, "prov", None)
            if not prov or not len(prov):
                continue
            
            page_info = prov[0]
            if page_info.page_no != page_num:
                continue
                
            bbox = page_info.bbox
            class_name = element.__class__.__name__
            
            # Map class name to standard colors
            color_hex = "#6b7280" # default gray
            for key, val in LAYOUT_COLORS.items():
                if key in class_name:
                    color_hex = val
                    break
                    
            color_rgb = hex_to_rgb(color_hex)
            
            l = getattr(bbox, "l", 0.0)
            b = getattr(bbox, "b", 0.0)
            r = getattr(bbox, "r", 0.0)
            t = getattr(bbox, "t", 0.0)
            
            x0 = int(l * scale_x)
            x1 = int(r * scale_x)
            y0 = int((page_height - t) * scale_y)
            y1 = int((page_height - b) * scale_y)
            
            # Draw semi-transparent filled rectangle
            draw.rectangle(
                [x0, y0, x1, y1],
                fill=(color_rgb[0], color_rgb[1], color_rgb[2], 30),
                outline=color_hex,
                width=3
            )
            
            # Draw a clean badge label
            badge_text = class_name.replace("Element", "")
            draw.text((x0 + 4, y0 + 2), badge_text, fill=color_hex)

        # Draw a Legend at the bottom
        final_w = img_w
        legend_h = 80
        legend_img = Image.new("RGB", (final_w, legend_h), "#0f172a")
        legend_draw = ImageDraw.Draw(legend_img)
        
        legend_items = [
            ("Text / Paragraphs", "#3b82f6"),
            ("Tabular Tables", "#9333ea"),
            ("Figures / Charts", "#16a34a"),
            ("Titles / Headings", "#f59e0b"),
            ("Lists / Items", "#06b6d4"),
        ]
        
        spacing = final_w // len(legend_items)
        for i, (label, color_hex) in enumerate(legend_items):
            x_pos = i * spacing + 20
            y_pos = 30
            legend_draw.rectangle([x_pos, y_pos, x_pos + 20, y_pos + 20], fill=color_hex, outline="white", width=1)
            legend_draw.text((x_pos + 30, y_pos + 4), label, fill="#f8fafc")
            
        # Combine page render + legend
        combined = Image.new("RGB", (img_w, img_h + legend_h))
        combined.paste(Image.alpha_composite(pil_image.convert("RGBA"), overlay).convert("RGB"), (0, 0))
        combined.paste(legend_img, (0, img_h))
        
        output_file = output_dir / f"layout_detection_page{page_num}.png"
        combined.save(output_file, "PNG", dpi=(300, 300))
        logger.info(f"Saved layout detection visual: {output_file}")
        
    pdf_doc.close()

async def generate_embedding_space_tsne(pipeline: PerceptionPipeline, output_dir: Path):
    """Artifact 2: Shared Cross-Modal t-SNE Projection."""
    logger.info("Generating Artifact 2: Shared Cross-Modal t-SNE Plot...")
    
    # 1. Fetch points from Qdrant
    points, _ = await pipeline.catalog.client.scroll(
        collection_name=pipeline.catalog.collection_name,
        limit=100,
        with_vectors=True,
        with_payload=True
    )
    
    vectors = []
    modalities = []
    filenames = []
    
    for pt in points:
        vec = pt.vector.get("dense")
        if vec:
            vectors.append(vec)
            modalities.append(pt.payload.get("modality", "unknown"))
            filenames.append(os.path.basename(pt.payload.get("source_file", "unknown")))
            
    # Embed sample queries
    queries = [
        "What is the copay amount on the insurance card?",
        "John Smith patient checkup visit notes",
        "Clinical care coordination policies"
    ]
    encoder = DenseEncoder()
    query_vecs = encoder.embed_text(queries)
    
    all_vectors = np.vstack([np.array(vectors), np.array(query_vecs)])
    
    # 2. Run t-SNE
    from sklearn.manifold import TSNE
    perplexity = min(5, len(all_vectors) - 1)
    reducer = TSNE(n_components=2, perplexity=perplexity, metric="cosine", random_state=42, init="random")
    embeddings_2d = reducer.fit_transform(all_vectors)
    
    doc_len = len(vectors)
    doc_2d = embeddings_2d[:doc_len]
    query_2d = embeddings_2d[doc_len:]
    
    # 3. Plotting
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
    
    color_map = {
        "pdf": ("#3b82f6", "o", "PDF Text Chunks"),
        "image": ("#16a34a", "s", "VLM Visual Chunks"),
        "audio": ("#ea580c", "^", "Audio Chunks"),
        "table": ("#9333ea", "D", "CSV Tabular Profile")
    }
    
    # Scatter doc points
    for mod, (color, marker, label) in color_map.items():
        idxs = [i for i, m in enumerate(modalities) if m == mod]
        if idxs:
            ax.scatter(
                doc_2d[idxs, 0], doc_2d[idxs, 1],
                color=color, marker=marker, label=label,
                s=120, alpha=0.85, edgecolors="#f8fafc", linewidths=0.5
            )
            
            # Label document names
            for idx in idxs:
                ax.annotate(
                    filenames[idx],
                    (doc_2d[idx, 0], doc_2d[idx, 1]),
                    xytext=(5, 5), textcoords="offset points",
                    fontsize=7, color="#cbd5e1", alpha=0.8
                )
                
    # Scatter query points
    ax.scatter(
        query_2d[:, 0], query_2d[:, 1],
        color="#ef4444", marker="*", label="Text Queries",
        s=250, edgecolors="white", linewidths=0.5, zorder=10
    )
    
    for i, q in enumerate(queries):
        ax.annotate(
            f"Query: \"{q[:35]}...\"",
            (query_2d[i, 0], query_2d[i, 1]),
            xytext=(6, -10), textcoords="offset points",
            fontsize=8, color="#fca5a5", weight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="#ef4444", alpha=0.15, ec="#ef4444")
        )
        
    ax.set_title("Cross-Modal Shared Vector Space (CLIP t-SNE Projection)", fontsize=14, pad=15, weight="bold", color="#f8fafc")
    ax.set_xlabel("t-SNE Dimension 1", fontsize=10, color="#94a3b8")
    ax.set_ylabel("t-SNE Dimension 2", fontsize=10, color="#94a3b8")
    ax.legend(loc="upper right", frameon=True, facecolor="#1e293b", edgecolor="#334155")
    ax.grid(True, color="#1e293b", linestyle="--", alpha=0.5)
    
    output_file = output_dir / "embedding_space_tsne.png"
    plt.savefig(output_file, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved embedding space plot: {output_file}")

def generate_pii_redaction_before_after(csv_path: Path, output_dir: Path):
    """Artifact 3: PII Redaction Visualizer."""
    logger.info("Generating Artifact 3: PII Redaction Before/After...")
    
    # 1. Parse CSV and build raw clinical note text block
    raw_texts = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for _, row in zip(range(4), reader):
            raw_texts.append(
                f"Patient record: Nurse {row['nurse_name']} completed home visit on date {row['visit_date']}. "
                f"Service charges totaled ${row['billing_amount']} under diagnostic code {row['diagnosis_code']}. "
                f"Clinical progress log: {row['notes']}"
            )
            
    raw_paragraph = "\n\n".join(raw_texts)
    
    # 2. Run Redaction Scanner
    scanner = SensitivityScanner()
    redacted_paragraph = scanner.redact_pii(raw_paragraph)
    
    # 3. Render side-by-side matplotlib image
    plt.style.use("dark_background")
    fig, (ax_before, ax_after) = plt.subplots(1, 2, figsize=(16, 9), dpi=300)
    
    for ax in (ax_before, ax_after):
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        
    ax_before.set_title("BEFORE REDACTION (PII / PHI Highlighted)", fontsize=12, pad=15, weight="bold", color="#ef4444")
    ax_after.set_title("AFTER REDACTION (Grounded Protection)", fontsize=12, pad=15, weight="bold", color="#22c55e")
    
    # We will format and wrap text to render cleanly inside matplotlib panels
    def wrap_and_draw(ax, text, highlight_pii=False):
        lines = text.split("\n")
        y_pos = 0.95
        line_height = 0.045
        
        for line in lines:
            if not line.strip():
                y_pos -= line_height
                continue
                
            # Basic text wrap
            words = line.split(" ")
            current_line = ""
            for word in words:
                if len(current_line) + len(word) > 75:
                    # Draw current line
                    draw_line_segments(ax, current_line, y_pos, highlight_pii)
                    y_pos -= line_height
                    current_line = word + " "
                else:
                    current_line += word + " "
            if current_line:
                draw_line_segments(ax, current_line, y_pos, highlight_pii)
                y_pos -= line_height
            
            y_pos -= 0.02 # double spacing between paragraphs

    def draw_line_segments(ax, line, y_pos, highlight_pii):
        # If highlighting PII, parse and highlight nurse names (like Daniel Doyle, Olivia Moore, Calvin Nielsen, Holly Wood)
        pii_names = ["Daniel Doyle", "Olivia Moore", "Calvin Nielsen", "Holly Wood"]
        
        # Draw line segment by segment to color PII text
        if highlight_pii:
            pattern = "|".join([re.escape(name) for name in pii_names])
            parts = re.split(f"({pattern})", line)
            
            x_pos = 0.02
            for part in parts:
                if not part:
                    continue
                is_pii = part in pii_names
                color = "#ef4444" if is_pii else "#cbd5e1"
                weight = "bold" if is_pii else "normal"
                
                # Add highlighting background for PII
                bbox = dict(boxstyle="round,pad=0.15", fc="#ef4444", alpha=0.25, ec="none") if is_pii else None
                
                ax.text(
                    x_pos, y_pos, part,
                    fontsize=8, fontfamily="monospace",
                    color=color, weight=weight, bbox=bbox,
                    transform=ax.transAxes, verticalalignment="top"
                )
                
                # Estimate text bounds to advance x position (approximate spacing per char)
                x_pos += len(part) * 0.0118
        else:
            # Under redaction, replace [REDACTED] formatting with special highlighting
            parts = re.split(r"(\[REDACTED\])", line)
            x_pos = 0.02
            for part in parts:
                if not part:
                    continue
                is_redacted = part == "[REDACTED]"
                color = "#22c55e" if is_redacted else "#cbd5e1"
                weight = "bold" if is_redacted else "normal"
                bbox = dict(boxstyle="round,pad=0.15", fc="#22c55e", alpha=0.25, ec="none") if is_redacted else None
                
                ax.text(
                    x_pos, y_pos, part,
                    fontsize=8, fontfamily="monospace",
                    color=color, weight=weight, bbox=bbox,
                    transform=ax.transAxes, verticalalignment="top"
                )
                x_pos += len(part) * 0.0118

    wrap_and_draw(ax_before, raw_paragraph, highlight_pii=True)
    wrap_and_draw(ax_after, redacted_paragraph, highlight_pii=False)
    
    output_file = output_dir / "pii_redaction_before_after.png"
    plt.savefig(output_file, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved PII Redaction visual: {output_file}")

async def main():
    logger.info("Initializing synthetic pipeline elements...")
    
    # 1. Setup paths
    output_dir = Path("artifacts")
    output_dir.mkdir(exist_ok=True)
    
    pdf_path = Path("data/samples/patient_care_protocol.pdf")
    csv_path = Path("data/samples/home_health_visits.csv")
    
    # 2. Initialize pipeline and run sample ingestion
    pipeline = PerceptionPipeline()
    await pipeline.initialize()
    
    sample_files = [
        "data/samples/patient_care_protocol.pdf",
        "data/samples/insurance_card_front.png",
        "data/samples/home_health_visits.csv",
        "data/samples/nurse_visit_note_001.wav",
    ]
    
    logger.info("Ingesting sample documents into isolated vector storage...")
    for f in sample_files:
        if os.path.exists(f):
            await pipeline.ingest_document(f)
            
    # 3. Generate all 3 visuals
    if pdf_path.exists():
        draw_layout_boundaries(pdf_path, output_dir)
        
    await generate_embedding_space_tsne(pipeline, output_dir)
    
    if csv_path.exists():
        generate_pii_redaction_before_after(csv_path, output_dir)

    logger.info("Successfully generated all visual book artifacts in folder 'artifacts/'!")

if __name__ == "__main__":
    asyncio.run(main())
