from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import List, Optional
import fitz  # PyMuPDF
from openai import AsyncOpenAI
from fuzzywuzzy import fuzz
from datetime import datetime
import os
import json
import re
import asyncio
from dotenv import load_dotenv
from supabase_client import supabase

load_dotenv()

app = FastAPI()
client = AsyncOpenAI(api_key=os.getenv("OPEN_AI_KEY"))

async def get_allocation_keys():
    """Fetch allocation keys (cost categories) from Supabase"""
    # Fallback to hardcoded if table doesn't exist or error
    try:
        response = supabase.table("cost_categories").select("name, allocation_key").execute()
        if response.data:
            return {item["name"]: item["allocation_key"] for item in response.data}
    except Exception as e:
        print(f"Error fetching cost categories: {e}")
    
    return {
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

async def get_buildings():
    """Fetch buildings from Supabase"""
    try:
        response = supabase.table("buildings").select("id, address").execute()
        if response.data:
            return response.data
    except Exception as e:
        print(f"Error fetching buildings: {e}")
    
    return [
        {"id": 1, "address": "Musterstraße 1, 12345 Berlin"},
        {"id": 2, "address": "Beispielweg 3, 54321 München"},
        {"id": 3, "address": "Schmelzhüttenstr. 39, 07545 Gera"}
    ]

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join(page.get_text() for page in doc)

def match_building(address: str, buildings: List[dict]):
    best, score = None, 0
    for b in buildings:
        s = fuzz.partial_ratio(address, b["address"])
        if s > score:
            best, score = b, s
    return best if score > 50 else None

UNIFIED_INVOICE_SCHEMA = {
    "name": "process_invoice",
    "description": "Determine if the invoice is valid for a whole building and extract data if so.",
    "parameters": {
        "type": "object",
        "properties": {
            "is_whole_building": {"type": "boolean", "description": "Is this for a whole building (True) or a single apartment (False)?"},
            "is_valid": {"type": "boolean", "description": "Is the invoice valid (dates, amounts, relevant for cost allocation)?"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "reason": {"type": "string", "description": "Reasoning for building check and validation status."},
            "indicators_found": {"type": "array", "items": {"type": "string"}, "description": "List of indicators (e.g., 'Wohnungsnummer', 'Gebäudeabrechnung')"},
            "invoice_data": {
                "type": "object",
                "properties": {
                    "invoice_date":   {"type": ["string", "null"], "description": "Datum der Rechnung, DD.MM.YYYY"},
                    "period_start":   {"type": ["string", "null"], "description": "Abrechnungszeitraum von, DD.MM.YYYY"},
                    "period_end":     {"type": ["string", "null"], "description": "Abrechnungszeitraum bis, DD.MM.YYYY"},
                    "total_gross_amount": {"type": ["number", "null"], "description": "Gesamtbruttobetrag der Rechnung in EUR"},
                    "total_net_amount":   {"type": ["number", "null"], "description": "Gesamtnettobetrag der Rechnung in EUR"},
                    "total_vat_amount":   {"type": ["number", "null"], "description": "Gesamtumsatzsteuer in EUR"},
                    "address":        {"type": ["string", "null"], "description": "Rechnungsanschrift oder Versicherungsort"},
                    "recipient":      {"type": ["string", "null"], "description": "Empfänger der Rechnung"},
                    "line_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "cost_category": {
                                    "type": "string",
                                    "enum": ["Grundsteuer", "Kaltwasser", "Entwässerung", "Heizkosten", "Warmwasserversorgung", "Hausmeister", "Sach- & Haftpflichtversicherung", "Müllabfuhr", "Aufzüge", "Straßenreinigung", "Gebäudereinigung", "Gartenpflege", "Beleuchtung", "Schornsteinfeger", "Sonstiges"],
                                    "description": "Art der Kosten"
                                },
                                "gross_amount":   {"type": ["number", "null"]},
                                "net_amount":     {"type": ["number", "null"]},
                                "vat_amount":     {"type": ["number", "null"]}
                            },
                            "required": ["cost_category", "gross_amount", "net_amount", "vat_amount"]
                        }
                    }
                }
            }
        },
        "required": ["is_whole_building", "is_valid", "confidence", "reason"]
    }
}

async def process_invoice_unified(text: str) -> dict:
    prompt = (
        "Du bist ein erfahrener Hausverwalter. Analysiere diese Rechnung.\n\n"
        "1. BUILDING CHECK: Bestimme, ob die Rechnung für das gesamte Gebäude (GÜLTIG) "
        "oder eine einzelne Wohnung/Apartment (UNGÜLTIG) ist.\n"
        "Indikatoren für Wohnung: Wohnungsnummer, Stockwerk (links/rechts), einzelner Mieter.\n"
        "Indikatoren für Gebäude: Hausverwaltung als Empfänger, Gesamtverbrauch, 'Gebäudeabrechnung'.\n\n"
        "2. VALIDATION: Ist die Rechnung für eine Betriebskostenabrechnung gültig? "
        "(Leistungszeitraum, Zahlungsaufforderung, USt-Angaben, laut BetrKV umlagefähig).\n\n"
        "3. EXTRACTION: Wenn gültig, extrahiere alle Details und alle Kostenpositionen.\n\n"
        f"Rechnungstext:\n{text}"
    )

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            tools=[{"type": "function", "function": UNIFIED_INVOICE_SCHEMA}],
            tool_choice={"type": "function", "function": {"name": "process_invoice"}},
            temperature=0
        )
        call = resp.choices[0].message.tool_calls[0]
        return json.loads(call.function.arguments)
    except Exception as e:
        return {
            "is_whole_building": False,
            "is_valid": False,
            "confidence": "low",
            "reason": f"AI Processing Error: {str(e)}"
        }

@app.post("/api/invoices/process/")
async def process_invoices(
    files: List[UploadFile] = File(...),
    authorization: str = Header(None),
):
    results = []
    # Fetch data from Supabase in parallel
    buildings_task = asyncio.create_task(get_buildings())
    allocation_keys_task = asyncio.create_task(get_allocation_keys())
    
    buildings = await buildings_task
    allocation_keys = await allocation_keys_task

    for up in files:
        if not up.filename.lower().endswith(".pdf"):
            results.append({"file": up.filename, "error": "Only PDFs supported."})
            continue

        try:
            raw_pdf = await up.read()
            text = extract_text_from_pdf(raw_pdf)
            
            # Use unified processing
            processed = await process_invoice_unified(text)
            
            if not processed.get("is_whole_building") or not processed.get("is_valid"):
                results.append({
                    "file": up.filename,
                    "validated": False,
                    "reason": processed.get("reason", "Unknown validation error"),
                    "building_check": {
                        "is_whole_building": processed.get("is_whole_building", False),
                        "confidence": processed.get("confidence", "low"),
                        "indicators_found": processed.get("indicators_found", [])
                    },
                    "flag_for_manual_review": True
                })
                continue

            invoice_data = processed.get("invoice_data", {})
            address_from_llm = invoice_data.get("address")
            
            # Fallback for address extraction
            if not address_from_llm:
                match = re.search(r"Versicherungsort[:\s]+(.+)", text, re.IGNORECASE)
                address_from_llm = match.group(1).strip() if match else ""

            building = match_building(address_from_llm, buildings)
            if not building:
                results.append({
                    "file": up.filename,
                    "validated": True,
                    "error": "Address not matched to any building",
                    "flag_for_manual_review": True,
                    "extracted_address": address_from_llm
                })
                continue

            # Process line items
            line_items = invoice_data.get("line_items", [])
            if not line_items:
                # Fallback if no line items were extracted separately
                line_items = [{
                    "cost_category": "Sonstiges",
                    "gross_amount": invoice_data.get("total_gross_amount"),
                    "net_amount": invoice_data.get("total_net_amount"),
                    "vat_amount": invoice_data.get("total_vat_amount"),
                }]

            year = datetime.now().year
            
            for item in line_items:
                category = item.get("cost_category", "Sonstiges")
                item_data = {
                    "file":           up.filename,
                    "validated":      True,
                    "building":       building,
                    "year":           year,
                    "draft_action":   "appended to existing draft",
                    "cost_category":  category,
                    "allocation_key": allocation_key.get(category, "Unknown"),
                    "building_check": {
                        "is_whole_building": True,
                        "confidence": processed.get("confidence"),
                        "indicators_found": processed.get("indicators_found")
                    },
                    "invoice_date":   invoice_data.get("invoice_date"),
                    "period_start":   invoice_data.get("period_start"),
                    "period_end":     invoice_data.get("period_end"),
                    "address":        address_from_llm,
                    "recipient":      invoice_data.get("recipient"),
                    "total_gross_amount": invoice_data.get("total_gross_amount"),
                    "total_net_amount":   invoice_data.get("total_net_amount"),
                    "total_vat_amount":   invoice_data.get("total_vat_amount"),
                    "gross_amount":   item.get("gross_amount"),
                    "net_amount":     item.get("net_amount"),
                    "vat_amount":     item.get("vat_amount"),
                    "validation_reason": processed.get("reason")
                }
                results.append(item_data)

        except Exception as e:
            results.append({
                "file": up.filename,
                "error": "Unexpected error during processing",
                "detail": str(e)
            })

    return JSONResponse({"invoices": results})
