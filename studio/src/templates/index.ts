// Bundled template scenes for the gallery. Use absolute positions so they lay
// out predictably on first load in the freeform editor.

export interface Template {
  id: string;
  name: string;
  description: string;
  yaml: string;
}

export const TEMPLATES: Template[] = [
  {
    id: "hello-world",
    name: "Hello World",
    description: "Minimal: a client talking to a server.",
    yaml: `theme: dark_terminal
resolution: "1080p"
fps: 60
nodes:
  - {id: client, label: Client, type: user, position: {x: 200, y: 480}}
  - {id: server, label: API Server, position: {x: 900, y: 480}}
connections:
  - {id: c1, source: client, target: server}
choreography:
  - action: play
    animation: {type: fade_in, targets: [client, server, c1]}
  - action: play
    animation: {type: transfer, connection: c1, payload: "GET /"}
`,
  },
  {
    id: "login-flow",
    name: "Login Flow",
    description: "Client authenticates against an API backed by a database.",
    yaml: `theme: neon_cyber
resolution: "1080p"
fps: 60
nodes:
  - {id: client, label: Client, type: user, position: {x: 150, y: 480}}
  - {id: auth, label: Auth Service, position: {x: 750, y: 480}}
  - {id: db, label: Users DB, type: database, position: {x: 1350, y: 480}}
connections:
  - {id: c1, source: client, target: auth}
  - {id: c2, source: auth, target: db}
choreography:
  - action: play
    animation: {type: fade_in, targets: [client, auth, db, c1, c2]}
  - action: play
    animation: {type: transfer, connection: c1, payload: "POST /login"}
  - action: play
    animation: {type: pulse, target: auth}
  - action: play
    animation: {type: transfer, connection: c2, payload: "SELECT user"}
`,
  },
  {
    id: "microservices",
    name: "Microservices",
    description: "An API gateway fanning out to two services.",
    yaml: `theme: blueprint
resolution: "1080p"
fps: 60
nodes:
  - {id: gw, label: API Gateway, position: {x: 200, y: 480}}
  - {id: users, label: Users Svc, position: {x: 900, y: 260}}
  - {id: orders, label: Orders Svc, position: {x: 900, y: 700}}
connections:
  - {id: c1, source: gw, target: users}
  - {id: c2, source: gw, target: orders}
choreography:
  - action: play
    animation: {type: fade_in, targets: [gw, users, orders, c1, c2]}
  - action: concurrent
    animations:
      - {type: transfer, connection: c1, payload: "GET /users"}
      - {type: transfer, connection: c2, payload: "GET /orders"}
`,
  },
  {
    id: "cloud-infra",
    name: "Cloud Infrastructure",
    description: "API with a cache and an async queue feeding a database.",
    yaml: `theme: dark_terminal
resolution: "1080p"
fps: 60
nodes:
  - {id: client, label: Client, type: user, position: {x: 120, y: 480}}
  - {id: api, label: API Server, position: {x: 700, y: 480}}
  - {id: cache, label: Redis Cache, type: cache, position: {x: 700, y: 220}}
  - {id: queue, label: Task Queue, type: queue, position: {x: 1300, y: 260}}
  - {id: db, label: PostgreSQL, type: database, position: {x: 1300, y: 720}}
connections:
  - {id: c1, source: client, target: api}
  - {id: c2, source: api, target: cache}
  - {id: c3, source: api, target: queue}
  - {id: c4, source: queue, target: db}
choreography:
  - action: play
    animation: {type: fade_in, targets: [client, api, cache, queue, db, c1, c2, c3, c4]}
  - action: play
    animation: {type: transfer, connection: c1, payload: "GET /data"}
  - action: play
    animation: {type: highlight, target: cache}
  - action: play
    animation: {type: transfer, connection: c3, payload: "enqueue"}
`,
  },
];

export const DEFAULT_TEMPLATE = TEMPLATES[0];
