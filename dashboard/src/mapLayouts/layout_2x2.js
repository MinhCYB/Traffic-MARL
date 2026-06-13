// layout_2x2.js — SVG layout cho topology 2×2 (4 ngã tư synthetic)
//
// Layout:
//   N01 ── N02
//    |      |
//   N03 ── N04

export const W = 360;
export const H = 320;

export const NODE = {
  N01: { x: 110, y: 100 },
  N02: { x: 250, y: 100 },
  N03: { x: 110, y: 220 },
  N04: { x: 250, y: 220 },
};

export const SRC = {
  SRC1: { x: 180, y: 100 },
  SRC2: { x: 180, y: 220 },
  SRC3: { x: 110, y: 160 },
  SRC4: { x: 250, y: 160 },
};

export const EDGES = {
  "N01_SRC1": { from: "N01", to: "SRC1", type: "main" },
  "SRC1_N02": { from: "SRC1", to: "N02", type: "main" },
  "N02_SRC1": { from: "N02", to: "SRC1", type: "main" },
  "SRC1_N01": { from: "SRC1", to: "N01", type: "main" },
  "N03_SRC2": { from: "N03", to: "SRC2", type: "main" },
  "SRC2_N04": { from: "SRC2", to: "N04", type: "main" },
  "N04_SRC2": { from: "N04", to: "SRC2", type: "main" },
  "SRC2_N03": { from: "SRC2", to: "N03", type: "main" },
  "N01_SRC3": { from: "N01", to: "SRC3", type: "alley" },
  "SRC3_N03": { from: "SRC3", to: "N03", type: "alley" },
  "N03_SRC3": { from: "N03", to: "SRC3", type: "alley" },
  "SRC3_N01": { from: "SRC3", to: "N01", type: "alley" },
  "N02_SRC4": { from: "N02", to: "SRC4", type: "alley" },
  "SRC4_N04": { from: "SRC4", to: "N04", type: "alley" },
  "N04_SRC4": { from: "N04", to: "SRC4", type: "alley" },
  "SRC4_N02": { from: "SRC4", to: "N02", type: "alley" },
  "NT_N_W_N01": { from: { x: 110, y: 20  }, to: "N01", type: "outskirts" },
  "N01_NT_N_W": { from: "N01", to: { x: 110, y: 20  }, type: "outskirts" },
  "NT_N_E_N02": { from: { x: 250, y: 20  }, to: "N02", type: "outskirts" },
  "N02_NT_N_E": { from: "N02", to: { x: 250, y: 20  }, type: "outskirts" },
  "NT_S_W_N03": { from: { x: 110, y: 300 }, to: "N03", type: "outskirts" },
  "N03_NT_S_W": { from: "N03", to: { x: 110, y: 300 }, type: "outskirts" },
  "NT_S_E_N04": { from: { x: 250, y: 300 }, to: "N04", type: "outskirts" },
  "N04_NT_S_E": { from: "N04", to: { x: 250, y: 300 }, type: "outskirts" },
  "NT_W_N_N01": { from: { x: 20,  y: 100 }, to: "N01", type: "outskirts" },
  "N01_NT_W_N": { from: "N01", to: { x: 20,  y: 100 }, type: "outskirts" },
  "NT_W_S_N03": { from: { x: 20,  y: 220 }, to: "N03", type: "outskirts" },
  "N03_NT_W_S": { from: "N03", to: { x: 20,  y: 220 }, type: "outskirts" },
  "NT_E_N_N02": { from: { x: 340, y: 100 }, to: "N02", type: "outskirts" },
  "N02_NT_E_N": { from: "N02", to: { x: 340, y: 100 }, type: "outskirts" },
  "NT_E_S_N04": { from: { x: 340, y: 220 }, to: "N04", type: "outskirts" },
  "N04_NT_E_S": { from: "N04", to: { x: 340, y: 220 }, type: "outskirts" },
};

// IntersectionGrid layout — 2×2 grid
export const GRID = [
  ["N01", "N02"],
  ["N03", "N04"],
];

export const NODE_LABELS = {
  N01: "Công sở\n+ Trường",
  N02: "Công sở\nMR",
  N03: "Khu\nDân Cư",
  N04: "Vui Chơi\n+ DC",
};

// Accident edges mẫu để demo (dùng trong UI dropdown)
export const DEMO_ACCIDENT_EDGES = [
  { label: "SRC1 → N02 (đường chính)", value: "SRC1_N02" },
  { label: "SRC2 → N04 (đường chính)", value: "SRC2_N04" },
];
