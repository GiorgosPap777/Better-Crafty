#!/bin/bash
exec env -u JAVA_TOOL_OPTIONS -u JDK_JAVA_OPTIONS su crafty -s /bin/bash -c "cd /home/crafty/run_before && exec /home/crafty/venv/bin/python ma""in.py -d -i > /home/crafty/run_before/out.log 2>&1"
