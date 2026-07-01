# Section 6.1: Sample Data Generator

import os
import sys
import json
import wave
import struct
import asyncio
from pathlib import Path
import pandas as pd
from faker import Faker
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import av
import edge_tts

# Instantiation of Faker
fake = Faker()
Faker.seed(42)

# Ensure sample output directories exist
SAMPLE_DIR = Path("data/samples")
GT_DIR = SAMPLE_DIR / "ground_truth"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
GT_DIR.mkdir(parents=True, exist_ok=True)

# Tracing context variables (simulating TracedLogger from src/ch6/logging.py)
print(f"Initializing sample generator. Saving all files to {SAMPLE_DIR}")

# ---------------------------------------------------------
# Audio Transcoding & Edge TTS Logic
# ---------------------------------------------------------

def mp3_to_wav(mp3_path: Path, wav_path: Path):
    """Transcodes an MP3 file into a standard 16kHz mono WAV file for Whisper using PyAV."""
    try:
        with av.open(str(mp3_path)) as src, av.open(str(wav_path), 'w') as dst:
            in_stream = src.streams.audio[0]
            out_stream = dst.add_stream('pcm_s16le', rate=16000, layout='mono')
            resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)

            for packet in src.demux(in_stream):
                for frame in packet.decode():
                    resampled_frames = resampler.resample(frame)
                    if resampled_frames:
                        for res_frame in resampled_frames:
                            res_frame.pts = None
                            for out_packet in out_stream.encode(res_frame):
                                dst.mux(out_packet)
            # Flush encoder
            for out_packet in out_stream.encode():
                dst.mux(out_packet)
        print(f"Transcoded {mp3_path.name} to {wav_path.name} successfully.")
    except Exception as e:
        print(f"Error transcoding {mp3_path} to {wav_path}: {e}. Generating fallback silence.")
        generate_silent_wav(wav_path, duration=10)

def generate_silent_wav(wav_path: Path, duration: int = 5, sample_rate: int = 16000):
    """Generates a dummy 16-bit PCM mono WAV file of silent frames."""
    with wave.open(str(wav_path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        num_frames = sample_rate * duration
        data = struct.pack('<' + 'h' * num_frames, *([0] * num_frames))
        w.writeframes(data)
    print(f"Generated silent WAV at {wav_path}")

async def generate_tts_audio(text: str, output_wav_path: Path, voice: str = "en-US-JennyNeural"):
    """Downloads TTS audio using edge-tts API and saves it as a 16kHz mono WAV file."""
    mp3_temp = output_wav_path.with_suffix(".mp3")
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(mp3_temp))
        mp3_to_wav(mp3_temp, output_wav_path)
    except Exception as e:
        print(f"Edge-TTS API failed: {e}. Generating silent WAV instead.")
        generate_silent_wav(output_wav_path, duration=10)
    finally:
        if mp3_temp.exists():
            mp3_temp.unlink()

# ---------------------------------------------------------
# PIL Image Generation
# ---------------------------------------------------------

def generate_synthetic_image(filename: str, text_lines: list[str], title: str):
    """Generates a synthetic medical/insurance card or schedule image using Pillow."""
    img_path = SAMPLE_DIR / filename
    width, height = 640, 400
    image = Image.new("RGBA", (width, height), color=(240, 245, 255, 255))
    draw = ImageDraw.Draw(image)

    # Draw card border and background elements
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=15, fill=(255, 255, 255, 255), outline=(50, 100, 200, 255), width=4)
    draw.rectangle([20, 20, width - 20, 80], fill=(50, 100, 200, 255))

    # Try loading default font
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # Title text
    draw.text((40, 35), title, fill=(255, 255, 255, 255), font=font)

    # Body text
    y_offset = 110
    for line in text_lines:
        draw.text((45, y_offset), line, fill=(40, 40, 40, 255), font=font)
        y_offset += 35

    # Decorative checkmarks
    draw.ellipse([width - 80, 40, width - 40, 80], fill=(100, 200, 100, 255))
    draw.line([width - 68, 62, width - 58, 70, width - 50, 52], fill=(255, 255, 255, 255), width=3)

    image.convert("RGB").save(str(img_path), "PNG")
    print(f"Generated image card at {img_path}")

# ---------------------------------------------------------
# ReportLab PDF Generation
# ---------------------------------------------------------

def draw_pdf_chart(canvas, doc):
    """Draws a synthetic chart figure on the PDF canvas using reportlab shape primitives."""
    canvas.saveState()
    # Draw simple axes
    canvas.setStrokeColor(colors.HexColor("#333333"))
    canvas.setLineWidth(2)
    canvas.line(100, 150, 400, 150) # X axis
    canvas.line(100, 150, 100, 350) # Y axis
    
    # Draw bars
    canvas.setFillColor(colors.HexColor("#3264c8"))
    canvas.rect(130, 150, 40, 120, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#c83264"))
    canvas.rect(200, 150, 40, 180, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#32c864"))
    canvas.rect(270, 150, 40, 80, fill=1, stroke=0)
    
    # Draw labels
    canvas.setFillColor(colors.HexColor("#111111"))
    canvas.drawString(135, 130, "Q1")
    canvas.drawString(205, 130, "Q2")
    canvas.drawString(275, 130, "Q3")
    canvas.drawString(110, 360, "Units Audited")
    canvas.restoreState()

def generate_synthetic_pdfs():
    """Creates synthetic multi-page PDF documents simulating corporate healthcare files."""
    styles = getSampleStyleSheet()
    
    # PDF 1: policy document
    pdf1_path = SAMPLE_DIR / "home_health_policy.pdf"
    doc1 = SimpleDocTemplate(str(pdf1_path), pagesize=letter)
    story1 = []
    story1.append(Paragraph("Home Health Audit & Billing Policy", styles["Title"]))
    story1.append(Spacer(1, 20))
    story1.append(Paragraph("Section 1.1: Scope of Audits", styles["Heading2"]))
    story1.append(Paragraph("This document covers the standards and billing compliance rules for all home health visits. All timesheet records must be signed by the attending nurse and validated by the client within 72 hours of completion. Failure to log correct hours will result in automatic billing flags.", styles["Normal"]))
    story1.append(Spacer(1, 15))
    story1.append(Paragraph("Section 1.2: Audit Trends Figure", styles["Heading2"]))
    story1.append(Spacer(1, 220)) # Leaving space for flow chart / bar chart drawn in canvas callbacks
    
    # We will build pages and add the custom canvas chart on page 1
    doc1.build(story1, onFirstPage=draw_pdf_chart)
    print(f"Generated PDF at {pdf1_path}")

    # PDF 2: Patient protocols with table
    pdf2_path = SAMPLE_DIR / "patient_care_protocol.pdf"
    doc2 = SimpleDocTemplate(str(pdf2_path), pagesize=letter)
    story2 = []
    story2.append(Paragraph("Patient Care Protocol Guidelines", styles["Title"]))
    story2.append(Spacer(1, 15))
    story2.append(Paragraph("Section 2.1: Care Codes Mapping", styles["Heading2"]))
    
    # Embed a Table
    data = [
        ["Service Code", "Description", "Max Hours"],
        ["S9123", "Nursing visit, home, clinical assessment", "2.0"],
        ["S9124", "Nursing visit, home, diabetic care", "1.5"],
        ["T1001", "Nursing assessment / evaluation", "3.0"]
    ]
    t = Table(data, colWidths=[100, 250, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3264c8")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#dddddd")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f9f9f9")])
    ]))
    story2.append(t)
    story2.append(Spacer(1, 20))
    story2.append(Paragraph("Ensure all treatments are completed as scheduled.", styles["Normal"]))
    doc2.build(story2)
    print(f"Generated PDF at {pdf2_path}")

# ---------------------------------------------------------
# Tabular CSV Data Generation
# ---------------------------------------------------------

def generate_csv_data():
    """Generates two heterogeneous schema CSV files simulating clinical registries."""
    csv1_path = SAMPLE_DIR / "home_health_visits.csv"
    
    # 500 rows for home_health_visits
    visits = []
    for _ in range(500):
        visits.append({
            "patient_id": fake.uuid4()[:8],
            "nurse_name": fake.name(),
            "visit_date": fake.date_between(start_date="-30d", end_date="today").isoformat(),
            "time_in": "09:00",
            "time_out": "11:30",
            "service_code": fake.random_element(elements=["S9123", "S9124", "T1001"]),
            "diagnosis_code": fake.random_element(elements=["I10", "E11.9", "Z74.01"]),
            "notes": fake.sentence(),
            "billing_amount": round(fake.random_number(digits=3) + 0.5, 2)
        })
    df_visits = pd.DataFrame(visits)
    df_visits.to_csv(str(csv1_path), index=False)
    print(f"Generated CSV visits log at {csv1_path}")

    # 200 rows for medical_supplies_inventory
    csv2_path = SAMPLE_DIR / "medical_supplies_inventory.csv"
    supplies = []
    for _ in range(200):
        supplies.append({
            "supply_id": "SUP-" + str(fake.random_number(digits=4)),
            "item_name": fake.random_element(elements=["Insulin Syringes", "Sterile Gauze", "Saline Solution", "Nitrile Gloves", "Adhesive Tape"]),
            "category": fake.random_element(elements=["Disposable", "Clinical", "Personal Protective"]),
            "quantity": fake.random_int(min=10, max=1000),
            "unit_price": round(fake.random_number(digits=2) + 0.99, 2),
            "reorder_level": fake.random_int(min=5, max=50),
            "supplier": fake.company(),
            "last_ordered": fake.date_between(start_date="-90d", end_date="today").isoformat()
        })
    df_supplies = pd.DataFrame(supplies)
    df_supplies.to_csv(str(csv2_path), index=False)
    print(f"Generated CSV supplies log at {csv2_path}")

# ---------------------------------------------------------
# Master Coordination & Ground Truth Logging
# ---------------------------------------------------------

async def main():
    print("Step 1: Generating PDFs...")
    generate_synthetic_pdfs()

    print("\nStep 2: Generating Images...")
    generate_synthetic_image(
        "insurance_card_front.png",
        [
            "Plan: HealthFirst Premium Care",
            "Member ID: HFP-98765432-01",
            "Group Number: GRP-55443",
            "Payer ID: 887621",
            "Copay: Office $20 / Specialist $40"
        ],
        "FirstHealth Insurance Card"
    )
    generate_synthetic_image(
        "insurance_card_back.png",
        [
            "Customer Service: 1-800-555-0199",
            "Provider Line: 1-800-555-0211",
            "Send claims to: PO Box 5000, Newark NJ",
            "Website: www.healthfirstpremium.com",
            "Pharmacist Helpdesk: BIN 004336"
        ],
        "Claims & Contact Information"
    )
    generate_synthetic_image(
        "medication_chart.png",
        [
            "Patient: Sarah Connor (DOB: 11/10/1965)",
            "Medication       | Dosage | Frequency | Route",
            "----------------------------------------------",
            "Metformin        | 500mg  | Twice daily| Oral",
            "Lisinopril       | 10mg   | Daily morning| Oral",
            "Atorvastatin     | 20mg   | Bedtime    | Oral"
        ],
        "Active Medication Administration Chart"
    )
    generate_synthetic_image(
        "visit_schedule_board.png",
        [
            "Nurse Care Scheduling Board - July 2026",
            "Nurse: Alex Mercer, RN",
            "--------------------------------------",
            "08:00 AM - visit patient John Smith (S9123)",
            "10:30 AM - visit patient Sarah Connor (S9124)",
            "02:00 PM - evaluation patient David Miller (T1001)"
        ],
        "Nurse Assignment Care Board"
    )

    print("\nStep 3: Generating heterogeneous CSV tables...")
    generate_csv_data()

    print("\nStep 4: Generating high-quality WAV speech notes via edge-tts...")
    audio_tasks = [
        generate_tts_audio(
            "Patient John Smith, date of birth March 15 1952. Arrived at 9:15 AM. Blood pressure 140 over 90. Administered insulin 10 units subcutaneously. Lungs are clear on auscultation.",
            SAMPLE_DIR / "nurse_visit_note_001.wav"
        ),
        generate_tts_audio(
            "Called Doctor Patel's office regarding patient medication change. Doctor confirmed increasing Lisinopril dosage to 20 milligrams once daily starting tomorrow. Patient was educated on tracking daily blood pressure.",
            SAMPLE_DIR / "care_coordination_call.wav"
        ),
        generate_tts_audio(
            "End of shift summary. Three patients seen today. First patient John Smith is stable. Second patient Sarah Connor reports nausea from Metformin. Doctor notified. Third patient David Miller needs social work follow up.",
            SAMPLE_DIR / "shift_handoff_summary.wav"
        )
    ]
    await asyncio.gather(*audio_tasks)

    # Write Ground Truth configuration details
    gt_data = {
        "nurse_visit_note_001.wav": {
            "modality": "audio",
            "transcript_contains": ["John Smith", "9:15 AM", "blood pressure", "140 over 90", "insulin"],
            "expected_entities": ["John Smith", "10 units"],
            "duration_min": 5.0
        },
        "care_coordination_call.wav": {
            "modality": "audio",
            "transcript_contains": ["Doctor Patel", "Lisinopril", "20 milligrams", "blood pressure"],
            "expected_entities": ["Doctor Patel", "Lisinopril"],
            "duration_min": 5.0
        },
        "shift_handoff_summary.wav": {
            "modality": "audio",
            "transcript_contains": ["Three patients", "John Smith", "Sarah Connor", "David Miller"],
            "expected_entities": ["John Smith", "Sarah Connor", "David Miller"],
            "duration_min": 5.0
        },
        "insurance_card_front.png": {
            "modality": "image",
            "expected_metadata": {
                "member_id": "HFP-98765432-01",
                "group_number": "GRP-55443"
            }
        },
        "medication_chart.png": {
            "modality": "image",
            "expected_metadata": {
                "patient": "Sarah Connor",
                "medications": ["Metformin", "Lisinopril", "Atorvastatin"]
            }
        },
        "home_health_visits.csv": {
            "modality": "table",
            "row_count": 500,
            "columns": ["patient_id", "nurse_name", "visit_date", "time_in", "time_out", "service_code", "diagnosis_code", "notes", "billing_amount"]
        },
        "medical_supplies_inventory.csv": {
            "modality": "table",
            "row_count": 200,
            "columns": ["supply_id", "item_name", "category", "quantity", "unit_price", "reorder_level", "supplier", "last_ordered"]
        }
    }
    with open(GT_DIR / "expected_truth.json", "w") as f:
        json.dump(gt_data, f, indent=2)
    print(f"\nGround truth expectations written to {GT_DIR / 'expected_truth.json'}")
    print("\nGeneration process complete. All datasets ready.")

if __name__ == "__main__":
    asyncio.run(main())
