from pydantic import BaseModel


class CreateBookingRequest(BaseModel):
    user_id: str
    flight_id: str
    passenger_name: str
    passenger_email: str
    seat_count: int


class BookingResponse(BaseModel):
    id: str
    user_id: str
    flight_id: str
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: float
    status: str

    class Config:
        from_attributes = True


class FlightResponse(BaseModel):
    id: str
    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    total_seats: int
    available_seats: int
    price: float
    status: str
