"""
Entrypoint Serverless Vercel per Motore Espropri Italia
Proprietà intellettuale: Nicola Valigi (Houdinick)
"""

import sys
from pathlib import Path

# Aggiungi root al path di Python per importare server e moduli
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from server import app
