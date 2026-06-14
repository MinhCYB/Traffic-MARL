// layout_uet.js — SVG layout cho topology UET (15 ngã tư)
//
// Topology:
//   N01 = N02 = N03 = N04 = N05 = N06   ← Row 1 arterial (y=80)
//    |     |     |     |     |     |
//   N11   N12   N07 — N08 — N09 — N10   ← Row M secondary (y=200) + N11/N12 dọc
//    |     |     |     |     |     |
//   N11 = N12 = N13 = N14 = N15         ← Row 2 arterial (y=320)
//                               N10─N15  ← đường chéo góc Đông

export const W = 660;
export const H = 420;

// ── Ngã tư chính ──────────────────────────────────────────────────────────────
export const NODE = {
  // Row 1
  N01: { x: 80,  y: 80  },
  N02: { x: 190, y: 80  },
  N03: { x: 300, y: 80  },
  N04: { x: 410, y: 80  },
  N05: { x: 520, y: 80  },
  N06: { x: 610, y: 80  },

  // Row M (giữa)
  N07: { x: 300, y: 200 },
  N08: { x: 410, y: 200 },
  N09: { x: 520, y: 200 },
  N10: { x: 610, y: 200 },

  // Row 2
  N11: { x: 80,  y: 320 },
  N12: { x: 190, y: 320 },
  N13: { x: 300, y: 320 },
  N14: { x: 410, y: 320 },
  N15: { x: 520, y: 320 },
};

// ── SRC nodes — điểm giữa 2 ngã tư ──────────────────────────────────────────
export const SRC = {
  // Row 1 ngang
  SRC_R1_AB: { x: 135, y: 80  },  // N01 ↔ N02
  SRC_R1_BC: { x: 245, y: 80  },  // N02 ↔ N03
  SRC_R1_CD: { x: 355, y: 80  },  // N03 ↔ N04
  SRC_R1_DE: { x: 465, y: 80  },  // N04 ↔ N05
  SRC_R1_EF: { x: 565, y: 80  },  // N05 ↔ N06

  // Row 2 ngang
  SRC_R2_AB: { x: 135, y: 320 },  // N11 ↔ N12
  SRC_R2_BC: { x: 245, y: 320 },  // N12 ↔ N13
  SRC_R2_CD: { x: 355, y: 320 },  // N13 ↔ N14
  SRC_R2_DE: { x: 465, y: 320 },  // N14 ↔ N15

  // Row M ngang
  SRC_RM_AB: { x: 355, y: 200 },  // N07 ↔ N08
  SRC_RM_BC: { x: 465, y: 200 },  // N08 ↔ N09
  SRC_RM_CD: { x: 565, y: 200 },  // N09 ↔ N10

  // Dọc arterial
  SRC_V1:    { x: 80,  y: 200 },  // N01 ↔ N11
  SRC_V2:    { x: 190, y: 200 },  // N02 ↔ N12
  SRC_V6:    { x: 610, y: 140 },  // N06 ↔ N10

  // Dọc secondary
  SRC_V3N:   { x: 300, y: 140 },  // N03 ↔ N07
  SRC_V3S:   { x: 300, y: 260 },  // N07 ↔ N13
  SRC_V4N:   { x: 410, y: 140 },  // N04 ↔ N08
  SRC_V4S:   { x: 410, y: 260 },  // N08 ↔ N14
  SRC_V5N:   { x: 520, y: 140 },  // N05 ↔ N09
  SRC_V5S:   { x: 520, y: 260 },  // N09 ↔ N15

  // Đường chéo N10 ↔ N15
  SRC_V10:   { x: 565, y: 260 },  // N10 ↔ N15 (chéo)
};

// ── Edges ─────────────────────────────────────────────────────────────────────
export const EDGES = {
  // ── Row 1 arterial ──────────────────────────────────────────────────────────
  "SRC_R1_AB_N01":  { from: "SRC_R1_AB", to: "N01",       type: "arterial" },
  "N01_SRC_R1_AB":  { from: "N01",       to: "SRC_R1_AB", type: "arterial" },
  "SRC_R1_AB_N02":  { from: "SRC_R1_AB", to: "N02",       type: "arterial" },
  "N02_SRC_R1_AB":  { from: "N02",       to: "SRC_R1_AB", type: "arterial" },

  "SRC_R1_BC_N02":  { from: "SRC_R1_BC", to: "N02",       type: "arterial" },
  "N02_SRC_R1_BC":  { from: "N02",       to: "SRC_R1_BC", type: "arterial" },
  "SRC_R1_BC_N03":  { from: "SRC_R1_BC", to: "N03",       type: "arterial" },
  "N03_SRC_R1_BC":  { from: "N03",       to: "SRC_R1_BC", type: "arterial" },

  "SRC_R1_CD_N03":  { from: "SRC_R1_CD", to: "N03",       type: "arterial" },
  "N03_SRC_R1_CD":  { from: "N03",       to: "SRC_R1_CD", type: "arterial" },
  "SRC_R1_CD_N04":  { from: "SRC_R1_CD", to: "N04",       type: "arterial" },
  "N04_SRC_R1_CD":  { from: "N04",       to: "SRC_R1_CD", type: "arterial" },

  "SRC_R1_DE_N04":  { from: "SRC_R1_DE", to: "N04",       type: "arterial" },
  "N04_SRC_R1_DE":  { from: "N04",       to: "SRC_R1_DE", type: "arterial" },
  "SRC_R1_DE_N05":  { from: "SRC_R1_DE", to: "N05",       type: "arterial" },
  "N05_SRC_R1_DE":  { from: "N05",       to: "SRC_R1_DE", type: "arterial" },

  "SRC_R1_EF_N05":  { from: "SRC_R1_EF", to: "N05",       type: "arterial" },
  "N05_SRC_R1_EF":  { from: "N05",       to: "SRC_R1_EF", type: "arterial" },
  "SRC_R1_EF_N06":  { from: "SRC_R1_EF", to: "N06",       type: "arterial" },
  "N06_SRC_R1_EF":  { from: "N06",       to: "SRC_R1_EF", type: "arterial" },

  // ── Row 2 arterial ──────────────────────────────────────────────────────────
  "SRC_R2_AB_N11":  { from: "SRC_R2_AB", to: "N11",       type: "arterial" },
  "N11_SRC_R2_AB":  { from: "N11",       to: "SRC_R2_AB", type: "arterial" },
  "SRC_R2_AB_N12":  { from: "SRC_R2_AB", to: "N12",       type: "arterial" },
  "N12_SRC_R2_AB":  { from: "N12",       to: "SRC_R2_AB", type: "arterial" },

  "SRC_R2_BC_N12":  { from: "SRC_R2_BC", to: "N12",       type: "arterial" },
  "N12_SRC_R2_BC":  { from: "N12",       to: "SRC_R2_BC", type: "arterial" },
  "SRC_R2_BC_N13":  { from: "SRC_R2_BC", to: "N13",       type: "arterial" },
  "N13_SRC_R2_BC":  { from: "N13",       to: "SRC_R2_BC", type: "arterial" },

  "SRC_R2_CD_N13":  { from: "SRC_R2_CD", to: "N13",       type: "arterial" },
  "N13_SRC_R2_CD":  { from: "N13",       to: "SRC_R2_CD", type: "arterial" },
  "SRC_R2_CD_N14":  { from: "SRC_R2_CD", to: "N14",       type: "arterial" },
  "N14_SRC_R2_CD":  { from: "N14",       to: "SRC_R2_CD", type: "arterial" },

  "SRC_R2_DE_N14":  { from: "SRC_R2_DE", to: "N14",       type: "arterial" },
  "N14_SRC_R2_DE":  { from: "N14",       to: "SRC_R2_DE", type: "arterial" },
  "SRC_R2_DE_N15":  { from: "SRC_R2_DE", to: "N15",       type: "arterial" },
  "N15_SRC_R2_DE":  { from: "N15",       to: "SRC_R2_DE", type: "arterial" },

  // ── Row M secondary (giữa) ──────────────────────────────────────────────────
  "SRC_RM_AB_N07":  { from: "SRC_RM_AB", to: "N07",       type: "secondary" },
  "N07_SRC_RM_AB":  { from: "N07",       to: "SRC_RM_AB", type: "secondary" },
  "SRC_RM_AB_N08":  { from: "SRC_RM_AB", to: "N08",       type: "secondary" },
  "N08_SRC_RM_AB":  { from: "N08",       to: "SRC_RM_AB", type: "secondary" },

  "SRC_RM_BC_N08":  { from: "SRC_RM_BC", to: "N08",       type: "secondary" },
  "N08_SRC_RM_BC":  { from: "N08",       to: "SRC_RM_BC", type: "secondary" },
  "SRC_RM_BC_N09":  { from: "SRC_RM_BC", to: "N09",       type: "secondary" },
  "N09_SRC_RM_BC":  { from: "N09",       to: "SRC_RM_BC", type: "secondary" },

  "SRC_RM_CD_N09":  { from: "SRC_RM_CD", to: "N09",       type: "secondary" },
  "N09_SRC_RM_CD":  { from: "N09",       to: "SRC_RM_CD", type: "secondary" },
  "SRC_RM_CD_N10":  { from: "SRC_RM_CD", to: "N10",       type: "secondary" },
  "N10_SRC_RM_CD":  { from: "N10",       to: "SRC_RM_CD", type: "secondary" },

  // ── Dọc arterial ────────────────────────────────────────────────────────────
  "SRC_V1_N01":     { from: "SRC_V1",    to: "N01",        type: "arterial" },
  "N01_SRC_V1":     { from: "N01",       to: "SRC_V1",     type: "arterial" },
  "SRC_V1_N11":     { from: "SRC_V1",    to: "N11",        type: "arterial" },
  "N11_SRC_V1":     { from: "N11",       to: "SRC_V1",     type: "arterial" },

  "SRC_V2_N02":     { from: "SRC_V2",    to: "N02",        type: "arterial" },
  "N02_SRC_V2":     { from: "N02",       to: "SRC_V2",     type: "arterial" },
  "SRC_V2_N12":     { from: "SRC_V2",    to: "N12",        type: "arterial" },
  "N12_SRC_V2":     { from: "N12",       to: "SRC_V2",     type: "arterial" },

  "SRC_V6_N06":     { from: "SRC_V6",    to: "N06",        type: "arterial" },
  "N06_SRC_V6":     { from: "N06",       to: "SRC_V6",     type: "arterial" },
  "SRC_V6_N10":     { from: "SRC_V6",    to: "N10",        type: "arterial" },
  "N10_SRC_V6":     { from: "N10",       to: "SRC_V6",     type: "arterial" },

  // ── Dọc secondary ───────────────────────────────────────────────────────────
  "SRC_V3N_N03":    { from: "SRC_V3N",   to: "N03",        type: "secondary" },
  "N03_SRC_V3N":    { from: "N03",       to: "SRC_V3N",    type: "secondary" },
  "SRC_V3N_N07":    { from: "SRC_V3N",   to: "N07",        type: "secondary" },
  "N07_SRC_V3N":    { from: "N07",       to: "SRC_V3N",    type: "secondary" },

  "SRC_V3S_N07":    { from: "SRC_V3S",   to: "N07",        type: "secondary" },
  "N07_SRC_V3S":    { from: "N07",       to: "SRC_V3S",    type: "secondary" },
  "SRC_V3S_N13":    { from: "SRC_V3S",   to: "N13",        type: "secondary" },
  "N13_SRC_V3S":    { from: "N13",       to: "SRC_V3S",    type: "secondary" },

  "SRC_V4N_N04":    { from: "SRC_V4N",   to: "N04",        type: "secondary" },
  "N04_SRC_V4N":    { from: "N04",       to: "SRC_V4N",    type: "secondary" },
  "SRC_V4N_N08":    { from: "SRC_V4N",   to: "N08",        type: "secondary" },
  "N08_SRC_V4N":    { from: "N08",       to: "SRC_V4N",    type: "secondary" },

  "SRC_V4S_N08":    { from: "SRC_V4S",   to: "N08",        type: "secondary" },
  "N08_SRC_V4S":    { from: "N08",       to: "SRC_V4S",    type: "secondary" },
  "SRC_V4S_N14":    { from: "SRC_V4S",   to: "N14",        type: "secondary" },
  "N14_SRC_V4S":    { from: "N14",       to: "SRC_V4S",    type: "secondary" },

  "SRC_V5N_N05":    { from: "SRC_V5N",   to: "N05",        type: "secondary" },
  "N05_SRC_V5N":    { from: "N05",       to: "SRC_V5N",    type: "secondary" },
  "SRC_V5N_N09":    { from: "SRC_V5N",   to: "N09",        type: "secondary" },
  "N09_SRC_V5N":    { from: "N09",       to: "SRC_V5N",    type: "secondary" },

  "SRC_V5S_N09":    { from: "SRC_V5S",   to: "N09",        type: "secondary" },
  "N09_SRC_V5S":    { from: "N09",       to: "SRC_V5S",    type: "secondary" },
  "SRC_V5S_N15":    { from: "SRC_V5S",   to: "N15",        type: "secondary" },
  "N15_SRC_V5S":    { from: "N15",       to: "SRC_V5S",    type: "secondary" },

  // ── Đường chéo N10 ↔ N15 ───────────────────────────────────────────────────
  "SRC_V10_N10":    { from: "SRC_V10",   to: "N10",        type: "secondary" },
  "N10_SRC_V10":    { from: "N10",       to: "SRC_V10",    type: "secondary" },
  "SRC_V10_N15":    { from: "SRC_V10",   to: "N15",        type: "secondary" },
  "N15_SRC_V10":    { from: "N15",       to: "SRC_V10",    type: "secondary" },

  // ── External boundary ────────────────────────────────────────────────────────
  // Tây
  "EXT_W_N01_in":   { from: { x: 20,  y: 80  }, to: "N01", type: "outskirts" },
  "N01_EXT_W_N01":  { from: "N01", to: { x: 20,  y: 80  }, type: "outskirts" },
  "EXT_W_N11_in":   { from: { x: 20,  y: 320 }, to: "N11", type: "outskirts" },
  "N11_EXT_W_N11":  { from: "N11", to: { x: 20,  y: 320 }, type: "outskirts" },

  // Đông
  "EXT_E_N06_in":   { from: { x: 645, y: 80  }, to: "N06", type: "outskirts" },
  "N06_EXT_E_N06":  { from: "N06", to: { x: 645, y: 80  }, type: "outskirts" },
  "EXT_E_N10_in":   { from: { x: 645, y: 200 }, to: "N10", type: "outskirts" },
  "N10_EXT_E_N10":  { from: "N10", to: { x: 645, y: 200 }, type: "outskirts" },
  "EXT_E_N15_in":   { from: { x: 555, y: 355 }, to: "N15", type: "outskirts" },
  "N15_EXT_E_N15":  { from: "N15", to: { x: 555, y: 355 }, type: "outskirts" },

  // Bắc
  "EXT_N_N03_in":   { from: { x: 300, y: 20  }, to: "N03", type: "outskirts" },
  "N03_EXT_N_N03":  { from: "N03", to: { x: 300, y: 20  }, type: "outskirts" },
  "EXT_N_N04_in":   { from: { x: 410, y: 20  }, to: "N04", type: "outskirts" },
  "N04_EXT_N_N04":  { from: "N04", to: { x: 410, y: 20  }, type: "outskirts" },
  "EXT_N_N05_in":   { from: { x: 520, y: 20  }, to: "N05", type: "outskirts" },
  "N05_EXT_N_N05":  { from: "N05", to: { x: 520, y: 20  }, type: "outskirts" },
  "EXT_N_N06_in":   { from: { x: 610, y: 20  }, to: "N06", type: "outskirts" },
  "N06_EXT_N_N06":  { from: "N06", to: { x: 610, y: 20  }, type: "outskirts" },

  // Nam
  "EXT_S_N11_in":   { from: { x: 80,  y: 400 }, to: "N11", type: "outskirts" },
  "N11_EXT_S_N11":  { from: "N11", to: { x: 80,  y: 400 }, type: "outskirts" },
  "EXT_S_N13_in":   { from: { x: 300, y: 400 }, to: "N13", type: "outskirts" },
  "N13_EXT_S_N13":  { from: "N13", to: { x: 300, y: 400 }, type: "outskirts" },
  "EXT_S_N14_in":   { from: { x: 410, y: 400 }, to: "N14", type: "outskirts" },
  "N14_EXT_S_N14":  { from: "N14", to: { x: 410, y: 400 }, type: "outskirts" },
  "EXT_S_N15_in":   { from: { x: 520, y: 400 }, to: "N15", type: "outskirts" },
  "N15_EXT_S_N15":  { from: "N15", to: { x: 520, y: 400 }, type: "outskirts" },
};

// GRID — dùng để render IntersectionGrid (row × col, null = ô trống)
export const GRID = [
  ["N01", "N02", "N03",  "N04",  "N05",  "N06" ],
  [null,  null,  "N07",  "N08",  "N09",  "N10" ],
  ["N11", "N12", "N13",  "N14",  "N15",  null  ],
];

export const NODE_LABELS = {
  N01: "Xuân Thủy + Trục Tây",
  N02: "Xuân Thủy + Trục TB",
  N03: "Xuân Thủy + Đ.Nội 1",
  N04: "Xuân Thủy + Đ.Nội 2",
  N05: "Xuân Thủy + Đ.Nội 3",
  N06: "Xuân Thủy + Trục Đông",
  N07: "Nội bộ + Đ.Nội 1",
  N08: "Nội bộ + Đ.Nội 2",
  N09: "Nội bộ + Đ.Nội 3",
  N10: "Nội bộ + Trục Đông",
  N11: "Nguyễn Phong Sắc + Tây",
  N12: "Nguyễn Phong Sắc + TB",
  N13: "Nguyễn Phong Sắc + Đ1",
  N14: "Nguyễn Phong Sắc + Đ2",
  N15: "Nguyễn Phong Sắc + Đ3",
};

// Auto-gen danh sách edges nội bộ (loại EXT và raw-coord) cho accident demo
const NODE_IDS = Object.keys(NODE);
export const DEMO_ACCIDENT_EDGES = Object.entries(EDGES)
  .filter(([, e]) => {
    const fromIsCoord = typeof e.from === "object";
    const toIsCoord   = typeof e.to   === "object";
    return !fromIsCoord && !toIsCoord;
  })
  .filter(([, e]) => {
    const fromIsNode = NODE_IDS.includes(e.from);
    const toIsNode   = NODE_IDS.includes(e.to);
    return !fromIsNode || !toIsNode; // ít nhất 1 đầu là SRC
  })
  .map(([id, e]) => ({
    label: `${e.from} → ${e.to}`,
    value: id,
  }));