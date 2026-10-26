"""Convert RNAfold PostScript output using the configured Ghostscript."""
import os
import subprocess
import sys

subprocess.run([os.environ.get("MRNAVIEWER_GS_BIN", "gs"),
                "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dEPSCrop",
                "-sDEVICE=png16m", "-r150", "-sOutputFile="+sys.argv[2], sys.argv[1]],
               check=True, capture_output=True)
