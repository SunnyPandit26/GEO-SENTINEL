@echo off
echo ======================================================================
echo    GEO-SENTINEL: Sovereign Satellite Intelligence & Change Platform
echo ======================================================================
echo.
echo [1/3] Verifying Python and CUDA environment...
python -c "import torch; print('PyTorch:', torch.__version__, '| CUDA Available:', torch.cuda.is_available())"
echo.
echo [2/3] Checking dataset and vector archive status...
if not exist "data\index_storage\faiss_index.bin" (
    echo [INFO] Index not found. Generating GeoTIFF dataset and building FAISS index...
    python data\generate_dataset.py
    python scripts\index_archive.py
)
echo.
echo [3/3] Starting GEO-SENTINEL Sovereign Workstation on http://127.0.0.1:8000 ...
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
pause
