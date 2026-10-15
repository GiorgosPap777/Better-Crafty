#!/bin/bash
exec env -u JAVA_TOOL_OPTIONS -u JDK_JAVA_OPTIONS su crafty -s /bin/bash -c "cd /home/crafty/run && exec /home/crafty/venv/bin/python main.py -d -i > /home/crafty/run/out.log 2>&1"
