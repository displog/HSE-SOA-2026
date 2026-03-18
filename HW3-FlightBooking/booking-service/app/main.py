from fastapi import FastAPI

from app.routers import flights, bookings

app = FastAPI(title="Booking Service")

app.include_router(flights.router)
app.include_router(bookings.router)


@app.get("/health")
def health():
    return {"status": "ok"}
