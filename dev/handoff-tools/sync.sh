#!/bin/bash
# Sync tracked repo sources into the run dir (keeps runtime state like app/config, servers, logs)
cd /home/user/Better-Crafty
git ls-files -co --exclude-standard -z | tar --null -T - -cf - | tar -C /home/crafty/run -xf -
chown -R crafty:crafty /home/crafty/run
