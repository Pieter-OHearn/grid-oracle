from fastapi import FastAPI
from api.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="GridOracle API", version="0.1.0")


@app.get("/health")
def health_check():
    return {"status": "ok"}
