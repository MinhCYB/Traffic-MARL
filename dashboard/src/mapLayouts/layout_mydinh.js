// layout_mydinh.js — SVG layout cho topology Mỹ Đình (8 ngã tư thực tế)
//
// Layout (SVG coords, W=480 H=420):
//
//   N01 ── N02 ── N03        ← Hồ Tùng Mậu (y=90)
//    |      |      |
//   N04 ── N05 ── N06        ← Hàm Nghi / Phạm Hùng (y=210)
//    |      |
//   N07 ── N08               ← Trần Hữu Dực (y=330)

export const W = 480;
export const H = 420;

export const NODE = {
  N01: { x: 100, y: 90  },
  N02: { x: 240, y: 90  },
  N03: { x: 380, y: 90  },
  N04: { x: 100, y: 210 },
  N05: { x: 240, y: 210 },
  N06: { x: 380, y: 210 },
  N07: { x: 100, y: 330 },
  N08: { x: 240, y: 330 },
};

// mydinh không có SRC node hiển thị ở giữa — chỉ có external boundary
export const SRC = {};

// Edges nội bộ giữa các ngã tư + external boundary connectors
export const EDGES = {
  // ── Hồ Tùng Mậu (ngang trên, arterial) ──
  "SRC_HTM_W_N01_in":  { from: { x: 20,  y: 90  }, to: "N01", type: "arterial" },
  "N01_HTM_W_out":     { from: "N01", to: { x: 20,  y: 90  }, type: "arterial" },
  "N01_N02":           { from: "N01", to: "N02",              type: "arterial" },
  "N02_N01":           { from: "N02", to: "N01",              type: "arterial" },
  "N02_N03":           { from: "N02", to: "N03",              type: "arterial" },
  "N03_N02":           { from: "N03", to: "N02",              type: "arterial" },
  "SRC_HTM_E_N03_in":  { from: { x: 460, y: 90  }, to: "N03", type: "arterial" },
  "N03_HTM_E_out":     { from: "N03", to: { x: 460, y: 90  }, type: "arterial" },

  // ── Lê Đức Thọ (dọc giữa, arterial) ──
  "SRC_LDT_N_N02_in":  { from: { x: 240, y: 20  }, to: "N02", type: "arterial" },
  "N02_LDT_N_out":     { from: "N02", to: { x: 240, y: 20  }, type: "arterial" },
  "N02_N05":           { from: "N02", to: "N05",              type: "arterial" },
  "N05_N02":           { from: "N05", to: "N02",              type: "arterial" },
  "N05_N08":           { from: "N05", to: "N08",              type: "arterial" },
  "N08_N05":           { from: "N08", to: "N05",              type: "arterial" },
  "SRC_LDT_S_N08_in":  { from: { x: 240, y: 400 }, to: "N08", type: "arterial" },
  "N08_LDT_S_out":     { from: "N08", to: { x: 240, y: 400 }, type: "arterial" },

  // ── Phạm Hùng (dọc phải, arterial) ──
  "SRC_PH_N03_in":     { from: { x: 380, y: 20  }, to: "N03", type: "arterial" },
  "N03_PH_out":        { from: "N03", to: { x: 380, y: 20  }, type: "arterial" },
  "N03_N06":           { from: "N03", to: "N06",              type: "arterial" },
  "N06_N03":           { from: "N06", to: "N03",              type: "arterial" },
  "SRC_PH_N06_in":     { from: { x: 460, y: 210 }, to: "N06", type: "arterial" },
  "N06_PH_out":        { from: "N06", to: { x: 460, y: 210 }, type: "arterial" },

  // ── Nguyễn Cơ Thạch (dọc trái, secondary) ──
  "SRC_NCT_N_N01_in":  { from: { x: 100, y: 20  }, to: "N01", type: "secondary" },
  "N01_NCT_N_out":     { from: "N01", to: { x: 100, y: 20  }, type: "secondary" },
  "N01_N04":           { from: "N01", to: "N04",              type: "secondary" },
  "N04_N01":           { from: "N04", to: "N01",              type: "secondary" },
  "N04_N07":           { from: "N04", to: "N07",              type: "secondary" },
  "N07_N04":           { from: "N07", to: "N04",              type: "secondary" },
  "SRC_NCT_S_N07_in":  { from: { x: 20,  y: 330 }, to: "N07", type: "secondary" },
  "N07_NCT_S_out":     { from: "N07", to: { x: 20,  y: 330 }, type: "secondary" },

  // ── Hàm Nghi (ngang giữa, secondary) ──
  "N04_N05":           { from: "N04", to: "N05",              type: "secondary" },
  "N05_N04":           { from: "N05", to: "N04",              type: "secondary" },
  "N05_N06":           { from: "N05", to: "N06",              type: "secondary" },
  "N06_N05":           { from: "N06", to: "N05",              type: "secondary" },

  // ── Trần Hữu Dực (ngang dưới, secondary) ──
  "N07_N08":           { from: "N07", to: "N08",              type: "secondary" },
  "N08_N07":           { from: "N08", to: "N07",              type: "secondary" },

  // ── External boundary còn lại ──
  "EXT_W_N01_in":      { from: { x: 20,  y: 90  }, to: "N01", type: "outskirts" },
  "EXT_W_N04_in":      { from: { x: 20,  y: 210 }, to: "N04", type: "outskirts" },
  "N04_EXT_W_out":     { from: "N04", to: { x: 20,  y: 210 }, type: "outskirts" },
  "EXT_W_N07_in":      { from: { x: 20,  y: 330 }, to: "N07", type: "outskirts" },
  "EXT_S_N07_in":      { from: { x: 100, y: 400 }, to: "N07", type: "outskirts" },
  "N07_EXT_S_out":     { from: "N07", to: { x: 100, y: 400 }, type: "outskirts" },
  "EXT_S_N08_in":      { from: { x: 240, y: 400 }, to: "N08", type: "outskirts" },
  "N08_EXT_S_out":     { from: "N08", to: { x: 240, y: 400 }, type: "outskirts" },
  "EXT_E_N03_in":      { from: { x: 460, y: 90  }, to: "N03", type: "outskirts" },
  "EXT_E_N06_in":      { from: { x: 460, y: 210 }, to: "N06", type: "outskirts" },
  "N06_EXT_E_out":     { from: "N06", to: { x: 460, y: 210 }, type: "outskirts" },
  "EXT_N_N01_in":      { from: { x: 100, y: 20  }, to: "N01", type: "outskirts" },
  "EXT_N_N02_in":      { from: { x: 240, y: 20  }, to: "N02", type: "outskirts" },
  "EXT_N_N03_in":      { from: { x: 380, y: 20  }, to: "N03", type: "outskirts" },
};

// IntersectionGrid layout — 3×3 với N07/N08 chỉ ở 2 cột trái
// render như L-shape: hàng 1 đủ 3, hàng 2 đủ 3, hàng 3 chỉ 2
export const GRID = [
  ["N01", "N02", "N03"],
  ["N04", "N05", "N06"],
  ["N07", "N08", null ],
];

export const NODE_LABELS = {
  N01: "Hồ Tùng Mậu\n+ NCT",
  N02: "HTM\n+ Lê Đức Thọ",
  N03: "HTM\n+ Phạm Hùng",
  N04: "NCT\n+ Hàm Nghi",
  N05: "LDT\n+ Hàm Nghi",
  N06: "Phạm Hùng\n+ Hàm Nghi",
  N07: "NCT\n+ Trần Hữu Dực",
  N08: "LDT\n+ Trần Hữu Dực",
};

// Accident edges mẫu để demo
export const DEMO_ACCIDENT_EDGES = [
  { label: "Hồ Tùng Mậu → N02 (arterial)",  value: "N01_N02" },
  { label: "Lê Đức Thọ → N05 (arterial)",    value: "N02_N05" },
  { label: "Phạm Hùng → N06 (arterial)",     value: "N03_N06" },
  { label: "Hàm Nghi N04 → N05 (secondary)", value: "N04_N05" },
];
