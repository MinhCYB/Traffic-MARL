"""
traffic_env.py — SUMO environment wrapper cho RL

Wrap TraCI API, enforce min_green_time, trả về state/reward/done
theo interface chuẩn để agent dùng.

Flow mỗi step:
    1. Nhận actions từ agent (dict {intersection_id: 0|1})
    2. Enforce min_green_time — override action nếu chưa đủ thời gian
    3. Apply actions → TraCI setPhase / yellow phase
    4. simulationStep() × delta_time
    5. Đọc detector data từ TraCI
    6. Build states, compute rewards
    7. Trả về (states, rewards, done, info)
"""

import os
import sys
import random
from pathlib import Path

import numpy as np
import traci

from env.state_builder import (
    INTERSECTION_IDS,
    INCOMING_EDGES,
    OUTGOING_EDGES,
    NUM_LANES,
    build_all_states,
    build_node_features,
    get_incoming_queues,
    get_outgoing_queues,
)
from env.reward import compute_reward, compute_global_reward

# ── Cấu hình ─────────────────────────────────────────────────────────────────

SIM_ROOT = Path(__file__).parent.parent / "simulation"

def _get_sumo_cfg(topology: str) -> Path:
    return SIM_ROOT / topology / f"{topology}.sumocfg"

def _get_route_files(topology: str) -> dict[str, Path]:
    base = SIM_ROOT / topology / "routes"
    return {
        "peak":    base / "routes_peak.rou.xml",
        "weekend": base / "routes_weekend.rou.xml",
        "night":   base / "routes_night.rou.xml",
    }

ROUTE_WEIGHTS = {"peak": 0.6, "weekend": 0.3, "night": 0.1}

# Phase definitions cho mỗi ngã tư
# 0: NS_green, 1: NS_yellow, 2: EW_green, 3: EW_yellow
YELLOW_PHASE = {0: 1, 2: 3}   # green phase → yellow phase trước khi switch
NEXT_GREEN_PHASE = {1: 2, 3: 0}  # yellow phase → green phase tiếp theo

MIN_GREEN_TIME = 10   # giây — enforce ở env, không phải model
YELLOW_TIME    = 3    # giây — yellow phase cố định
DELTA_TIME     = 5    # giây — agent quyết định mỗi 5s
SIM_END        = 3600 # giây — 1 episode = 1 giờ


class TrafficEnv:
    """
    SUMO traffic environment — hỗ trợ nhiều topology (2x2, 2x3, ...).

    Actions:
        0 → giữ nguyên phase hiện tại
        1 → chuyển sang phase tiếp theo (yellow → next green)

    Observation:
        states: dict {intersection_id: np.ndarray (21,)}
        node_features: np.ndarray (N, 21) — dùng cho GAT

    Reward:
        dict {intersection_id: float} — Max Pressure per agent
    """

    def __init__(
        self,
        port:       int  = 8813,
        topology:   str  = "2x2",
        use_gui:    bool = False,
        seed:       int  = 42,
        delta_time: int  = 5,
    ):
        self.port       = port
        self.topology   = topology
        self.use_gui    = use_gui
        self.seed       = seed
        self.delta_time = delta_time

        # State tracking
        self._step = 0
        self._phase: dict[str, int] = {nid: 0 for nid in INTERSECTION_IDS}
        self._time_since_change: dict[str, float] = {nid: 0.0 for nid in INTERSECTION_IDS}
        self._yellow_countdown: dict[str, int] = {nid: 0 for nid in INTERSECTION_IDS}
        self._in_yellow: dict[str, bool] = {nid: False for nid in INTERSECTION_IDS}
        self._green_time: dict[str, float] = {nid: 0.0 for nid in INTERSECTION_IDS}

        self._connected = False
        self._accident_edges: dict[str, str] = {}  # edge_id -> block_mode

    def reset(self, route_type: str | None = None) -> dict:
        """
        Khởi động / restart SUMO, trả về initial states.

        Args:
            route_type: "peak" | "weekend" | "night" | None (random theo weight)

        Returns:
            {"states": dict, "node_features": np.ndarray}
        """
        if self._connected:
            traci.close()
            self._connected = False

        route_type = route_type or self._sample_route()
        route_files = _get_route_files(self.topology)
        route_file  = str(route_files[route_type])

        sumo_bin = "sumo-gui" if self.use_gui else "sumo"
        sumo_cmd = [
            sumo_bin,
            "-c", str(_get_sumo_cfg(self.topology)),
            "--route-files", route_file,
            "--seed", str(self.seed),
            "--no-step-log", "true",
            "--no-warnings", "true",
            "--time-to-teleport", "300",
        ]

        traci.start(sumo_cmd, port=self.port)
        self._connected = True

        # Reset state tracking
        self._step = 0
        self._phase = {nid: 0 for nid in INTERSECTION_IDS}
        self._time_since_change = {nid: 0.0 for nid in INTERSECTION_IDS}
        self._yellow_countdown = {nid: 0 for nid in INTERSECTION_IDS}
        self._in_yellow = {nid: False for nid in INTERSECTION_IDS}
        self._green_time = {nid: 0.0 for nid in INTERSECTION_IDS}
        self._accident_edges = {}

        # Set initial phase
        for nid in INTERSECTION_IDS:
            traci.trafficlight.setPhase(nid, 0)

        obs = self._get_obs()
        return obs

    def step(self, actions: dict[str, int]) -> tuple[dict, dict, bool, dict]:
        """
        Thực hiện 1 decision step (DELTA_TIME giây).

        Args:
            actions: {intersection_id: 0 (keep) | 1 (switch)}

        Returns:
            obs    : {"states": dict, "node_features": np.ndarray}
            rewards: {intersection_id: float}
            done   : bool
            info   : dict (metrics cho logging)
        """
        # Enforce min_green_time và apply actions
        for nid in INTERSECTION_IDS:
            self._apply_action(nid, actions.get(nid, 0))

        # Advance simulation delta_time steps
        for _ in range(self.delta_time):
            traci.simulationStep()
            self._step += 1
            self._update_timers()

        # Đọc detector data
        queue_data, density_data = self._read_detectors()

        # Build states
        states = build_all_states(
            queue_per_lane=queue_data,
            density_per_lane=density_data,
            current_phases=self._phase,
            time_since_change=self._time_since_change,
        )
        node_features = build_node_features(states)

        # Compute rewards
        rewards = {}
        pressures = {}
        for nid in INTERSECTION_IDS:
            inc = get_incoming_queues(nid, {e: queue_data[nid].get(e, [0.0, 0.0])
                                            for e in INCOMING_EDGES[nid]})
            out = get_outgoing_queues(nid, {e: queue_data[nid].get(e, [0.0, 0.0])
                                            for e in OUTGOING_EDGES[nid]})
            rewards[nid] = compute_reward(inc, out)
            pressures[nid] = -rewards[nid]

        done = self._step >= SIM_END

        info = self._get_info(pressures)

        obs = {"states": states, "node_features": node_features}
        return obs, rewards, done, info

    def close(self):
        if self._connected:
            traci.close()
            self._connected = False

    def inject_accident(self, edge_id: str, block_mode: str = "1"):
        """
        Giả lập tai nạn bằng obstacle vehicle.

        Args:
            edge_id   : edge bị tai nạn (vd: "SRC1_N02")
            block_mode: "1" = block 1 lane, "all" = block tất cả lanes
        """
        try:
            # Tìm route hợp lệ cho obstacle — dùng edge hiện tại
            route_id = f"accident_route_{edge_id}"
            try:
                traci.route.add(route_id, [edge_id])
            except Exception:
                pass  # route đã tồn tại

            lanes = [0] if block_mode == "1" else list(range(NUM_LANES))

            for i, lane_idx in enumerate(lanes):
                veh_id = f"accident_{edge_id}_l{lane_idx}"
                # Xóa nếu đã tồn tại
                if veh_id in traci.vehicle.getIDList():
                    traci.vehicle.remove(veh_id)

                try:
                    traci.vehicle.add(
                        vehID=veh_id,
                        routeID=route_id,
                        typeID="car",
                        departLane=lane_idx,
                        departPos=80.0,
                        departSpeed=0,
                    )
                    traci.vehicle.setSpeed(veh_id, 0)
                    traci.vehicle.setSpeedMode(veh_id, 0)  # không tự tăng tốc
                    traci.vehicle.setLength(veh_id, 8.0)   # xe to hơn bình thường
                    traci.vehicle.setColor(veh_id, (255, 50, 50, 255))  # đỏ
                except Exception:
                    # Fallback: giảm tốc độ lane
                    lane_id = f"{edge_id}_{lane_idx}"
                    try:
                        traci.lane.setMaxSpeed(lane_id, 0.5)
                    except Exception:
                        pass

            self._accident_edges[edge_id] = block_mode
        except Exception as e:
            print(f"[inject_accident] error: {e}")

    def clear_accident(self, edge_id: str):
        """Restore lane sau tai nạn."""
        # Xóa obstacle vehicles
        for vid in list(traci.vehicle.getIDList()):
            if vid.startswith(f"accident_{edge_id}"):
                try:
                    traci.vehicle.remove(vid)
                except Exception:
                    pass
        # Restore lane speed
        for lane_idx in range(NUM_LANES):
            lane_id = f"{edge_id}_{lane_idx}"
            try:
                traci.lane.setMaxSpeed(lane_id, 13.89)
            except Exception:
                pass
        self._accident_edges.pop(edge_id, None)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _apply_action(self, nid: str, action: int):
        """
        Apply action cho một ngã tư, enforce min_green_time.

        Action bị override thành 0 (keep) nếu:
        - Đang trong yellow phase
        - Green time chưa đủ MIN_GREEN_TIME
        """
        if self._in_yellow[nid]:
            return  # đang yellow, không làm gì

        if action == 1:
            if self._green_time[nid] < MIN_GREEN_TIME:
                return  # chưa đủ min green, override → keep
            # Bắt đầu yellow phase
            yellow = YELLOW_PHASE.get(self._phase[nid])
            if yellow is not None:
                traci.trafficlight.setPhase(nid, yellow)
                self._phase[nid] = yellow
                self._in_yellow[nid] = True
                self._yellow_countdown[nid] = YELLOW_TIME
                self._green_time[nid] = 0.0
                self._time_since_change[nid] = 0.0

    def _update_timers(self):
        """Gọi mỗi simulation second — update yellow countdown và green timer."""
        for nid in INTERSECTION_IDS:
            if self._in_yellow[nid]:
                self._yellow_countdown[nid] -= 1
                if self._yellow_countdown[nid] <= 0:
                    # Chuyển sang green tiếp theo
                    next_green = NEXT_GREEN_PHASE.get(self._phase[nid])
                    if next_green is not None:
                        traci.trafficlight.setPhase(nid, next_green)
                        self._phase[nid] = next_green
                    self._in_yellow[nid] = False
                    self._yellow_countdown[nid] = 0
            else:
                self._green_time[nid] += 1.0
                self._time_since_change[nid] += 1.0

    def _read_detectors(self) -> tuple[dict, dict]:
        """
        Đọc queue và density từ tất cả E2 detectors qua TraCI.

        Returns:
            queue_data  : {intersection_id: {edge_id: [lane0, lane1]}}
            density_data: {intersection_id: {edge_id: [lane0, lane1]}}
        """
        queue_data: dict[str, dict[str, list[float]]] = {nid: {} for nid in INTERSECTION_IDS}
        density_data: dict[str, dict[str, list[float]]] = {nid: {} for nid in INTERSECTION_IDS}

        for nid in INTERSECTION_IDS:
            for edge in INCOMING_EDGES[nid]:
                queues = []
                densities = []
                for lane_idx in range(NUM_LANES):
                    det_id = f"e2_{edge}_{lane_idx}"
                    try:
                        q = traci.lanearea.getLastStepHaltingNumber(det_id)
                        d = traci.lanearea.getLastStepOccupancy(det_id) / 100.0
                    except traci.exceptions.TraCIException:
                        q, d = 0.0, 0.0
                    queues.append(float(q))
                    densities.append(float(d))
                queue_data[nid][edge] = queues
                density_data[nid][edge] = densities

        return queue_data, density_data

    def _get_obs(self) -> dict:
        """Đọc obs lần đầu sau reset."""
        queue_data, density_data = self._read_detectors()
        states = build_all_states(
            queue_per_lane=queue_data,
            density_per_lane=density_data,
            current_phases=self._phase,
            time_since_change=self._time_since_change,
        )
        return {"states": states, "node_features": build_node_features(states)}

    def _get_info(self, pressures: dict[str, float]) -> dict:
        """Metrics cho logging — không dùng để train."""
        vehicles = traci.vehicle.getIDList()
        speeds = [traci.vehicle.getSpeed(v) for v in vehicles] if vehicles else [0.0]
        waits  = [traci.vehicle.getWaitingTime(v) for v in vehicles] if vehicles else [0.0]

        return {
            "step": self._step,
            "global_reward": compute_global_reward(pressures),
            "pressures": pressures,
            "avg_speed": float(np.mean(speeds)) * 3.6,
            "avg_waiting_time": float(np.mean(waits)),
            "throughput": traci.simulation.getArrivedNumber(),
            "n_vehicles": len(vehicles),
            "edge_speeds": self._read_edge_speeds(),
            "accident_edges": dict(self._accident_edges),
        }

    def _read_edge_speeds(self) -> dict[str, float]:
        """Tính avg speed (km/h) trên từng edge — dùng cho heatmap."""
        edge_speeds = {}
        try:
            for edge_id in traci.edge.getIDList():
                if edge_id.startswith(":"):  # bỏ internal junction edges
                    continue
                speed = traci.edge.getLastStepMeanSpeed(edge_id) * 3.6  # m/s → km/h
                edge_speeds[edge_id] = round(speed, 1)
        except Exception:
            pass
        return edge_speeds

    @staticmethod
    def _sample_route() -> str:
        r = random.random()
        if r < 0.6:
            return "peak"
        elif r < 0.9:
            return "weekend"
        return "night"