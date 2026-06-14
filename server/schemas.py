"""
schemas.py — Pydantic schemas cho FastAPI
"""

from pydantic import BaseModel
from typing import Optional


class IntersectionData(BaseModel):
    id:                 str
    phase:              int
    queue_per_lane:     list[float]
    density_per_lane:   list[float]
    waiting_time:       float
    reward:             float
    time_since_change:  float = 0.0   # giây kể từ lần đổi pha cuối — dùng cho countdown


class MetricsData(BaseModel):
    avg_speed:          float
    avg_waiting_time:   float
    total_waiting_time: float = 0.0
    throughput:         int
    n_vehicles:         int
    vehicles_spawned:   int   = 0
    vehicles_completed: int   = 0
    global_reward:      float


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
    topology:           str = "2x2"          # NEW — map hiện tại đang chạy
    intersections:      list[IntersectionData]
    metrics:            MetricsData
    vehicles:           Optional[list[VehicleData]]    = None
    edge_speeds:        Optional[dict[str, float]]     = None
    accident_edges:     Optional[dict[str, str]]       = None
    attention_weights:  Optional[list[list[float]]]    = None
    event:              Optional[str]                  = None
    phase_duration:     Optional[int]                  = None   # MIN_GREEN + YELLOW_TIME


class CommandPayload(BaseModel):
    command: str   # "start" | "reset" | "inject_accident:<edge_id>"
