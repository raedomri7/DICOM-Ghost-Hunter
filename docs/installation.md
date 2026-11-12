# DICOM Ghost Hunter — Installation Guide (Windows 11)

## Prerequisites

- Windows 11 Pro
- Python 3.12 (`py` launcher)
- 8 GB RAM minimum (16 GB recommended)
- GPU optional (NVIDIA CUDA for PyTorch AI features)

## Installation

```powershell
# 1. Create virtual environment
py -m venv .venv

# 2. Activate
.venv\Scripts\Activate.ps1

# 3. Install dependencies
py -m pip install -r requirements.txt

# 4. Configure (optional)
copy .env.example .env
# Edit .env and config/qc_rules.yaml as needed

# 5. Initialize database
py -c "from app.database import bootstrap_database; bootstrap_database()"

# 6. Run the application
py main.py
```

## Optional Dependencies

| Feature | Package | Command |
|---------|---------|---------|
| AI / PyTorch | torch, torchvision | `py -m pip install torch torchvision` |
| Medical AI | MONAI | `py -m pip install monai` |
| 3D visualization | VTK | `py -m pip install vtk` |
| DICOM networking | pynetdicom | `py -m pip install pynetdicom` |

## Running Tests

```powershell
.venv\Scripts\Activate.ps1
py -m pytest tests/ -v
```

## Linting

```powershell
.venv\Scripts\Activate.ps1
py -m ruff check app/ tests/ main.py
```

## Packaging (PyInstaller)

```powershell
.venv\Scripts\Activate.ps1
py -m pip install pyinstaller
pyinstaller --noconsole --name "DICOM Ghost Hunter" main.py
```

## Orthanc PACS (Optional)

Install Orthanc server separately from https://www.orthanc-server.com/, then configure host in `.env`:

```
ORTHANC_HOST=http://localhost:8042
ORTHANC_USERNAME=
ORTHANC_PASSWORD=
```
