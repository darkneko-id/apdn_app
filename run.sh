#!/bin/bash
echo "Starting TKDN Finder..."
echo "Buka browser di http://localhost:8000"
echo "Tekan Ctrl+C untuk berhenti."
echo ""
uvicorn tkdn_finder.main:app --host 127.0.0.1 --port 8000
