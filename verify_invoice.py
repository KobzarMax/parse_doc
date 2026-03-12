import asyncio
import os
import json
from main import extract_text_from_pdf, extract_invoice_data_via_llm, validate_invoice_via_llm, match_building, determine_cost_category, ALLOCATION_KEYS
from dotenv import load_dotenv

load_dotenv()

async def verify_generated_invoice():
    pdf_path = "valid_invoice.pdf"
    
    # User's category JSON
    cost_categories_json = [
        {"id":"06eec641-9e50-46e3-a965-c484e4f4e7f8","type":"fuel_costs","name":"Brennstoffkosten","options":["Gas","Öl","Fernwärme","Pellets","Erdgas (Brennwert)","Erdgas (Heizwert)","Heizöl EL","Flüssiggas (LPG)","Nahwärme (BHKW)","Holzhackschnitzel","Wärmepumpe (Strom)","Stromdirektheizung"],"allocation_key":"m2 Wohnfläche"},
        {"id":"bf43735a-2921-4bc1-a681-948b34bb43d2","type":"operating_current","name":"Betriebsstrom","options":["Strom für Umwälzpumpen","Regeltechnik"],"allocation_key":"Verbrauch"},
        {"id":"17829886-886e-4e45-871b-71c6a7e50cbc","type":"maintenance_costs","name":"Wartungskosten","options":["Regelmäßige Wartung der Heizungsanlage (z. B. Brennerprüfung)","Reinigung"],"allocation_key":"Wohneinheiten"},
        {"id":"f9cdae79-257d-4bc7-88a3-b8b0202c5fda","type":"metering_service_costs","name":"Messdienstkosten","options":["Ablesung","Auswertung","Gerätebereitstellung"],"allocation_key":"m2 Wohnfläche"},
        {"id":"858cf4ad-1725-45d2-a696-05a464ac2f3a","type":"metering_device_rental","name":"Miete der Messgeräte","options":["Heizkostenverteiler","Wärmemengenzähler","Warmwasserzähler","Kaltwasserzähler","Kältezähler"],"allocation_key":"Wohneinheiten"},
        {"id":"96c32bfd-0f54-4a16-adc7-58a382b8f0b8","type":"chimney_sweep_costs","name":"Schornsteinfegerkosten","options":["Kosten für die Emissionsmessung","Nur der auf die Heizung entfallende Teil"],"allocation_key":"Verbrauch"},
        {"id":"924a7bbc-d9e7-437b-960a-f631336b536d","type":"other_operating_costs","name":"Sonstige Betriebskosten","options":["Legionellenprüfung bei Warmwasserbereitung","Kosten für die Reinigung des Heizraums"],"allocation_key":"m2 Wohnfläche"}
    ]

    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print(f"--- Verifying {pdf_path} ---")
    
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # 1. Extract Text
    text = extract_text_from_pdf(pdf_bytes)
    print("\n[1] Extracted Text Snippet:")
    print(text[:500] + "...")
    
    # 2. Extract Data via LLM
    print("\n[2] Extracting Data via LLM...")
    fields = extract_invoice_data_via_llm(text)
    print(json.dumps(fields, indent=2))
    
    # 3. Validate Invoice
    print("\n[3] Validating Invoice...")
    validation = validate_invoice_via_llm(text)
    print(json.dumps(validation, indent=2))
    
    # 4. Match Building
    print("\n[4] Matching Building...")
    address = fields.get("address")
    building = match_building(address or "")
    print(f"Matched Building: {building}")
    
    # 5. Determine Cost Category and Option
    print("\n[5] Determining Cost Category and Option...")
    category, option = determine_cost_category(text, cost_categories_json)
    print(f"Category: {category}")
    print(f"Option: {option}")
    
    print("\n--- Summary ---")
    if validation.get("validated") and building and category != "Sonstiges":
        print("SUCCESS: The invoice passes all checks!")
        if option:
            print(f"Option identified: {option}")
        else:
            print("No specific option identified.")
    else:
        print("FAILURE: The invoice did not pass all checks.")
        if not validation.get("validated"):
            print(f"- Validation failed: {validation.get('reason')}")
        if not building:
            print("- Building matching failed")
        if category == "Sonstiges":
            print("- Cost category determination failed (returned 'Sonstiges')")

if __name__ == "__main__":
    asyncio.run(verify_generated_invoice())
