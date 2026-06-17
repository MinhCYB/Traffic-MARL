"""
worker_base.py — Base worker class

Mỗi worker chạy trong 1 process riêng:
    - Khởi động SUMO trên port riêng
    - Chạy agent inference
    - POST JSON lên server mỗi DELTA_TIME giây
    - Nhận lệnh từ server qua polling (start/inject_accident/reset)
"""

import time
import json
import requests
import numpy as np
from abc import ABC, abstractmethod

from training.config import (
    SERVER_HOST, SERVER_PORT, DELTA_TIME, SEED, TOPOLOGY,
    MIN_GREEN_TIME, YELLOW_TIME,
)
from environment.traffic_env import TrafficEnv
from environment.state_builder import INTERSECTION_IDS, EDGE_INDEX, MAX_LANES_TOTAL

import os, sys

class _SuppressTraCIWarnings:
    """Filter '0xd4' unsubscribe warnings khỏi stderr."""
    def __init__(self, stream): self._stream = stream
    def write(self, msg):
        if "0xd4" not in msg and "subscription to remove" not in msg:
            self._stream.write(msg)
    def flush(self): self._stream.flush()

sys.stderr = _SuppressTraCIWarnings(sys.stderr)


class WorkerBase(ABC):
    """
    Abstract base worker.

    Subclass override:
        - model_name: str
        - build_agent(): trả về agent đã load checkpoint
        - get_extra_payload(): dict bổ sung vào JSON (vd: attention_weights)
    """

    model_name: str = "base"

    def __init__(self, port: int, use_gui: bool = False):
        self.port    = port
        self.env     = TrafficEnv(port=port, topology=TOPOLOGY, use_gui=use_gui, seed=SEED)
        self.agent   = self.build_agent()
        self.base_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
        self._running = False
        self._step    = 0
        # Cache cho batch vehicle subscription (tối ưu TraCI round-trips)
        self._subscribed_vehicles: set[str] = set()
        self._lane_length_cache:   dict[str, float] = {}

        # Đăng ký substep callback để stream vehicles + lights mỗi 1s sim-time
        self.env.on_substep = self._on_substep
        # Thread pool 1 worker — đảm bảo POST không block simulation loop
        from concurrent.futures import ThreadPoolExecutor
        self._stream_executor = ThreadPoolExecutor(max_workers=1)
        self._stream_pending  = False   # throttle: bỏ qua nếu POST trước chưa xong

    def _on_substep(self, phases: dict, time_since_change: dict):
        """
        Được gọi sau mỗi traci.simulationStep() (1s sim-time).
        Stream vehicle positions + traffic light state lên /stream endpoint.
        POST chạy trên thread riêng — không block simulation loop.
        """
        if self._stream_pending:
            return  # POST trước chưa xong → bỏ qua frame này, không block

        vehicles = self._read_vehicles()
        intersections = [
            {
                "id":    nid,
                "phase": int(phases.get(nid, 0)),
                "time_since_change": round(float(time_since_change.get(nid, 0)), 1),
            }
            for nid in phases
        ]
        payload = {
            "mode":          self.model_name,
            "vehicles":      vehicles,
            "intersections": intersections,
        }
        self._stream_pending = True
        self._stream_executor.submit(self._post_stream_sync, payload)

    def _post_stream_sync(self, payload: dict):
        """Chạy trên background thread — POST rồi clear flag."""
        try:
            requests.post(
                f"{self.base_url}/stream",
                json=payload,
                timeout=0.8,
            )
        except requests.exceptions.RequestException:
            pass
        finally:
            self._stream_pending = False

    # ── Abstract ──────────────────────────────────────────────────────────────

    @abstractmethod
    def build_agent(self):
        """Khởi tạo và load agent. Trả về agent đã set_eval()."""
        raise NotImplementedError

    def get_extra_payload(self) -> dict:
        """
        Data bổ sung vào JSON payload — override trong subclass.
        Vd: GATWorker trả về attention_weights.
        """
        return {}

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        """Main loop — chạy đến khi nhận lệnh stop."""
        print(f"[{self.model_name}] Worker started, port={self.port}")
        route_type, volume = self._wait_for_start()

        while True:
            try:
                obs  = self.env.reset(route_type=route_type, volume_scale=volume)
                done = False
                self._step = 0
                # Reset subscription caches mỗi episode (xe mới hoàn toàn)
                self._subscribed_vehicles = set()
                self._lane_length_cache   = {}

                while not done:
                    actions = self.agent.select_actions(obs)
                    next_obs, rewards, done, info = self.env.step(actions)
                    self._step += 1

                    payload = self._build_payload(next_obs, rewards, info)
                    self._post(payload)

                    cmd = self._poll_command()
                    if cmd and cmd.startswith("reset"):
                        break
                    elif cmd and cmd.startswith("start"):
                        # Restart với config mới
                        parts      = cmd.split(":")
                        route_type = parts[1] if len(parts) > 1 else None
                        volume     = float(parts[2]) if len(parts) > 2 else 1.0
                        break
                    elif cmd and cmd.startswith("inject_accident"):
                        parts      = cmd.split(":")
                        edge_id    = parts[1] if len(parts) > 1 else "SRC1_N02"
                        block_mode = parts[2] if len(parts) > 2 else "all"
                        self.env.inject_accident(edge_id, block_mode)
                    elif cmd and cmd == "clear_accident":
                        self.env.clear_accident()

                    obs = next_obs

                self._post({"mode": self.model_name, "event": "episode_done", "step": self._step})

            except Exception as e:
                print(f"[{self.model_name}] Error: {e} — restarting...")
                try:
                    self.env.close()
                except Exception:
                    pass
                import time
                time.sleep(2)

            route_type, volume = self._wait_for_start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_payload(self, obs: dict, rewards: dict, info: dict) -> dict:
        """Xây dựng JSON payload theo schema."""
        states = obs["states"]

        intersections = []
        for nid in INTERSECTION_IDS:
            s = states[nid]
            # State layout: density(MAX_LANES_TOTAL) + queue(MAX_LANES_TOTAL) + phase(4) + time(1)
            queue_per_lane   = s[MAX_LANES_TOTAL : 2 * MAX_LANES_TOTAL].tolist()
            density_per_lane = s[0 : MAX_LANES_TOTAL].tolist()

            # Lấy phase thực tế từ env (bao gồm cả yellow=1,3) thay vì argmax state vector
            current_phases = info.get("current_phases", {})
            current_phase  = int(current_phases.get(nid, 0))

            tsc = info.get("time_since_change", {})
            intersections.append({
                "id":                nid,
                "phase":             current_phase,
                "queue_per_lane":    queue_per_lane,
                "density_per_lane":  density_per_lane,
                "waiting_time":      round(float(info.get("waiting_times_per_node", {}).get(nid, 0)), 2),
                "reward":            round(float(rewards.get(nid, 0)), 4),
                "time_since_change": round(float(tsc.get(nid, 0)), 1),
            })

        payload = {
            "mode":           self.model_name,
            "step":           self._step,
            "timestamp":      time.time(),
            "topology":       TOPOLOGY,
            "intersections":  intersections,
            "vehicles":       self._read_vehicles(),
            "edge_speeds":    info.get("edge_speeds", {}),
            "accident_edges": info.get("accident_edges", {}),
            "metrics": {
                "avg_speed":          round(info.get("avg_speed", 0), 2),
                "avg_waiting_time":   round(info.get("avg_waiting_time", 0), 2),
                "total_waiting_time": round(info.get("total_waiting_time", 0), 1),
                "throughput":         info.get("throughput", 0),
                "n_vehicles":         info.get("n_vehicles", 0),
                "vehicles_spawned":   info.get("vehicles_spawned", 0),
                "vehicles_completed": info.get("vehicles_completed", 0),
                "vehicles_teleported": info.get("vehicles_teleported", 0),
                "global_reward":      round(info.get("global_reward", 0), 4),
            },
            "global_reward":    round(info.get("global_reward", 0), 4),
            "phase_duration":   MIN_GREEN_TIME + YELLOW_TIME,
        }

        # Merge extra data từ subclass (vd: attention weights)
        payload.update(self.get_extra_payload())
        return payload

    def _read_vehicles(self) -> list[dict]:
        """
        Đọc vị trí, tốc độ, loại xe từ TraCI dùng batch context subscription.

        Tối ưu so với v1: thay vì gọi N TraCI calls riêng lẻ mỗi xe,
        dùng traci.vehicle.getAllContextSubscriptionResults() (1 round-trip).
        Subscribe khi xe mới xuất hiện, unsubscribe khi xe rời mạng.
        """
        try:
            import traci
            import traci.constants as tc

            # Subscribe xe mới — chỉ tốn kém lần đầu xe vào mạng
            current_ids = set(traci.vehicle.getIDList())
            new_ids     = current_ids - self._subscribed_vehicles
            gone_ids    = self._subscribed_vehicles - current_ids

            _VARS = (
                tc.VAR_ROAD_ID,       # edge
                tc.VAR_LANE_INDEX,    # lane index
                tc.VAR_LANEPOSITION,  # position along lane
                tc.VAR_SPEED,         # m/s
                tc.VAR_TYPE,          # type id
                tc.VAR_ANGLE,         # heading
            )

            for vid in new_ids:
                traci.vehicle.subscribe(vid, _VARS)
            for vid in gone_ids:
                try:
                    traci.vehicle.unsubscribe(vid)
                except Exception:
                    pass

            self._subscribed_vehicles = current_ids

            # Một lần lấy toàn bộ kết quả subscription
            sub_results = traci.vehicle.getAllSubscriptionResults()

            vehicles = []
            for vid, vals in sub_results.items():
                try:
                    edge_id  = vals.get(tc.VAR_ROAD_ID, "")
                    lane_idx = vals.get(tc.VAR_LANE_INDEX, 0)
                    lane_pos = vals.get(tc.VAR_LANEPOSITION, 0.0)
                    speed    = vals.get(tc.VAR_SPEED, 0.0)
                    vtype    = vals.get(tc.VAR_TYPE, "")
                    angle    = vals.get(tc.VAR_ANGLE, 0.0)

                    # Lane length từ cache
                    lane_key = f"{edge_id}_{lane_idx}"
                    if lane_key not in self._lane_length_cache:
                        try:
                            self._lane_length_cache[lane_key] = traci.lane.getLength(lane_key)
                        except Exception:
                            self._lane_length_cache[lane_key] = 0.0
                    lane_len = self._lane_length_cache[lane_key]
                    pos_norm = round(lane_pos / lane_len, 3) if lane_len > 0 else 0.0

                    vehicles.append({
                        "id":    vid,
                        "edge":  edge_id,
                        "lane":  lane_idx,
                        "pos":   pos_norm,
                        "speed": round(speed * 3.6, 1),
                        "type":  vtype,
                        "angle": round(angle, 1),
                    })
                except Exception:
                    continue
            return vehicles
        except Exception:
            return []

    def _post(self, payload: dict):
        """POST JSON lên server, bỏ qua nếu server chưa sẵn sàng."""
        try:
            r = requests.post(
                f"{self.base_url}/data",
                json=payload,
                timeout=1.0,
            )
            if r.status_code != 200:
                print(f"[{self.model_name}] POST /data failed: {r.status_code} {r.text[:200]}")
        except requests.exceptions.RequestException as e:
            print(f"[{self.model_name}] POST /data error: {e}")

    def _poll_command(self) -> str | None:
        """GET lệnh từ server command channel."""
        try:
            resp = requests.get(
                f"{self.base_url}/command/{self.model_name}",
                timeout=0.5,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("command")
        except requests.exceptions.RequestException:
            pass
        return None

    def _wait_for_start(self) -> tuple[str | None, float]:
        """Block cho đến khi nhận lệnh start. Trả về (route_type, volume_scale)."""
        print(f"[{self.model_name}] Waiting for start command...")
        while True:
            cmd = self._poll_command()
            if cmd and cmd.startswith("start"):
                parts      = cmd.split(":")
                route_type = parts[1] if len(parts) > 1 and parts[1] else None
                volume     = float(parts[2]) if len(parts) > 2 else 1.0
                print(f"[{self.model_name}] Start received — route={route_type}, volume={volume}x")
                return route_type, volume
            time.sleep(0.5)

    def close(self):
        self.env.close()