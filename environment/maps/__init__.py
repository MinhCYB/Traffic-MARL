"""
env/maps/__init__.py — Load topology data theo config.TOPOLOGY

Usage:
    from env.maps import INTERSECTION_IDS, INCOMING_EDGES, OUTGOING_EDGES
    from env.maps import ADJACENCY_MATRIX, NUM_LANES, get_edge_lanes
"""

from training.config import TOPOLOGY

if TOPOLOGY == "2x2":
    from environment.maps.map_2x2 import (
        INTERSECTION_IDS,
        INCOMING_EDGES,
        OUTGOING_EDGES,
        ADJACENCY_MATRIX,
        NUM_LANES,
    )
    def get_edge_lanes(edge_id: str) -> int:
        return NUM_LANES

elif TOPOLOGY == "mydinh":
    from environment.maps.map_mydinh import (
        INTERSECTION_IDS,
        INCOMING_EDGES,
        OUTGOING_EDGES,
        ADJACENCY_MATRIX,
        NUM_LANES,
        get_edge_lanes,
    )

else:
    raise ValueError(f"[maps] Unknown topology: '{TOPOLOGY}'. Thêm file map_{TOPOLOGY}.py vào env/maps/")
