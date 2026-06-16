# test_checkpoint.py
import torch
import numpy as np
import importlib.util, pathlib

# Load map_mydinh.py trực tiếp — bypass hoàn toàn __init__.py và config
spec = importlib.util.spec_from_file_location(
    "map_mydinh",
    pathlib.Path(__file__).parent / "environment/maps/map_mydinh.py"
)
map_mydinh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(map_mydinh)

INTERSECTION_IDS = map_mydinh.INTERSECTION_IDS
INCOMING_EDGES   = map_mydinh.INCOMING_EDGES
ADJACENCY_MATRIX = map_mydinh.ADJACENCY_MATRIX
get_edge_lanes   = map_mydinh.get_edge_lanes

MAX_LANES_TOTAL = max(
    sum(get_edge_lanes(e) for e in edges)
    for edges in INCOMING_EDGES.values()
)
STATE_DIM = MAX_LANES_TOTAL * 2 + 4 + 1
_src, _dst = np.where(ADJACENCY_MATRIX == 1)
EDGE_INDEX = np.stack([_src, _dst], axis=0).astype(np.int64)

print(f"STATE_DIM={STATE_DIM}, nodes={len(INTERSECTION_IDS)}, edges={EDGE_INDEX.shape[1]}")

# Load model
spec2 = importlib.util.spec_from_file_location(
    "gat_marl",
    pathlib.Path(__file__).parent / "models/gat_marl.py"
)
gat_marl = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(gat_marl)
GATMARLNet = gat_marl.GATMARLNet

net = GATMARLNet(state_dim=STATE_DIM, hidden_dim=64, num_heads=4, num_actions=2)
ckpt = torch.load("checkpoints/final/gat_marl_mydinh_best.pt", map_location="cpu", weights_only=True)
net.load_state_dict(ckpt["online_net"])
net.eval()

edge_index = torch.tensor(EDGE_INDEX, dtype=torch.long)

scenarios = {
    "all_heavy": np.random.uniform(0.7, 1.0, (8, STATE_DIM)).astype(np.float32),
    "all_light":  np.zeros((8, STATE_DIM), dtype=np.float32),
    "mixed": np.array([
        np.random.uniform(0.8, 1.0, STATE_DIM) if i % 2 == 0
        else np.zeros(STATE_DIM)
        for i in range(8)
    ], dtype=np.float32),
}

for name, features in scenarios.items():
    x = torch.tensor(features)
    with torch.no_grad():
        q = net(x, edge_index)
    actions = q.argmax(dim=-1).numpy()
    print(f"\n[{name}]")
    print(f"  actions : { {nid: int(a) for nid, a in zip(INTERSECTION_IDS, actions)} }")
    print(f"  Q-values:\n{q.numpy().round(3)}")
    