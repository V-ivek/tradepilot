from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="tradepilot-gateway", version="0.1.0")
    return app


app = create_app()
