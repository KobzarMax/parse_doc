from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import List, Optional
import fitz  # PyMuPDF
from openai import OpenAI
from fuzzywuzzy import fuzz
from datetime import datetime
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPEN_AI_KEY"))

BUILDING_DB = [
    {"id": 1, "address": "Musterstraße 1, 12345 Berlin"},
    {"id": 2, "address": "Beispielweg 3, 54321 München"},
    {"id": 3, "address": "Schmelzhüttenstr. 39, 07545 Gera"}
]

ALLOCATION_KEYS = {
    "Grundsteuer": "Wohnfläche in qm",
    "Kaltwasser": "Verbrauch",
    "Entwässerung": "Wohnfläche in qm",
    "Heizkosten": "Verbrauch",
    "Warmwasserversorgung": "Verbrauch",
    "Hausmeister": "Anzahl Wohneinheiten",
    "Sach- & Haftpflichtversicherung": "Anzahl Wohneinheiten",
    "Müllabfuhr": "Anzahl Wohneinheiten",
    "Aufzüge": "Anzahl Wohneinheiten - Erdgeschoss",
    "Straßenreinigung": "Anzahl Wohneinheiten",
    "Gebäudereinigung": "Wohnfläche in qm",
    "Gartenpflege": "Wohnfläche in qm",
    "Beleuchtung": "Wohnfläche in qm",
    "Schornsteinfeger": "Wohnfläche in qm"
}

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join(page.get_text() for page in doc)

def match_building(address: str):
    best, score = None, 0
    for b in BUILDING_DB:
        s = fuzz.partial_ratio(address, b["address"])
        if s > score:
            best, score = b, s
    return best if score > 50 else None

def determine_cost_category(text: str) -> str:
    categories = list(ALLOCATION_KEYS.keys())
    prompt = (
        f"Analysiere den folgenden Rechnungstext und bestimme, "
        f"welche dieser Kostenarten zutrifft:\n{', '.join(categories)}\n\n{text}"
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    content = resp.choices[0].message.content
    for c in categories:
        if c.lower() in content.lower():
            return c
    return "Sonstiges"

INVOICE_SCHEMA = {
    "name": "extract_invoice_data",
    "description": "Pull out key invoice fields from a German utility-cost invoice.",
    "parameters": {
        "type": "object",
        "properties": {
            "invoice_date":   {"type": ["string", "null"], "description": "Datum der Rechnung, DD.MM.YYYY"},
            "period_start":   {"type": ["string", "null"], "description": "Abrechnungszeitraum von, DD.MM.YYYY"},
            "period_end":     {"type": ["string", "null"], "description": "Abrechnungszeitraum bis, DD.MM.YYYY"},
            "gross_amount":   {"type": ["number", "null"], "description": "Bruttobetrag in EUR"},
            "net_amount":     {"type": ["number", "null"], "description": "Nettobetrag in EUR"},
            "vat_amount":     {"type": ["number", "null"], "description": "Umsatzsteuerbetrag in EUR"},
            "address":        {"type": ["string", "null"], "description": "Rechnungsanschrift oder Versicherungsort"},
            "recipient":      {"type": ["string", "null"], "description": "Empfänger der Rechnung"}
        },
        "required": ["invoice_date","gross_amount","net_amount","vat_amount"]
    }
}

def extract_invoice_data_via_llm(text: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": text}],
        functions=[INVOICE_SCHEMA],
        function_call={"name": "extract_invoice_data"},
        temperature=0
    )
    args = resp.choices[0].message.function_call.arguments
    return json.loads(args)

def check_apartment_vs_building(text: str) -> dict:
    """
    Enhanced check to determine if invoice is for individual apartment vs whole building
    """
    prompt = (
        "Du bist ein erfahrener Hausverwalter. Analysiere die Rechnung und bestimme eindeutig, "
        "ob diese Rechnung für eine einzelne Wohnung/Apartment oder für das gesamte Gebäude/Mehrfamilienhaus ist.\n\n"
        "WICHTIG: Rechnungen für einzelne Wohnungen/Apartments sind NICHT für Betriebskostenabrechnungen geeignet!\n\n"
        "Achte besonders auf folgende Indikatoren:\n\n"
        "FÜR EINZELNE WOHNUNG (UNGÜLTIG):\n"
        "- Wohnungsnummer, Appartmentnummer (z.B. 'Wohnung 3', 'App. 2', 'Whg. Nr. 5')\n"
        "- Stockwerk mit Wohnungsangabe (z.B. '2. OG links', '1. Stock rechts')\n"
        "- Einzelner Mieter als Rechnungsempfänger\n"
        "- Geringe Verbrauchsmengen die für eine Wohnung typisch sind\n"
        "- Zählernummer für einzelne Wohnung\n"
        "- Formulierungen wie 'für Ihre Wohnung', 'Wohnungsabrechnung'\n\n"
        "FÜR GANZES GEBÄUDE (GÜLTIG):\n"
        "- Hausverwaltung oder Eigentümergemeinschaft als Empfänger\n"
        "- Gesamtgebäude-Verbrauch oder -Kosten\n"
        "- Bezeichnungen wie 'Mehrfamilienhaus', 'Gesamtobjekt', 'Haus-Nr.'\n"
        "- Gemeinschaftsflächen, Allgemeinstrom, Hausanschluss\n"
        "- Formulierungen wie 'für das Objekt', 'Gebäudeabrechnung'\n"
        "- Hauswart, Gebäudereinigung, Gartenpflege für gesamtes Objekt\n\n"
        "Gib deine Antwort ausschließlich im JSON-Format zurück:\n"
        "{\n"
        "  \"is_whole_building\": true/false,\n"
        "  \"confidence\": \"high/medium/low\",\n"
        "  \"indicators_found\": [\"Liste der gefundenen Indikatoren\"],\n"
        "  \"reason\": \"Detaillierte Begründung\"\n"
        "}\n\n"
        f"Rechnungstext:\n{text}"
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
    except Exception as e:
        return {
            "is_whole_building": False,
            "confidence": "low",
            "indicators_found": [],
            "reason": f"API call failed: {str(e)}"
        }

    raw = response.choices[0].message.content.strip()
    
    # Clean markdown-style JSON formatting
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
        return {
            "is_whole_building": parsed.get("is_whole_building", False),
            "confidence": parsed.get("confidence", "low"),
            "indicators_found": parsed.get("indicators_found", []),
            "reason": parsed.get("reason", "No reason provided.")
        }
    except Exception as e:
        return {
            "is_whole_building": False,
            "confidence": "low", 
            "indicators_found": [],
            "reason": f"LLM response parse failed: {str(e)} - RAW: {raw}"
        }

def validate_invoice_via_llm(text: str) -> dict:
    """
    Enhanced validation that includes building vs apartment check
    """
    # First check if it's for whole building or individual apartment
    building_check = check_apartment_vs_building(text)
    
    if not building_check["is_whole_building"]:
        return {
            "validated": False,
            "reason": f"Rechnung ist für eine einzelne Wohnung/Apartment, nicht für das gesamte Gebäude. {building_check['reason']}",
            "building_check": building_check
        }
    
    # If it passes the building check, proceed with standard validation
    prompt = (
        "Du bist ein erfahrener Hausverwalter. Beurteile, ob eine Rechnung gemäß der Anforderungen für Betriebskostenabrechnung gültig ist. "
        "Diese Rechnung wurde bereits als 'für gesamtes Gebäude' eingestuft.\n\n"
        "Gib deine Antwort ausschließlich im JSON-Format wie folgt zurück:\n\n"
        "{\n"
        "  \"is_valid\": true/false,\n"
        "  \"reason\": \"...\"\n"
        "}\n\n"
        "Kriterien für eine gültige Rechnung:\n"
        "- Enthält Abrechnungszeitraum oder Leistungszeitraum\n"
        "- Enthält Zahlungsaufforderung oder Zahlungsziel\n"
        "- Zeigt Nettobetrag, Bruttobetrag und Umsatzsteuer oder erklärt, warum sie nicht enthalten sind (z.B. bei öffentlichen Gebührenbescheiden)\n"
        "- Ist zur Umlage auf Mieter geeignet laut BetrKV\n"
        "- Enthält alle relevanten Informationen einer Rechnung laut § 14 UStG\n\n"
        "Wichtiger Hinweis: Gebührenbescheide von öffentlichen Einrichtungen (z.B. Müllabfuhr, Wasserverbände) sind auch gültig, "
        "selbst wenn sie keine Umsatzsteuer ausweisen, sofern alle anderen Kriterien erfüllt sind.\n\n"
        f"Rechnungstext:\n{text}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
    except Exception as e:
        return {
            "validated": False, 
            "reason": f"API call failed: {str(e)}",
            "building_check": building_check
        }

    raw = response.choices[0].message.content.strip()

    # Clean markdown-style JSON formatting
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
        return {
            "validated": parsed.get("is_valid", False),
            "reason": parsed.get("reason", "No reason provided."),
            "building_check": building_check
        }
    except Exception as e:
        return {
            "validated": False,
            "reason": f"LLM response parse failed: {str(e)} - RAW: {raw}",
            "building_check": building_check
        }

@app.post("/api/invoices/process/")
async def process_invoices(
    files: List[UploadFile] = File(...),
    authorization: str = Header(None),
):
    results = []
    for up in files:
        if not up.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "Only PDFs supported.")

        raw = await up.read()
        text = extract_text_from_pdf(raw)
        print(text)

        try:
            fields = extract_invoice_data_via_llm(text)
        except Exception as e:
            results.append({
                "file": up.filename,
                "error": "LLM parsing failed",
                "detail": str(e)
            })
            continue

        validation = validate_invoice_via_llm(text)
        if not validation["validated"]:
            results.append({
                "file": up.filename,
                "validated": False,
                "reason": validation["reason"],
                "building_check": validation.get("building_check", {}),
                "flag_for_manual_review": True
            })
            continue

        address_from_llm = fields.get("address")
        if not address_from_llm:
            match = re.search(r"Versicherungsort[:\s]+(.+)", text, re.IGNORECASE)
            address_from_llm = match.group(1).strip() if match else None

        building = match_building(address_from_llm or "")
        if not building:
            results.append({
                "file": up.filename,
                "validated": True,
                "error": "Address not matched",
                "flag_for_manual_review": True
            })
            continue

        category = determine_cost_category(text)
        allocation_key = ALLOCATION_KEYS.get(category, "Unknown")
        year = datetime.now().year
        action = "appended to existing draft"

        results.append({
            "file":           up.filename,
            "validated":      True,
            "building":       building,
            "year":           year,
            "draft_action":   action,
            "cost_category":  category,
            "allocation_key": allocation_key,
            "building_check": validation.get("building_check", {}),
            **fields,
            "validation_reason": validation["reason"]
        })

    return JSONResponse({"invoices": results})