/* Dedicated single-model WebLLM worker for iPhone Safari.
   This worker performs all actual language-model inference on-device.
   Pin 0.2.82: newer 0.2.83+ builds have reported GPU regressions. */
import { WebWorkerMLCEngineHandler } from "https://esm.run/@mlc-ai/web-llm@0.2.82";
const handler = new WebWorkerMLCEngineHandler();
self.onmessage = event => handler.onmessage(event);
