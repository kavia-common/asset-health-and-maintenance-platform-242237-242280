#!/bin/bash
cd /home/kavia/workspace/code-generation/asset-health-and-maintenance-platform-242237-242280/asset_management_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

