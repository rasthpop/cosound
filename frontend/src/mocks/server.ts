// MSW for Node (vitest). Tests switch scenarios with `server.use(...handlersFor("map-down"))`.
import { setupServer } from "msw/node";

import { handlersFor } from "./handlers";

export const server = setupServer(...handlersFor("happy"));
