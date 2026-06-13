// mapLayouts/index.js — load layout đúng theo topology string
import * as layout2x2    from "./layout_2x2.js";
import * as layoutMydinh from "./layout_mydinh.js";

const LAYOUTS = {
  "2x2":    layout2x2,
  "mydinh": layoutMydinh,
};

const FALLBACK = layout2x2;

/**
 * Trả về layout config cho topology đang chạy.
 * Nếu topology chưa có layout → fallback về 2x2 và log warning.
 */
export function getLayout(topology) {
  const layout = LAYOUTS[topology];
  if (!layout) {
    console.warn(`[mapLayouts] Không tìm thấy layout cho topology "${topology}", dùng 2x2 fallback.`);
    return FALLBACK;
  }
  return layout;
}

export { layout2x2, layoutMydinh };
