# Accessible India Form Assistant

An accessible form assistant that connects a web interface, AI form analysis, Indian-language speech input, answer validation, and SQLite persistence.

## Member Responsibilities

- Member 1: accessible HTML interface and usability controls.
- Member 2: Sarvam Indian-language speech-to-text.
- Member 3: Qwen/OpenRouter form-image analysis and answer understanding.
- Member 4: FastAPI integration, SQLite persistence, API routes, and deployment.

## Main Files

- `index.html`: main website. Upload a form, analyze it, answer fields, confirm answers, and submit.
- `backend.py`: FastAPI traffic controller and SQLite repository.
- `ai/form_analyzer.py`: extracts visible form fields from an image through OpenRouter.
- `ai/question_flow.py`: deterministic answer validation and confirmation logic.
- `sarvam_stt_module/`: Sarvam speech services.
- `render.yaml`: Render deployment configuration.

## Local Setup

Use Python 3.11 or newer.

```powershell
py -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_openrouter_key
SARVAM_API_KEY=your_sarvam_key
```

Start the unified application:

```powershell
py -m uvicorn backend:app --host 127.0.0.1 --port 8001
```

Open the website at:

`http://127.0.0.1:8001`

## User Workflow

1. Click **Upload form photo**.
2. Select a clear PNG, JPG, JPEG, WEBP, or GIF form image.
3. Click **Analyze form**.
4. Fill the extracted fields.
5. Click **Confirm answer** for every field.
6. Click **Submit completed form**.

The confirmed answers are saved in SQLite. The generated database file is ignored by Git.

## API Routes

- `GET /health`: service health check.
- `POST /forms/analyze`: analyze and save a form image.
- `GET /forms/{form_id}`: retrieve a saved form and answers.
- `POST /forms/{form_id}/answers`: validate and save an answer.
- `POST /forms/{form_id}/submit`: save a completed submission.
- `POST /voice/transcribe`: send recorded audio to Sarvam STT.
- `GET /docs`: interactive Swagger API documentation.

## Tests

```powershell
py -m pytest -q test_backend.py
```

## Deploy on Render

1. Open the GitHub repository: https://github.com/160624733299-design/Form-Assistant
2. Create a Render Web Service from the repository.
3. Render reads `render.yaml` for the build and start commands.
4. Add `OPENROUTER_API_KEY` and `SARVAM_API_KEY` as secret environment variables.
5. Deploy and open the public Render URL.

Never commit `.env` or API keys.