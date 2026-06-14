"""
build_map.py — Generic map builder cho Traffic-MARL (cross-platform)

Usage:
    python scripts/build_map.py mydinh    # build map cụ thể
    python scripts/build_map.py           # interactive: chọn từ danh sách

Convention: mỗi map phải có cấu trúc:
    simulation/<map_name>/
        net/<map_name>.nod.xml     ← bắt buộc
        net/<map_name>.edg.xml     ← bắt buộc
        net/<map_name>.typ.xml     ← optional
        routes/gen_routes.py       ← optional
        <map_name>.sumocfg         ← optional

Output tự gen:
    net/<map_name>.net.xml
    routes/routes_peak.rou.xml
    routes/routes_night.rou.xml
"""

import os
import sys
import subprocess
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
SIM_DIR     = ROOT / "simulation"

# ── Màu terminal (Windows compatible) ────────────────────────────
if sys.platform == "win32":
    os.system("color")  # enable ANSI trên Windows 10+

RED    = "\033[0;31m"
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN   = "\033[0;36m"
BOLD   = "\033[1m"
NC     = "\033[0m"

def log(msg):       print(msg)
def ok(msg):        print(f"    {GREEN}✓{NC} {msg}")
def err(msg):       print(f"{RED}[ERROR]{NC} {msg}"); sys.exit(1)
def step(n, msg):   print(f"\n{YELLOW}[{n}]{NC} {msg}")
def header(msg):    print(f"\n{BOLD}{'═'*40}{NC}\n{BOLD} {msg}{NC}\n{BOLD}{'═'*40}{NC}")

# ── Check SUMO_HOME ───────────────────────────────────────────────
def check_sumo():
    sumo_home = os.environ.get("SUMO_HOME", "")
    if not sumo_home:
        err(
            "SUMO_HOME chưa được set.\n"
            "  Windows:   set SUMO_HOME=C:\\path\\to\\sumo\n"
            "  Linux/Mac: export SUMO_HOME=/path/to/sumo"
        )
    netconvert = "netconvert.exe" if sys.platform == "win32" else "netconvert"
    result = subprocess.run(
        [netconvert, "--version"],
        capture_output=True
    )
    if result.returncode not in (0, 1):  # netconvert --version returns 1
        err(
            "netconvert không tìm thấy trong PATH.\n"
            f"  Thêm {sumo_home}\\bin vào PATH rồi thử lại."
        )

# ── Liệt kê maps có sẵn ──────────────────────────────────────────
def list_maps() -> list[str]:
    maps = []
    for d in sorted(SIM_DIR.iterdir()):
        if d.is_dir() and (d / "net" / f"{d.name}.nod.xml").exists():
            maps.append(d.name)
    return maps

# ── Chọn map ─────────────────────────────────────────────────────
def pick_map(arg: str | None) -> str:
    if arg:
        return arg

    maps = list_maps()
    if not maps:
        err(f"Không tìm thấy map nào trong {SIM_DIR}")

    log(f"{BOLD}Available maps:{NC}")
    for i, name in enumerate(maps, 1):
        log(f"  [{i}] {name}")
    log("")

    choice = input("Chọn map (số hoặc tên): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if not (0 <= idx < len(maps)):
            err(f"Số không hợp lệ: {choice}")
        return maps[idx]
    return choice

# ── Step 1: netconvert ────────────────────────────────────────────
def run_netconvert(map_name: str, map_dir: Path):
    step("1/2", f"netconvert → {map_name}.net.xml")

    cmd = [
        "netconvert",
        f"--node-files=net/{map_name}.nod.xml",
        f"--edge-files=net/{map_name}.edg.xml",
        f"--output-file=net/{map_name}.net.xml",
        "--tls.default-type=actuated",
        "--tls.cycle.time=90",
        "--no-turnarounds=true",
        "--junctions.corner-detail=5",
        
    ]

    typ_file = map_dir / "net" / f"{map_name}.typ.xml"
    if typ_file.exists():
        cmd.append(f"--type-files=net/{map_name}.typ.xml")

    result = subprocess.run(cmd, cwd=map_dir)
    if result.returncode != 0:
        err("netconvert thất bại. Kiểm tra lại nod.xml / edg.xml.")

    ok(f"net/{map_name}.net.xml")

# ── Step 2: gen routes ────────────────────────────────────────────
def run_gen_routes(map_dir: Path):
    gen_script = map_dir / "routes" / "gen_routes.py"
    if not gen_script.exists():
        step("2/2", "Không có gen_routes.py — bỏ qua route generation")
        return

    step("2/2", "gen_routes.py → routes_peak + routes_night")
    (map_dir / "routes").mkdir(exist_ok=True)

    result = subprocess.run([sys.executable, str(gen_script)], cwd=map_dir)
    if result.returncode != 0:
        err("gen_routes.py thất bại.")

    ok("routes/routes_peak.rou.xml")
    ok("routes/routes_night.rou.xml")

# ── Main ──────────────────────────────────────────────────────────
def main():
    check_sumo()

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    map_name = pick_map(arg)
    map_dir  = SIM_DIR / map_name

    # Validate
    if not map_dir.is_dir():
        err(f"Không tìm thấy folder: {map_dir}")
    if not (map_dir / "net" / f"{map_name}.nod.xml").exists():
        err(f"Thiếu: net/{map_name}.nod.xml")
    if not (map_dir / "net" / f"{map_name}.edg.xml").exists():
        err(f"Thiếu: net/{map_name}.edg.xml")

    header(f"Building map: {CYAN}{map_name}{NC}")

    run_netconvert(map_name, map_dir)
    run_gen_routes(map_dir)

    log(f"\n{BOLD}{'═'*40}{NC}")
    log(f"{GREEN} Done!{NC} Map {CYAN}{map_name}{NC} built thành công.")
    log(f"\n Test SUMO GUI:")
    log(f"   {CYAN}sumo-gui simulation/{map_name}/{map_name}.sumocfg{NC}")
    log(f"{BOLD}{'═'*40}{NC}\n")


if __name__ == "__main__":
    main()