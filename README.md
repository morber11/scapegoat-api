# Scapegoat API
Because we all need someone to blame

Web: [morber11/scapegoat-web](https://github.com/morber11/scapegoat-web)

Run server:

Note: needs to be run from /src directory
You will need to copy .env to /src as well

```bash
cp .env.example .env
pip install -e '.[dev]'
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
