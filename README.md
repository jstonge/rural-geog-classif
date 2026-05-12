

## Methodology

Knobs to tune
- single-label categories (versus multi-label): 
  - qual
  - quant
  - both
  - Descriptive
  - spatial/mapping
  - unclear
  - Others we could includes
    - theoretical/essay versus descriptive-empirical
    - both -> spatial-quant
- the underlying model (so far only Gemma4)
- the data shown
  - abstract
  - abstract+title
  - full text (first X tokens)
  - Multi-phase stategy
    - Extract headers; infer method sections; found method section
- the prompt
  - changing instructions
  - providing more examples

## setup

This command to get a H200 node:
```sh
srun --partition=nvgpu --gpus=1 --constraint=GPU_SKU:H200      --cpus-per-task=8 --mem=128G --time=3:00:00 --pty /bin/bash
```
Lets load cuda 12.9.1
```sh
module load cuda/12.9.1
```
lets download `vllm` library accordingly
```
uv venv python=3.12 && source .venv/bin/activate
uv pip install vllm --extra-index-url https://wheels.vllm.ai/0.20.2/cu129 --extra-index-url https://download.pytorch.org/whl/cu129 --index-strategy unsafe-best-match
```
To start `vllm` server with thinking enabled
```
uv run vllm serve google/gemma-4-31B-it \
  --max-model-len 16384 \
  --enable-auto-tool-choice \
  --reasoning-parser gemma4 \
  --tool-call-parser gemma4 \
  --chat-template transform/src/tool_chat_template_gemma4.jinja
```
For that to work, you need the template [tool_chat_template_gemma4.jinja](https://github.com/vllm-project/vllm/blob/main/examples/tool_chat_template_gemma4.jinja) (docs on thinking mode can be found [here](https://ai.google.dev/gemma/docs/capabilities/thinking)). Lets run a jupyter server to serve the notebook. It needs to live on the same node than our LLM:
```
uv run jupyter notebook --no-browser --ip=0.0.0.0 --port=8888
```
Connect to provided port in notebook. Once the `vllm` server shows `(APIServer pid=1192940) INFO:     Application startup complete.`, you're ready to go!