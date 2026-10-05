// Composition root: the only place that knows which concrete pieces are used.
import { HttpBackend } from "./backend.js";
import { AppController } from "./controller.js";
import { EXAMPLES } from "./examples.js";
import { AppModel } from "./model.js";
import { AppView } from "./view.js";

const model = new AppModel();
const controller = new AppController(model, new HttpBackend(), { examples: EXAMPLES });
new AppView(document, model, controller);
