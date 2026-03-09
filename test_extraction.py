import asyncio
import os
from main import extract_text_from_pdf, process_invoice_unified
import fitz
import json
from dotenv import load_dotenv

load_dotenv()

pdf_path = r"c:\_upwork\heididoc\examples\20251208073308.pdf"

async def test_extraction():
    try:
        if not os.path.exists(pdf_path):
            print(f"Error: PDF not found at {pdf_path}")
            return

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        print(f"Read {len(pdf_bytes)} bytes")
        text = extract_text_from_pdf(pdf_bytes)
        print(f"Extracted text length: {len(text)} characters")

        print("\nTesting process_invoice_unified...")
        data = await process_invoice_unified(text)
        print(f"Result: {json.dumps(data, indent=2)}")

    except Exception as e:
        print(f"General error: {e}")

if __name__ == "__main__":
    asyncio.run(test_extraction())
