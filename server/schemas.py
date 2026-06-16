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
    vehicles_spawned:    int   = 0
    vehicles_completed:  int   = 0
    vehicles_teleported: int   = 0   # xe kẹt quá 300s bị SUMO xóa — indicator chất lượng policy
    global_reward:       float


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
    # timestamp và intersections/metrics là Optional để hỗ trợ
    # event-only payloads (vd: episode_done) không có simulation data.
    timestamp:          Optional[float]              = None
    topology:           str = "2x2"
    intersections:      Optional[list[IntersectionData]] = None
    metrics:            Optional[MetricsData]            = None
    vehicles:           Optional[list[VehicleData]]      = None
    edge_speeds:        Optional[dict[str, float]]        = None
    accident_edges:     Optional[dict[str, str]]          = None
    attention_weights:  Optional[list[list[float]]]       = None
    comm_this_step:     Optional[int]                     = None   # số cặp (i,j) có attn > threshold mỗi step
    event:              Optional[str]                     = None
    phase_duration:     Optional[int]                     = None
    global_reward:      Optional[float]                   = None   # top-level alias (cũng có trong metrics)


class CommandPayload(BaseModel):
    command: str   # "start" | "reset" | "inject_accident:<edge_id>"