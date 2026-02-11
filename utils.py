import PyPDF2

# def extract_text_from_pdf(file) -> str:
#     pdf_reader = PyPDF2.PdfReader(file.file)
#     text = ''
#     for page in pdf_reader.pages:
#         text += page.extract_text() or ''
#     return text

from openai import OpenAI
import os
from fastapi import UploadFile

# Ensure your OpenAI API key is set
client = OpenAI(api_key=os.getenv("OPEN_AI_KEY"))

async def extract_text_from_pdf(file: UploadFile) -> str:
    # Save file to disk synchronously
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as out_file:
        out_file.write(await file.read())

    # Upload to OpenAI
    with open(temp_file_path, "rb") as f:
        upload_response = client.files.create(file=f, purpose="assistants")
        file_id = upload_response.id

    # Call OpenAI API
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all invoice fields."},
                    {"type": "file", "file_id": file_id}
                ]
            }
        ]
    )

    # Optional: remove temp file
    os.remove(temp_file_path)

    return response.choices[0].message.content





def fuzzy_match_address(extracted_text: str, building_list: list) -> str:
    from fuzzywuzzy import process
    best_match, score = process.extractOne(extracted_text, building_list)
    return best_match if score > 80 else None
