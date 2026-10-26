// Linear + Slack glue for the droid-spec and droid-build workflows.
//
//   node bridge.mjs create-issue --spec droid-out/spec.md
//   node bridge.mjs get-issue    --issue <id>
//   node bridge.mjs update       --issue <id> [--state <name>] [--comment <md>] [--slack <text>]
//   node bridge.mjs slack        --text <text>          (replies in SLACK_CHANNEL/SLACK_TS thread)

import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";

const { positionals, values: args } = parseArgs({
  allowPositionals: true,
  options: {
    spec: { type: "string" },
    issue: { type: "string" },
    state: { type: "string" },
    comment: { type: "string" },
    slack: { type: "string" },
    text: { type: "string" },
  },
});

const env = process.env;
const STATE_FIELDS = "states { nodes { id name type } }";

const commands = {
  "create-issue": createIssue,
  "get-issue": getIssue,
  update,
  slack: () => slackReply(envThread(), args.text),
};

const command = commands[positionals[0]];
if (!command) {
  console.error(`Unknown command: ${positionals[0] ?? "(none)"}`);
  process.exit(2);
}
await command();

// ---------- commands ----------

async function findProjectId(name) {
  const { projects } = await linear(
    `query($name: String!) { projects(filter: { name: { eqIgnoreCase: $name } }) { nodes { id } } }`,
    { name },
  );
  if (!projects.nodes[0]) throw new Error(`No Linear project named ${name}`);
  return projects.nodes[0].id;
}

async function createIssue() {
  const spec = readFileSync(args.spec, "utf8").trim();
  const heading = /^#\s+(.+)$/m.exec(spec);
  const title = (heading?.[1] ?? "Feature request from Slack").trim().slice(0, 120);
  const body = heading ? spec.replace(heading[0], "").trim() : spec;
  const buildState = env.LINEAR_BUILD_STATE || "Todo";

  const { teams } = await linear(
    `query($key: String!) { teams(filter: { key: { eq: $key } }) { nodes { id ${STATE_FIELDS} } } }`,
    { key: requireEnv("LINEAR_TEAM_KEY") },
  );
  const team = teams.nodes[0];
  if (!team) throw new Error(`No Linear team with key ${env.LINEAR_TEAM_KEY}`);
  const backlog = pickState(team.states, env.LINEAR_SPEC_STATE || "Backlog", "backlog");
  const projectId = env.LINEAR_PROJECT_NAME ? await findProjectId(env.LINEAR_PROJECT_NAME) : undefined;

  const source = env.SLACK_PERMALINK
    ? `Requested in Slack by ${env.REQUESTER || "someone"}: ${env.SLACK_PERMALINK}`
    : `Requested by ${env.REQUESTER || "someone"}`;
  const description = [
    body,
    "---",
    `_${source}_`,
    `_Spec drafted by Factory Droid. Review it, then move it to **${buildState}** or comment \`@droid\` to start the build._`,
  ].join("\n\n");

  const { issueCreate } = await linear(
    `mutation($input: IssueCreateInput!) {
       issueCreate(input: $input) { success issue { id identifier url title } }
     }`,
    { input: { teamId: team.id, title, description, stateId: backlog?.id, projectId } },
  );
  const issue = issueCreate.issue;
  console.log(`Created ${issue.identifier}: ${issue.url}`);
  setOutput("identifier", issue.identifier);
  setOutput("url", issue.url);

  await slackReply(
    envThread(),
    `📋 Spec ready: <${issue.url}|${issue.identifier} ${issue.title}>\n` +
      `It's in *${backlog?.name ?? "the backlog"}*. Review it in Linear, then move it to *${buildState}* ` +
      "or comment `@droid` on the ticket to have Droid build it.",
  );
}

async function getIssue() {
  const issue = await fetchIssue(args.issue, "identifier title description url branchName team { key }");
  const skip = Boolean(env.LINEAR_TEAM_KEY) && issue.team.key !== env.LINEAR_TEAM_KEY;
  const thread = slackThreadFrom(issue.description);

  writeFileSync(
    join(env.RUNNER_TEMP ?? ".", "issue.md"),
    `# ${issue.identifier}: ${issue.title}\n\n${issue.description ?? ""}\n`,
  );
  setOutput("skip", String(skip));
  setOutput("identifier", issue.identifier);
  setOutput("title", issue.title);
  setOutput("url", issue.url);
  setOutput("branch", issue.branchName || `droid/${issue.identifier.toLowerCase()}`);
  setOutput("slack_channel", thread?.channel ?? "");
  setOutput("slack_ts", thread?.ts ?? "");
  console.log(`${issue.identifier} (${issue.team.key})${skip ? " — other team, skipping" : ""}`);
}

async function update() {
  const issue = await fetchIssue(args.issue, `description team { ${STATE_FIELDS} }`);

  if (args.comment) {
    await linear(
      "mutation($input: CommentCreateInput!) { commentCreate(input: $input) { success } }",
      { input: { issueId: issue.id, body: args.comment } },
    );
  }
  if (args.state) {
    const fallbackType = /review|progress/i.test(args.state) ? "started" : undefined;
    const state = pickState(issue.team.states, args.state, fallbackType);
    if (state) {
      await linear(
        "mutation($id: String!, $stateId: String!) { issueUpdate(id: $id, input: { stateId: $stateId }) { success } }",
        { id: issue.id, stateId: state.id },
      );
    } else {
      console.warn(`No Linear state named "${args.state}"; leaving state unchanged.`);
    }
  }
  if (args.slack) {
    await slackReply(slackThreadFrom(issue.description), args.slack);
  }
}

// ---------- Linear ----------

async function linear(query, variables) {
  const res = await fetch("https://api.linear.app/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: requireEnv("LINEAR_API_KEY") },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (!res.ok || json.errors) {
    throw new Error(`Linear API error: ${JSON.stringify(json.errors ?? json)}`);
  }
  return json.data;
}

async function fetchIssue(id, fields) {
  if (!id) throw new Error("--issue is required");
  const { issue } = await linear(`query($id: String!) { issue(id: $id) { id ${fields} } }`, { id });
  return issue;
}

function pickState(states, name, fallbackType) {
  const nodes = states.nodes;
  return (
    nodes.find((s) => s.name.toLowerCase() === name.toLowerCase()) ??
    (fallbackType ? nodes.find((s) => s.type === fallbackType) : undefined)
  );
}

// ---------- Slack ----------

function envThread() {
  return env.SLACK_CHANNEL && env.SLACK_TS ? { channel: env.SLACK_CHANNEL, ts: env.SLACK_TS } : null;
}

// Slack permalinks look like .../archives/C0123ABC/p1729700000123456 → ts 1729700000.123456
function slackThreadFrom(text) {
  const match = /slack\.com\/archives\/([A-Z0-9]+)\/p(\d{10})(\d{6})/.exec(text ?? "");
  return match ? { channel: match[1], ts: `${match[2]}.${match[3]}` } : null;
}

async function slackReply(thread, text) {
  if (!thread || !text || !env.SLACK_BOT_TOKEN) return;
  const res = await fetch("https://slack.com/api/chat.postMessage", {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      Authorization: `Bearer ${env.SLACK_BOT_TOKEN}`,
    },
    body: JSON.stringify({ channel: thread.channel, thread_ts: thread.ts, text, unfurl_links: false }),
  });
  const json = await res.json();
  if (!json.ok) console.warn(`Slack post failed: ${json.error}`);
}

// ---------- misc ----------

function requireEnv(name) {
  if (!env[name]) throw new Error(`${name} is not set`);
  return env[name];
}

function setOutput(key, value) {
  if (!env.GITHUB_OUTPUT) return;
  appendFileSync(env.GITHUB_OUTPUT, `${key}<<__BRIDGE_EOF__\n${value}\n__BRIDGE_EOF__\n`);
}
