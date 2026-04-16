2026-04-15
==========

Setting up the environment:
- We use [olmocr](https://github.com/allenai/olmocr?tab=readme-ov-file) for parsing PDFs.
- We use [model release 0.4.0](https://huggingface.co/allenai/olmOCR-2-7B-1025-FP8)
- To get the gpu, we run `srun --partition=nvgpu --gpus=1 --constraint=GPU_FP:FP64 --time=03:00:00 --pty bash` (one of the 112 GPUs of A100, H100, H200). All should have at least 12 GB of GPU RAM and 30GB of free disk space.
- We use the conda env called `olmoocr2` because one of the dependencies is `pdftoppm`, via `module load miniforge/25.11.0-py3.1`
- We also run on `module load cuda/12.9.1`
- Finally

```
pip install olmocr[gpu] --extra-index-url https://download.pytorch.org/whl/cu128

# Recommended: Install flash infer for faster inference on GPU
pip install https://download.pytorch.org/whl/cu128/flashinfer/flashinfer_python-0.2.5%2Bcu128torch2.7-cp38-abi3-linux_x86_64.whl
```