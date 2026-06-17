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

from environment.state_builder import (
    INTERSECTION_IDS,
    INCOMING_EDGES,
    OUTGOING_EDGES,
    NUM_LANES,
    build_all_states,
    build_node_features,
    get_incoming_queues,
    get_outgoing_queues,
)
from environment.maps import get_edge_lanes
from environment.reward import compute_reward, compute_global_reward, REWARD_SCALE
from training.config import SIM_END as _CFG_SIM_END, MIN_GREEN_TIME, YELLOW_TIME, DELTA_TIME as _CFG_DELTA_TIME

# ── Cấu hình ─────────────────────────────────────────────────────────────────

SIM_ROOT = Path(__file__).parent.parent / "simulation"

def _get_sumo_cfg(topology: str) -> Path:
    return SIM_ROOT / topology / f"{topology}.sumocfg"

def _get_route_files(topology: str) -> dict[str, Path]:
    base = SIM_ROOT / topology / "routes"
    return {
        "peak_morning": base / "routes_peak_morning.rou.xml",
        "peak_evening": base / "routes_peak_evening.rou.xml",
        "night":        base / "routes_night.rou.xml",
        # backward compat: fallback neu map chua gen file moi
        "peak":         base / "routes_peak.rou.xml",
    }

# Sampling weight khi train: morning/evening 35% moi loai, dem 30%
# "peak" weight=0 -- chi duoc pick neu la fallback duy nhat con ton tai
ROUTE_WEIGHTS = {"peak_morning": 0.35, "peak_evening": 0.35, "night": 0.30, "peak": 0.0}

# Phase definitions cho mỗi ngã tư
# 0: NS_green, 1: NS_yellow, 2: EW_green, 3: EW_yellow
YELLOW_PHASE = {0: 1, 2: 3}   # green phase → yellow phase trước khi switch
NEXT_GREEN_PHASE = {1: 2, 3: 0}  # yellow phase → green phase tiếp theo

DELTA_TIME     = _CFG_DELTA_TIME  # giây — lấy từ training/config.py (hiện tại: 5)
SIM_END        = _CFG_SIM_END    # giây — lấy từ training/config.py (hiện tại: 1800)


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

        # Callback được worker gán để nhận vehicle + light snapshots mỗi 1s sim-time.
        # Signature: on_substep(phases: dict, time_since_change: dict) -> None
        self.on_substep = None

        # State tracking
        self._step = 0
        self._phase: dict[str, int] = {nid: 0 for nid in INTERSECTION_IDS}
        self._time_since_change: dict[str, float] = {nid: 0.0 for nid in INTERSECTION_IDS}
        self._yellow_countdown: dict[str, int] = {nid: 0 for nid in INTERSECTION_IDS}
        self._in_yellow: dict[str, bool] = {nid: False for nid in INTERSECTION_IDS}
        self._green_time: dict[str, float] = {nid: 0.0 for nid in INTERSECTION_IDS}

        self._connected = False
        self._accident_edges: dict[str, str] = {}  # edge_id -> block_mode
        self._original_lane_speeds: dict[str, float] = {}  # lane_id -> original maxSpeed
        self._tmp_route_file: str | None = None  # temp route file to cleanup

    def reset(self, route_type: str | None = None, volume_scale: float = 1.0) -> dict:
        """
        Khởi động / restart SUMO, trả về initial states.

        Args:
            route_type  : "peak" | "weekend" | "night" | None (random theo weight)
            volume_scale: 0.5 = thưa, 1.0 = bình thường, 1.8 = đông

        Returns:
            {"states": dict, "node_features": np.ndarray}
        """
        if self._connected:
            traci.close()
            self._connected = False

        # Cleanup temp route file từ episode trước
        if self._tmp_route_file:
            try:
                import os
                os.unlink(self._tmp_route_file)
            except OSError:
                pass
            self._tmp_route_file = None

        route_type  = route_type or self._sample_route()
        route_files = _get_route_files(self.topology)

        # Backward compat: dashboard cu gui "peak" -> map sang "peak_morning"
        # neu file routes_peak.rou.xml khong ton tai (da gen routes moi)
        if (route_type == "peak"
                and not route_files["peak"].exists()
                and route_files["peak_morning"].exists()):
            route_type = "peak_morning"

        base_route  = str(route_files[route_type])

        # Scale volume nếu cần
        if volume_scale != 1.0:
            route_file = self._scale_route_file(base_route, volume_scale)
            self._tmp_route_file = route_file  # track để cleanup sau
        else:
            route_file = base_route

        sumo_bin = "sumo-gui" if self.use_gui else "sumo"
        sumo_cmd = [
            sumo_bin,
            "-c", str(_get_sumo_cfg(self.topology)),
            "--route-files", route_file,
            "--seed", str(self.seed),
            "--no-step-log", "true",
            "--no-warnings", "true",
            "--time-to-teleport", "300",
            "--device.rerouting.probability", "1.0",
            "--device.rerouting.period", "10",
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
        self._original_lane_speeds = {}

        # Set initial phase
        for nid in INTERSECTION_IDS:
            traci.trafficlight.setPhase(nid, 0)

        # Subscribe detectors một lần — đọc batch mỗi step
        self._init_detector_subscriptions()

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
        departed_count = 0
        arrived_count  = 0
        teleport_count = 0
        for _ in range(self.delta_time):
            traci.simulationStep()
            self._step += 1
            self._update_timers()
            departed_count += traci.simulation.getDepartedNumber()
            arrived_count  += traci.simulation.getArrivedNumber()
            teleport_count += traci.simulation.getStartingTeleportNumber()
            # Hook để worker stream vehicle + lights mỗi 1s sim-time
            if self.on_substep is not None:
                self.on_substep(self._phase.copy(), self._time_since_change.copy())

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

        # Flatten queue map: {edge_id: [lane0, lane1]} để dùng cho cả incoming lẫn outgoing
        # _read_detectors() chỉ đọc incoming — outgoing của N01 = incoming của neighbor
        # nên cần flat map toàn bộ để get_outgoing_queues tìm được đúng edge
        flat_queue: dict[str, list[float]] = {
            edge: lanes
            for nid in INTERSECTION_IDS
            for edge, lanes in queue_data[nid].items()
        }

        # Tính waiting time trung bình per intersection — dùng cho reward
        # Lấy tất cả xe, sau đó map theo edge → intersection
        wait_per_intersection: dict[str, float] = {nid: 0.0 for nid in INTERSECTION_IDS}
        try:
            all_vehicles = traci.vehicle.getIDList()
            if all_vehicles:
                # Gom waiting time của xe trên incoming edges của từng ngã tư
                inc_wait: dict[str, list[float]] = {nid: [] for nid in INTERSECTION_IDS}
                for vid in all_vehicles:
                    edge_id = traci.vehicle.getRoadID(vid)
                    wait    = traci.vehicle.getWaitingTime(vid)
                    for nid in INTERSECTION_IDS:
                        if edge_id in INCOMING_EDGES[nid]:
                            inc_wait[nid].append(wait)
                            break
                wait_per_intersection = {
                    nid: float(sum(ws) / len(ws)) if ws else 0.0
                    for nid, ws in inc_wait.items()
                }
        except Exception:
            pass  # fallback về 0.0 nếu TraCI lỗi — pressure vẫn active

        # Compute rewards — Hybrid: Waiting Time (70%) + Pressure (30%)
        rewards   = {}
        pressures = {}
        # Phạt teleport: chia đều cho tất cả agents — đây là lỗi chung của cả mạng
        # Mỗi xe bị teleport = penalty 0.5 (half max per-step reward), chia đều cho N agents
        # Cap ở 2.5 (50% base reward range) để tránh dominate khi gridlock tạm thời
        n_agents = len(INTERSECTION_IDS)
        teleport_penalty = min((0.5 * teleport_count) / n_agents * REWARD_SCALE, 2.5)
        for nid in INTERSECTION_IDS:
            inc = get_incoming_queues(nid, flat_queue)
            out = get_outgoing_queues(nid, flat_queue)
            rewards[nid]   = compute_reward(nid, inc, out, wait_per_intersection[nid]) - teleport_penalty
            pressures[nid] = -rewards[nid]

        done = self._step >= SIM_END

        info = self._get_info(pressures, departed_count, arrived_count, teleport_count)

        obs = {"states": states, "node_features": node_features}
        return obs, rewards, done, info

    def close(self):
        if self._connected:
            traci.close()
            self._connected = False
        # Cleanup temp route file
        if self._tmp_route_file:
            try:
                import os
                os.unlink(self._tmp_route_file)
            except OSError:
                pass
            self._tmp_route_file = None

    def inject_accident(self, edge_id: str, block_mode: str = "all"):
        """
        Giả lập tai nạn bằng cách giảm maxSpeed lane xuống gần 0.

        Args:
            edge_id   : edge bị tai nạn (vd: "SRC_HTM_W_N01")
            block_mode: "all"   = block tất cả lanes
                        "left"  = block lane trái (index 0)
                        "right" = block lane phải (index cuối)
        """
        try:
            n_lanes = traci.edge.getLaneNumber(edge_id)
        except Exception:
            n_lanes = NUM_LANES

        if block_mode == "all":
            lane_indices = list(range(n_lanes))
        elif block_mode == "left":
            lane_indices = [0]
        elif block_mode == "right":
            lane_indices = [n_lanes - 1]
        else:
            lane_indices = list(range(n_lanes))  # fallback = all

        # Vehicle classes cần disallow — đủ loại để không xe nào lọt qua
        _ALL_VCLASS = ["passenger", "truck", "bus", "motorcycle", "bicycle",
                       "pedestrian", "emergency", "authority", "army", "vip",
                       "ignoring", "rail", "ship", "custom1", "custom2"]

        for lane_idx in lane_indices:
            lane_id = f"{edge_id}_{lane_idx}"
            try:
                # Cache original maxSpeed trước khi modify
                if lane_id not in self._original_lane_speeds:
                    self._original_lane_speeds[lane_id] = traci.lane.getMaxSpeed(lane_id)
                if block_mode == "all":
                    # Disallow toàn bộ vehicle class → xe không thể vào lane
                    traci.lane.setDisallowed(lane_id, _ALL_VCLASS)
                else:
                    # Partial block: chỉ giảm tốc, xe creep qua hoặc chuyển làn
                    traci.lane.setMaxSpeed(lane_id, 0.3)
            except Exception:
                pass
        self._accident_edges[edge_id] = block_mode

    def clear_accident(self, edge_id: str = None):
        """Restore tất cả lanes về trạng thái bình thường."""
        edges_to_clear = list(self._accident_edges.keys()) if edge_id is None else [edge_id]
        for eid in edges_to_clear:
            block_mode = self._accident_edges.get(eid, "all")
            try:
                n_lanes = traci.edge.getLaneNumber(eid)
            except Exception:
                n_lanes = NUM_LANES
            for lane_idx in range(n_lanes):
                lane_id = f"{eid}_{lane_idx}"
                try:
                    if block_mode == "all":
                        traci.lane.setAllowed(lane_id, [])  # [] = allow all vclass
                    # Restore original maxSpeed (không hardcode 13.89 — residential/minor roads có speed khác)
                    orig_speed = self._original_lane_speeds.pop(lane_id, 13.89)
                    traci.lane.setMaxSpeed(lane_id, orig_speed)
                except Exception:
                    pass
        if edge_id is None:
            self._accident_edges.clear()
        else:
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

    def _init_detector_subscriptions(self):
        """
        Subscribe tất cả E2 detectors một lần sau reset.
        Sau đó getAllSubscriptionResults() là 1 round-trip thay vì N*M calls.
        """
        import traci.constants as tc
        self._det_ids: list[str] = []
        for nid in INTERSECTION_IDS:
            for edge in INCOMING_EDGES[nid]:
                n_lanes = get_edge_lanes(edge)
                for lane_idx in range(n_lanes):
                    det_id = f"e2_{edge}_{lane_idx}"
                    try:
                        traci.lanearea.subscribe(det_id, [
                            tc.LAST_STEP_VEHICLE_HALTING_NUMBER,  # queue
                            tc.LAST_STEP_OCCUPANCY,               # density
                        ])
                        self._det_ids.append(det_id)
                    except Exception:
                        pass

    def _read_detectors(self) -> tuple[dict, dict]:
        """
        Đọc queue và density từ tất cả E2 detectors qua TraCI.

        v2: dùng getAllSubscriptionResults() — 1 round-trip thay vì N*M calls.
        Fallback về per-call nếu subscription chưa init.
        """
        import traci.constants as tc

        queue_data:   dict[str, dict[str, list[float]]] = {nid: {} for nid in INTERSECTION_IDS}
        density_data: dict[str, dict[str, list[float]]] = {nid: {} for nid in INTERSECTION_IDS}

        # Lấy toàn bộ kết quả 1 lần
        try:
            sub_results = traci.lanearea.getAllSubscriptionResults()
        except Exception:
            sub_results = {}

        for nid in INTERSECTION_IDS:
            for edge in INCOMING_EDGES[nid]:
                queues    = []
                densities = []
                n_lanes = get_edge_lanes(edge)
                for lane_idx in range(n_lanes):
                    det_id = f"e2_{edge}_{lane_idx}"
                    vals   = sub_results.get(det_id)
                    if vals:
                        q = float(vals.get(tc.LAST_STEP_VEHICLE_HALTING_NUMBER, 0))
                        d = float(vals.get(tc.LAST_STEP_OCCUPANCY, 0)) / 100.0
                    else:
                        # Fallback per-call nếu subscription miss
                        try:
                            q = float(traci.lanearea.getLastStepHaltingNumber(det_id))
                            d = float(traci.lanearea.getLastStepOccupancy(det_id)) / 100.0
                        except Exception:
                            q, d = 0.0, 0.0
                    queues.append(q)
                    densities.append(d)
                queue_data[nid][edge]   = queues
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

    def _get_info(self, pressures: dict[str, float], departed: int = 0, arrived: int = 0, teleported: int = 0) -> dict:
        """Metrics cho logging — không dùng để train."""
        vehicles = traci.vehicle.getIDList()
        speeds   = [traci.vehicle.getSpeed(v) for v in vehicles] if vehicles else [0.0]
        waits    = [traci.vehicle.getWaitingTime(v) for v in vehicles] if vehicles else [0.0]
        total_wait = sum(waits)

        return {
            "step": self._step,
            "global_reward": compute_global_reward(pressures),
            "pressures": pressures,
            "avg_speed": float(np.mean(speeds)) * 3.6,
            "avg_waiting_time": float(np.mean(waits)),
            "total_waiting_time": round(total_wait, 1),
            "throughput":         arrived,
            "vehicles_spawned":   departed,
            "vehicles_completed": arrived,
            "vehicles_teleported": teleported,   # ← xe bị kẹt quá 300s, bị SUMO xóa
            "n_vehicles": len(vehicles),
            "edge_speeds":     self._read_edge_speeds(),
            "accident_edges":  dict(self._accident_edges),
            "current_phases":  dict(self._phase),
            "time_since_change": dict(self._time_since_change),
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

    def _sample_route(self) -> str:
        """Sample route type theo ROUTE_WEIGHTS, chỉ chọn file đang tồn tại.

        Ưu tiên peak_morning / peak_evening nếu đã gen file mới.
        Fallback về "peak" nếu chỉ có file cũ.
        """
        route_files = _get_route_files(self.topology)
        # Chỉ lấy các key có file tồn tại VÀ weight > 0
        available = [
            k for k, v in route_files.items()
            if v.exists() and ROUTE_WEIGHTS.get(k, 0.0) > 0
        ]
        # Fallback: nếu không có file nào match weight>0, thử "peak" cũ
        if not available:
            available = [k for k, v in route_files.items() if v.exists()]
        if not available:
            raise FileNotFoundError(
                f"Khong tim thay route file nao trong simulation/{self.topology}/routes/. "
                f"Chay: python simulation/{self.topology}/routes/gen_routes.py"
            )
        weights = [ROUTE_WEIGHTS.get(k, 0.1) for k in available]
        total = sum(weights)
        weights = [w / total for w in weights]
        return random.choices(available, weights=weights, k=1)[0]

    @staticmethod
    def _scale_route_file(base_path: str, scale: float) -> str:
        """
        Tạo route file tạm với volume scale.
        Nhân tất cả attribute 'number' trong <flow> tags theo scale.
        Trả về path file tạm.
        """
        import re, tempfile, os
        with open(base_path, "r", encoding="utf-8") as f:
            content = f.read()

        def replace_number(m):
            orig = int(m.group(1))
            scaled = max(1, round(orig * scale))
            return f'number="{scaled}"'

        scaled_content = re.sub(r'number="(\d+)"', replace_number, content)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".rou.xml",
            delete=False, encoding="utf-8",
            prefix="scaled_route_"
        )
        tmp.write(scaled_content)
        tmp.close()
        return tmp.name