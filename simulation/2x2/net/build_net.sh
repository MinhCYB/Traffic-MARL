#!/bin/bash
# Chạy 1 lần để generate 2x2.net.xml
# Yêu cầu: SUMO_HOME đã set, netconvert có trong PATH
#
# Windows: chạy trong Git Bash hoặc thay \ thành /
#   netconvert --node-files=2x2.nod.xml ^
#              --edge-files=2x2.edg.xml ^
#              --type-files=2x2.typ.xml ^
#              --output-file=2x2.net.xml ^
#              --tls.default-type=actuated ^
#              --no-turnarounds true ^
#              --junctions.corner-detail 5

netconvert \
    --node-files=2x2.nod.xml \
    --edge-files=2x2.edg.xml \
    --type-files=2x2.typ.xml \
    --output-file=2x2.net.xml \
    --tls.default-type=actuated \
    --no-turnarounds true \
    --junctions.corner-detail 5

echo "Done: 2x2.net.xml generated"
