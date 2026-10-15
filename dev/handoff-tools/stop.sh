#!/bin/bash
pkill -f "venv/bin/python main.py" ; sleep 2; pkill -9 -f "venv/bin/python main.py"; true
