#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Upgrading pip ---"
pip install --upgrade pip

echo "--- Installing build dependencies (cmake) ---"
pip install cmake

echo "--- Installing application requirements ---"
# We use MAKEFLAGS="-j1" to limit memory usage during dlib compilation
# This prevents the 8GB OOM error on Render's build system
export MAKEFLAGS="-j1"
pip install --no-cache-dir -r requirements.txt
