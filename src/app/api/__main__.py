"""`python -m app.api`: sobe a API local (127.0.0.1:8000) com a configuração do ambiente."""

import uvicorn

from app.api.main import criar_app

if __name__ == "__main__":
    uvicorn.run(criar_app(), host="127.0.0.1", port=8000)
