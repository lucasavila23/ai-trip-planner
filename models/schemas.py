from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class TripQuery(BaseModel):
    origin: str
    destination: str
    check_in: date
    check_out: date
    num_people: int
    budget_eur: Optional[float] = None
    confirmed: bool  # True only when user has confirmed all details


class Flight(BaseModel):
    airline: str
    departure_time: str
    arrival_time: str
    duration: str
    price_eur: float
    stops: int


class FlightResults(BaseModel):
    flights: list[Flight]


class Hotel(BaseModel):
    name: str
    price_per_night_eur: float
    total_price_eur: float
    rating: Optional[float] = None
    free_cancellation: bool
    cancellation_deadline: Optional[date] = None


class HotelResults(BaseModel):
    hotels: list[Hotel]


class Activity(BaseModel):
    name: str
    description: str
    price_eur: Optional[float] = None
    duration: Optional[str] = None
    category: Literal["culture", "food", "outdoor", "nightlife", "shopping", "other"]


class ActivityResults(BaseModel):
    activities: list[Activity]


class TripResults(BaseModel):
    query: TripQuery
    flights: list[Flight]
    hotels: list[Hotel]
    activities: list[Activity]
    summary: str = ""
