from fastapi import FastAPI

app = FastAPI()

# Эндпоинт для корня (то, что выдавало Not Found)
@app.get("/")
def read_root():
    return {"message": "Welcome to Catalog Service"}

# Эндпоинт для проверки здоровья (то, что работает)
@app.get("/health")
def health_check():
    return {"status": "ok"}