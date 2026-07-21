#!/bin/bash
sudo systemctl start srtime-api
echo "✅ SRTime Web iniciado"
echo ""
sudo systemctl status srtime-api --no-pager -l
