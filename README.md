# Invoice Processing API

A FastAPI application for processing building invoices using AI and optional user-defined cost categories.

## Deployment to Vercel

### Prerequisites

- Vercel account
- Supabase project with required tables

### Environment Variables

Set these in your Vercel project settings:

- `OPEN_AI_KEY`: Your OpenAI API key

### Deployment Steps

1. **Push your code to GitHub**

   ```bash
   git add .
   git commit -m "Prepare for Vercel deployment"
   git push origin main
   ```

2. **Deploy on Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Import your GitHub repository
   - Vercel will automatically detect the `vercel.json` configuration
   - Set the environment variables in the Vercel dashboard

3. **API Endpoints**
   - `POST /api/invoices/process/` - Process invoice PDFs. Accepts multipart/form-data with:
     - `files` (PDFs)
     - optional `costCategories` JSON string containing an array of user-defined cost category objects
     - optional `apartments` JSON string with array of apartment objects (frontend can supply list of units to help when invoice is for individual apartment)
   - `GET /api/health` - Health check

### Local Development

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env` file

3. Run locally:
   ```bash
   uvicorn main:app --reload
   ```

## API Usage

### Process Invoices

```bash
curl -X POST "https://your-app.vercel.app/api/invoices/process/" \
  -F "files=@invoice.pdf" \
  -F 'costCategories=[{"name":"Grundsteuer","allocation_key":"Wohnfläche in qm"}]'
```

The API expects PDF files and optionally a costCategories array; it returns structured invoice data with validation results.
