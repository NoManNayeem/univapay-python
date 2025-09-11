#  Project Structure



```bash
univapay-python/
├── univapay/
│   ├── __init__.py
│   ├── client.py           # Core API client
│   ├── auth.py            # JWT authentication
│   ├── models.py          # Data models/schemas
│   ├── exceptions.py      # Custom exceptions
│   ├── webhook.py         # Webhook handling
│   ├── widget.py          # Widget helper utilities
│   └── frameworks/        # Framework-specific integrations
│       ├── __init__.py
│       ├── django.py
│       ├── flask.py
│       └── fastapi.py
├── tests/
├── examples/
├── setup.py
├── ProjectStructure.md
├── README.md
├── requirements.txt
└── .gitignore
```