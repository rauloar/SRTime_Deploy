#!/bin/bash
sudo systemctl start srtime-api srtime-web
echo "✅ SRTime Web iniciado"
echo ""
sudo systemctl status srtime-api srtime-web --no-pager -l
