// layout_mydinh.js — SVG layout cho topology Mỹ Đình (8 ngã tư thực tế)
//
// Topology thực tế từ SUMO edge IDs:
//
//   N01 ──SRC_HTM_W── N02 ──SRC_HTM_E── N03     ← Hồ Tùng Mậu (y=90)
//    |                 |                  |
//  SRC_NCT_N        SRC_LDT_N          SRC_PH
//    |                 |                  |
//   N04 ──SRC_HN──── N05 ──SRC_NH────  N06     ← Hàm Nghi (y=210)
//    |                 |
//  SRC_NCT_S        SRC_LDT_S
//    |                 |
//   N07 ──SRC_THD── N08                        ← Trần Hữu Dực (y=330)

export const W = 500;
export const H = 430;

// Ngã tư chính
export const NODE = {
  N01: { x: 100, y: 90  },
  N02: { x: 250, y: 90  },
  N03: { x: 400, y: 90  },
  N04: { x: 100, y: 210 },
  N05: { x: 250, y: 210 },
  N06: { x: 400, y: 210 },
  N07: { x: 100, y: 330 },
  N08: { x: 250, y: 330 },
};

// SRC nodes — điểm giữa 2 ngã tư, xe chạy qua đây
export const SRC = {
  // Hồ Tùng Mậu (ngang)
  SRC_HTM_W: { x: 175, y: 90  },   // N01 ↔ N02
  SRC_HTM_E: { x: 325, y: 90  },   // N02 ↔ N03

  // Nguyễn Cơ Thạch (dọc trái)
  SRC_NCT_N: { x: 100, y: 150 },   // N01 ↔ N04
  SRC_NCT_S: { x: 100, y: 270 },   // N04 ↔ N07

  // Lê Đức Thọ (dọc giữa)
  SRC_LDT_N: { x: 250, y: 150 },   // N02 ↔ N05
  SRC_LDT_S: { x: 250, y: 270 },   // N05 ↔ N08

  // Phạm Hùng (dọc phải)
  SRC_PH:    { x: 400, y: 150 },   // N03 ↔ N06

  // Hàm Nghi (ngang giữa)
  SRC_HN:    { x: 175, y: 210 },   // N04 ↔ N05
  SRC_NH:    { x: 325, y: 210 },   // N05 ↔ N06

  // Trần Hữu Dực (ngang dưới)
  SRC_THD:   { x: 175, y: 330 },   // N07 ↔ N08
};

export const EDGES = {
  // ── Hồ Tùng Mậu (arterial, ngang trên) ──────────────────────────────────
  "SRC_HTM_W_N01":  { from: "SRC_HTM_W", to: "N01",        type: "arterial" },
  "N01_SRC_HTM_W":  { from: "N01",        to: "SRC_HTM_W", type: "arterial" },
  "SRC_HTM_W_N02":  { from: "SRC_HTM_W", to: "N02",        type: "arterial" },
  "N02_SRC_HTM_W":  { from: "N02",        to: "SRC_HTM_W", type: "arterial" },
  "SRC_HTM_E_N02":  { from: "SRC_HTM_E", to: "N02",        type: "arterial" },
  "N02_SRC_HTM_E":  { from: "N02",        to: "SRC_HTM_E", type: "arterial" },
  "SRC_HTM_E_N03":  { from: "SRC_HTM_E", to: "N03",        type: "arterial" },
  "N03_SRC_HTM_E":  { from: "N03",        to: "SRC_HTM_E", type: "arterial" },

  // ── Nguyễn Cơ Thạch (secondary, dọc trái) ────────────────────────────────
  "SRC_NCT_N_N01":  { from: "SRC_NCT_N", to: "N01",        type: "secondary" },
  "N01_SRC_NCT_N":  { from: "N01",        to: "SRC_NCT_N", type: "secondary" },
  "SRC_NCT_N_N04":  { from: "SRC_NCT_N", to: "N04",        type: "secondary" },
  "N04_SRC_NCT_N":  { from: "N04",        to: "SRC_NCT_N", type: "secondary" },
  "SRC_NCT_S_N04":  { from: "SRC_NCT_S", to: "N04",        type: "secondary" },
  "N04_SRC_NCT_S":  { from: "N04",        to: "SRC_NCT_S", type: "secondary" },
  "SRC_NCT_S_N07":  { from: "SRC_NCT_S", to: "N07",        type: "secondary" },
  "N07_SRC_NCT_S":  { from: "N07",        to: "SRC_NCT_S", type: "secondary" },

  // ── Lê Đức Thọ (arterial, dọc giữa) ─────────────────────────────────────
  "SRC_LDT_N_N02":  { from: "SRC_LDT_N", to: "N02",        type: "arterial" },
  "N02_SRC_LDT_N":  { from: "N02",        to: "SRC_LDT_N", type: "arterial" },
  "SRC_LDT_N_N05":  { from: "SRC_LDT_N", to: "N05",        type: "arterial" },
  "N05_SRC_LDT_N":  { from: "N05",        to: "SRC_LDT_N", type: "arterial" },
  "SRC_LDT_S_N05":  { from: "SRC_LDT_S", to: "N05",        type: "arterial" },
  "N05_SRC_LDT_S":  { from: "N05",        to: "SRC_LDT_S", type: "arterial" },
  "SRC_LDT_S_N08":  { from: "SRC_LDT_S", to: "N08",        type: "arterial" },
  "N08_SRC_LDT_S":  { from: "N08",        to: "SRC_LDT_S", type: "arterial" },

  // ── Phạm Hùng (arterial, dọc phải) ──────────────────────────────────────
  "SRC_PH_N03":     { from: "SRC_PH",     to: "N03",        type: "arterial" },
  "N03_SRC_PH":     { from: "N03",        to: "SRC_PH",     type: "arterial" },
  "SRC_PH_N06":     { from: "SRC_PH",     to: "N06",        type: "arterial" },
  "N06_SRC_PH":     { from: "N06",        to: "SRC_PH",     type: "arterial" },

  // ── Hàm Nghi (secondary, ngang giữa) ─────────────────────────────────────
  "SRC_HN_N04":     { from: "SRC_HN",     to: "N04",        type: "secondary" },
  "N04_SRC_HN":     { from: "N04",        to: "SRC_HN",     type: "secondary" },
  "SRC_HN_N05":     { from: "SRC_HN",     to: "N05",        type: "secondary" },
  "N05_SRC_HN":     { from: "N05",        to: "SRC_HN",     type: "secondary" },
  "SRC_NH_N05":     { from: "SRC_NH",     to: "N05",        type: "secondary" },
  "N05_SRC_NH":     { from: "N05",        to: "SRC_NH",     type: "secondary" },
  "SRC_NH_N06":     { from: "SRC_NH",     to: "N06",        type: "secondary" },
  "N06_SRC_NH":     { from: "N06",        to: "SRC_NH",     type: "secondary" },

  // ── Trần Hữu Dực (secondary, ngang dưới) ─────────────────────────────────
  "SRC_THD_N07":    { from: "SRC_THD",    to: "N07",        type: "secondary" },
  "N07_SRC_THD":    { from: "N07",        to: "SRC_THD",    type: "secondary" },
  "SRC_THD_N08":    { from: "SRC_THD",    to: "N08",        type: "secondary" },
  "N08_SRC_THD":    { from: "N08",        to: "SRC_THD",    type: "secondary" },

  // ── External boundary (xe vào/ra mạng) ───────────────────────────────────
  "EXT_N_N01_in":   { from: { x: 100, y: 20  }, to: "N01", type: "outskirts" },
  "N01_EXT_N_N01":  { from: "N01", to: { x: 100, y: 20  }, type: "outskirts" },
  "EXT_N_N02_in":   { from: { x: 250, y: 20  }, to: "N02", type: "outskirts" },
  "N02_EXT_N_N02":  { from: "N02", to: { x: 250, y: 20  }, type: "outskirts" },
  "EXT_N_N03_in":   { from: { x: 400, y: 20  }, to: "N03", type: "outskirts" },
  "N03_EXT_N_N03":  { from: "N03", to: { x: 400, y: 20  }, type: "outskirts" },
  "EXT_W_N01_in":   { from: { x: 20,  y: 90  }, to: "N01", type: "outskirts" },
  "N01_EXT_W_N01":  { from: "N01", to: { x: 20,  y: 90  }, type: "outskirts" },
  "EXT_W_N04_in":   { from: { x: 20,  y: 210 }, to: "N04", type: "outskirts" },
  "N04_EXT_W_N04":  { from: "N04", to: { x: 20,  y: 210 }, type: "outskirts" },
  "EXT_W_N07_in":   { from: { x: 20,  y: 330 }, to: "N07", type: "outskirts" },
  "N07_EXT_W_N07":  { from: "N07", to: { x: 20,  y: 330 }, type: "outskirts" },
  "EXT_E_N03_in":   { from: { x: 480, y: 90  }, to: "N03", type: "outskirts" },
  "N03_EXT_E_N03":  { from: "N03", to: { x: 480, y: 90  }, type: "outskirts" },
  "EXT_E_N06_in":   { from: { x: 480, y: 210 }, to: "N06", type: "outskirts" },
  "N06_EXT_E_N06":  { from: "N06", to: { x: 480, y: 210 }, type: "outskirts" },
  "EXT_S_N07_in":   { from: { x: 100, y: 410 }, to: "N07", type: "outskirts" },
  "N07_EXT_S_N07":  { from: "N07", to: { x: 100, y: 410 }, type: "outskirts" },
  "EXT_S_N08_in":   { from: { x: 250, y: 410 }, to: "N08", type: "outskirts" },
  "N08_EXT_S_N08":  { from: "N08", to: { x: 250, y: 410 }, type: "outskirts" },
};

export const GRID = [
  ["N01", "N02", "N03"],
  ["N04", "N05", "N06"],
  ["N07", "N08", null ],
];

export const NODE_LABELS = {
  N01: "HTM + NCT",
  N02: "HTM + LDT",
  N03: "HTM + PH",
  N04: "NCT + HN",
  N05: "LDT + HN",
  N06: "PH + HN",
  N07: "NCT + THD",
  N08: "LDT + THD",
};

// Auto-gen từ EDGES — chỉ internal edges giữa các NODE
const NODE_IDS = Object.keys(NODE);
export const DEMO_ACCIDENT_EDGES = Object.entries(EDGES)
  .filter(([, e]) => {
    const fromIsNode = typeof e.from === "string" && NODE_IDS.includes(e.from);
    const toIsNode   = typeof e.to   === "string" && NODE_IDS.includes(e.to);
    // Chỉ lấy edges đi qua SRC (N → SRC hoặc SRC → N) — đây là road segments thực
    return !fromIsNode || !toIsNode;  // ít nhất 1 đầu là SRC
  })
  .filter(([, e]) => {
    // Bỏ external boundary
    const fromIsCoord = typeof e.from === "object";
    const toIsCoord   = typeof e.to   === "object";
    return !fromIsCoord && !toIsCoord;
  })
  .map(([id, e]) => ({
    label: `${e.from} → ${e.to}`,
    value: id,
  }));