
## New workflow

### Problem statement 

Annotating papers is tricky. 

A. We are limited by time and energy that domain experts can put into reading documents. Even if they could read all of them, each document can be categorized in a number of ways. 

B. We want to use domain expertise, but not that much that we biased our distant reading methods.


### Solution

Lets have full-text available, abstract can only get you so far to infer methods. 

`docling` to get markdown from PDFs


Label studio for annotations. The key idea is that LS API offers a nice way to build feedback mechanism between models and domain experts. But we need to be careful in how we construct that feedback mechanism such that we avoid (B).

LS + custom static frontend can give you UX that is better than each taken indepently; static frontend can be used for specific task, while we centralized annotations using LS api.


## Methodology

Knobs that we can tune.

### 1. Model Architecture and Size

Model size and architecture work together to give base performance.

Right now we tried
 - `Gemma4-31B`

We could change the underlying model altogether, using something like `qwen3.6 27B dense` for instance. Or not.

`Gemma4-31B` has emerged as a relatively-small model size, yet performing well. Keeping the model size small means we can have better token/s performance, which is useful as we iterate. We just stick with that choice for this project.

#### Within mode, different modes

With `Gemma4 31B`, we can enable `thinking`. We could play with that, but thinking mode should almost always outperform non-thinking so we stick with `thinking` enabled across runs. 

### 2. Categories: 

Once we have decided the model, we can play with the categories. Current categories
  - `qual`
  - `quant`
  - `both`
  - `Descriptive`
  - `spatial/mapping`
  - `unclear`

Other categories we could include to disambiguate:
    - `theoretical/essay` versus `descriptive-empirical`
    - `both` -> `spatial-quant`

Note that here we used `single-label` approach. But we could used `multi-label` and droip some categories.


### 3. Prompt engineering

The way we describe the categories to what model have an impact on the output. Dumb models (typically smaller ones) might need more explicit instructions, and even there can hit some ceiling performance due to model architecture. Bigger models might have a more "common-sense", similar to undergrad-level thinking. But still needs to be informed concisely about the tasks.

We have a couple of knobs here, but we limited ourselves to:
  - Changing prompts (better framing, obvious pitfalls)
  - Providing informative examples
  - Longer prompt with more information and context (see Data)

This step is more tricky than it appears. 

### 4. Data

After we have chosen the model and the categories, what data are we showing? To the model, but also to the annotators. We will have disagreement based on that.

Currently we have tried the following:
  - `abstract`
  - `abstract+title`
  - `full text (first X tokens)`


#### Multi-phase (adaptive) stategy
  
We have developed what we call a `Section-based` approach. The workflow is as follows
  - (i) Extract headers: we have markdown, we can simply use `##`
  - (ii) Ask Gemma to infer method sections (needle in a haystack problem)
  - (iii) Ask Gemma to annotate based on the content of inferred method sections.

Here we have 3 steps informed by one model or another; model to parse PDF (but this is trustworthy, not genAI), model to extract method sections (_should_ be easy enough for gemma), and model to annotate (still where most of the thinking should happen).


### 5. Optimizing

To assess performance and see the impact of our choice, we also need a versioning system that allows to compare performance for all of our choices above.

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