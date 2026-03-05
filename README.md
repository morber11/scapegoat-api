# Scapegoat API
Because we all need someone to blame

Run server:

```bash
cp .env.example .env
pip install -e "[dev]"
uvicorn main:app --reload
```

Run tests:

```bash
pytest
```

Example request:

POST /api/v1/chat

```json
{
    "messages": [
        {
            "role": "user",
            "content": "this is my prompt"
        },
        {
            "role": "assistant",
            "content": "this is my response"
        }
    ]
}
```

only 2 roles are available, ``user`` and ``assistant``
