#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# build_map.sh — Generic map builder cho Traffic-MARL
#
# Usage:
#   ./build_map.sh <map_name>          # build map cụ thể
#   ./build_map.sh                     # interactive: chọn từ danh sách
#
# Convention: mỗi map phải có cấu trúc:
#   simulation/<map_name>/
#     net/<map_name>.nod.xml
#     net/<map_name>.edg.xml
#     net/<map_name>.typ.xml           (optional)
#     routes/gen_routes.py             (optional)
#     <map_name>.sumocfg               (optional)
#
# Output tự gen:
#   net/<map_name>.net.xml
#   routes/routes_peak.rou.xml
#   routes/routes_night.rou.xml
# ══════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Màu terminal ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Check SUMO_HOME ───────────────────────────────────────────────
if [ -z "$SUMO_HOME" ]; then
    echo -e "${RED}[ERROR]${NC} SUMO_HOME chưa được set."
    echo "  Linux/Mac: export SUMO_HOME=/path/to/sumo"
    echo "  Windows:   set SUMO_HOME=C:\\path\\to\\sumo"
    exit 1
fi

if ! command -v netconvert &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} netconvert không tìm thấy trong PATH."
    exit 1
fi

# ── Chọn map ──────────────────────────────────────────────────────
if [ -n "$1" ]; then
    MAP_NAME="$1"
else
    echo -e "${BOLD}Available maps:${NC}"
    i=1
    maplist=()
    for d in "$SCRIPT_DIR"/*/; do
        name=$(basename "$d")
        if [ -f "$d/net/${name}.nod.xml" ]; then
            echo "  [$i] $name"
            maplist+=("$name")
            ((i++))
        fi
    done
    echo ""
    read -rp "Chọn map (number hoặc tên): " choice
    if [[ "$choice" =~ ^[0-9]+$ ]]; then
        MAP_NAME="${maplist[$((choice-1))]}"
    else
        MAP_NAME="$choice"
    fi
fi

MAP_DIR="$SCRIPT_DIR/$MAP_NAME"

# ── Validate ──────────────────────────────────────────────────────
if [ ! -d "$MAP_DIR" ]; then
    echo -e "${RED}[ERROR]${NC} Không tìm thấy folder: $MAP_DIR"
    exit 1
fi
if [ ! -f "$MAP_DIR/net/${MAP_NAME}.nod.xml" ]; then
    echo -e "${RED}[ERROR]${NC} Thiếu: net/${MAP_NAME}.nod.xml"
    exit 1
fi
if [ ! -f "$MAP_DIR/net/${MAP_NAME}.edg.xml" ]; then
    echo -e "${RED}[ERROR]${NC} Thiếu: net/${MAP_NAME}.edg.xml"
    exit 1
fi

echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${BOLD} Building map: ${CYAN}${MAP_NAME}${NC}"
echo -e "${BOLD}══════════════════════════════════════${NC}"
cd "$MAP_DIR"

# ── Step 1: netconvert ────────────────────────────────────────────
echo -e "\n${YELLOW}[1/2]${NC} netconvert → ${MAP_NAME}.net.xml"

TYP_ARG=""
if [ -f "net/${MAP_NAME}.typ.xml" ]; then
    TYP_ARG="--type-files=net/${MAP_NAME}.typ.xml"
fi

netconvert \
    --node-files="net/${MAP_NAME}.nod.xml" \
    --edge-files="net/${MAP_NAME}.edg.xml" \
    $TYP_ARG \
    --output-file="net/${MAP_NAME}.net.xml" \
    --tls.default-type=actuated \
    --tls.cycle.time=90 \
    --no-turnarounds true \
    --junctions.corner-detail 5 \
    --geometry.remove true

echo -e "    ${GREEN}✓${NC} net/${MAP_NAME}.net.xml"

# ── Step 2: gen routes ────────────────────────────────────────────
if [ -f "routes/gen_routes.py" ]; then
    echo -e "\n${YELLOW}[2/2]${NC} gen_routes.py → routes_peak + routes_night"
    mkdir -p routes
    python routes/gen_routes.py
    echo -e "    ${GREEN}✓${NC} routes/routes_peak.rou.xml"
    echo -e "    ${GREEN}✓${NC} routes/routes_night.rou.xml"
else
    echo -e "\n${YELLOW}[2/2]${NC} Không có gen_routes.py — bỏ qua route generation"
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${GREEN} Done!${NC} Map ${CYAN}${MAP_NAME}${NC} built thành công."
echo ""
echo -e " Test SUMO GUI:"
echo -e "   ${CYAN}sumo-gui ${MAP_NAME}.sumocfg${NC}"
echo -e "${BOLD}══════════════════════════════════════${NC}"