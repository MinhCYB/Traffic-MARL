"""
schemas.py — Pydantic schemas cho FastAPI
"""

from pydantic import BaseModel
from typing import Optional


class IntersectionData(BaseModel):
    id:               str
    phase:            int
    queue_per_lane:   list[float]
    density_per_lane: list[float]
    waiting_time:     float
    reward:           float


class MetricsData(BaseModel):
    avg_speed:        float
    avg_waiting_time: float
    throughput:       int
    n_vehicles:       int
    global_reward:    float


class VehicleData(BaseModel):
    id:    str
    edge:  str
    lane:  int
    pos:   float
    speed: float
    type:  str
    angle: float


class WorkerPayload(BaseModel):
    mode:               str
    step:               int
    timestamp:          float
    intersections:      list[IntersectionData]
    metrics:            MetricsData
    vehicles:           Optional[list[VehicleData]] = None
    attention_weights:  Optional[list[list[float]]] = None
    event:              Optional[str] = None


class CommandPayload(BaseModel):
    command: str   # "start" | "reset" | "inject_accident:<edge_id>"