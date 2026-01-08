# RecruitAI-Core Backend

AI-powered talent acquisition system.

## Development

```bash
# Install dependencies
poetry install

# Run development server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
poetry run pytest
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
