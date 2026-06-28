from fastapi import FastAPI


app = FastAPI(title="CoinTwin API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
