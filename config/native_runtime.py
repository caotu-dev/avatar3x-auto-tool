"""Bound native math worker stacks before importing NumPy/OpenCV."""
import os


def configure_native_runtime():
    # The bot has one image-processing worker. Large default BLAS thread pools
    # reserve unnecessary per-thread stacks on machines sharing RAM with LDPlayer.
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '1'
