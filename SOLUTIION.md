# General Magic Take Home

The aim of this assignment was two fold:

1. Fix the agent overload issue related to the uncontrolled growth of execution agents
2. Add a new AI feature, with a focus on creativity/usefulness

This short README will give a brief but detailed description on the approach to achieving both goals.


## Fixing Agent Overload Issues

The issue to fix here is as the roster of execution agents grow they begin to overload the context of the interaction agent since every active agent is inserted into the messages of the LLM call at every turn in the ```prepare_message_with_history``` function. Interestingly the blog author's claim that semantic search is a naive solution — this is not necessarily correct. Semantic search (depending on how its implemented of course) is actually a really robust and useful solution to the problem as it is the best way to filter possible agents to a relevant subset and provide only those as agents to be rendered as part of message preparation with history. With this in mind my proposed and implemented solution works as follows:

### Embeddings, Search Space and Roster

A new embedding store (`AgentEmbeddingStore`) is added to the application backed by a JSON file (`embeddings.json`), along with an update to the schema of the roster. The roster was updated from a flat list of agent name strings to a list of dicts containing `name` and `last_interacted` (an ISO timestamp), which gives us the recency data we need for both the fallback strategy and eviction policy.

Both the embedding store and roster use file locking with exponential backoff retries to handle concurrent access safely — important since the embedding updates happen asynchronously and could race with other operations.

#### Execution Agent Creation and Reuse
When an execution agent is created by the interaction agent and added to the roster, a new embedding is added to the embedding store. This entry includes the agent name, the instruction used for the agent, and the embedding vector. The vector is generated using `openai/text-embedding-3-small` via OpenRouter — a small, fast embedding model that keeps latency low while still producing useful semantic representations. The text that gets embedded follows the format ```{agent_name}: {instruction}```.

Whenever an agent is reused (found to already be in the roster), its `last_interacted` timestamp is updated and the agent embeddings are regenerated. For the embedding update, a sliding window of the most recent instructions (configurable via `max_agent_instructions_for_embedding`, defaulting to 3) along with the agent name are used as the embedding text, following the format ```{agent_name}: {instruction_1} | {instruction_2} | {instruction_3}```. This allows the semantic search to bias towards what the agent has most recently done, improving relevancy of results. The older instructions naturally fall off the window as new ones arrive, so the embedding stays current without growing unbounded.

This embedding upsert happens async — fired off as a `loop.create_task` in the `send_message_to_agent` tool handler — to prevent blocking the event loop and adding unneeded latency. This can cause a very narrow edge case whereby a user sends a message that requires an execution agent and the embedding store has not been updated yet, so semantic search may not return that agent as part of the search. To combat this we also pull a set of the top k most recently interacted with agents from the roster and merge them with what semantic search returns when necessary to meet our quota of k results for rendering (this will be explained in the next section where we go through the flow of how the agents are rendered). As updating the embeddings is a very quick operation this edge case is not very likely but is a good thing to cover.

![Embedding and Agent Search Flow](./images/embedding_diagram.png)


#### Rendering Agents During Conversation

For each user and agent message that gets sent to the LLM, the list of active agents are rendered via the `_render_active_agents` function in `prepare_message_with_history`. The original solution took every agent in the roster, did no processing, and added them all to the set of messages sent to the LLM. The updated solution now does the following:

1. Takes the current message text (user message or agent message)
2. Short-circuits early: if the total number of agents in the roster is already at or below `top_k` (configurable, defaults to 5), all agents are returned directly — no point running semantic search when we'd return everything anyway
3. Embeds that message text using the same open ai embedding model
4. Searches through the embedding store by computing cosine similarity between the embedded message and the stored vector for each execution agent, scoped to only agents currently in the roster
5. Returns the agents with the k highest similarity scores
6. As fallback protection, also retrieves the top k most recently interacted with agents from the roster (sorted by `last_interacted` timestamp). If semantic search fails entirely (exception caught and logged), the recency results are used alone. Otherwise, the two sets are blended: semantic results take priority, then remaining slots are filled with recent agents that weren't already in the semantic results, up to the k quota
7. Renders those filtered agents as part of the chat message with history sent to the LLM

![Embedding Search at Request Time](./images/embedding_search.png)

#### Other Notes and Considerations
I had initially had the idea of exposing this agent search as a tool that the interaction agent could call, however quickly dismissed that as it would have introduced more latency, LLM calls and token usage that would not have been of great benefit when we can glean enough useful information from the text of the query and the instructions of the execution agent.

There was still the potential issue of having the number of agents in the roster and the number of embeddings stored grow uncontrollably. This would add potential latency to the semantic search and also expand the search space so much that semantic search would return less relevant execution agent results. To combat this I added a hard cap on the total number of execution agents that can live in the roster and in the embedding store (configurable via `max_execution_agents`, currently defaults to 50). When a new execution agent is spun up, as part of adding it to the roster we check the total count — if it exceeds the hard cap we use an LRU eviction policy based on the `last_interacted` timestamp to remove the least recently used agents from both the roster and the embedding store. The eviction is synchronous with the add operation so the cap is always enforced before the roster is persisted.

All of the key parameters — `top_k_agents`, `max_agent_instructions_for_embedding`, `embedding_model`, and `max_execution_agents` — are configurable through environment variables, making it easy to tune the system without code changes.


## Contextual Memory — User Preferences

### The Idea

The inspiration for this feature comes from two places. The first is concepts like `claude.md` and `agents.md` that we see in modern development tooling — instead of having to constantly remind the AI agents we work with about our quirks, desired behaviours and patterns, it makes much more sense to have a persistent memory that captures these things. OpenPoke is essentially a personal assistant, and a good personal assistant should be tailored to each person and the experience they want to have. Rather than the user having to repeat themselves every session, the system should just know.

The second, and what I think adds an extra bit of brilliance to the idea, is that the interaction agent can also identify and save preferences that it learns from you on its own. This makes OpenPoke feel like an application that is genuinely adapting to you — learning your preferences and tailoring your experience further without you having to do anything. If it notices you always write in lowercase, or that you consistently CC the same person on emails, it picks up on that pattern and saves it as a preference. The user gets a notification when this happens so they're always in the loop, but the fact that it happens proactively makes the experience feel much more alive and personal.

Yes, this does add some extra token cost since the preferences are injected into every turn. But when building products like this there is always a trade-off between added token cost and user experience, and this particular feature and the wow factor of it is well worth the slight increase in tokens used. A personal assistant that remembers how you like things done is fundamentally more useful than one that doesn't.

### How It Works

The preference system is backed by a `PreferenceStore` that persists to a JSON file (`user_preferences.json`), using the same file locking pattern as the roster and embedding store for safe concurrent access. Each preference is stored as an object with an `id`, `content` (the natural language preference text), `source` (either `"user"` for explicitly requested preferences or `"agent"` for ones the interaction agent inferred), and `created_at`/`updated_at` timestamps. There's a hard cap on the total number of preferences (configurable via `max_preferences`, defaults to 20) to prevent unbounded growth.

There are two distinct paths for creating preferences, and this separation is intentional:

**User-explicit preferences** — when the user directly asks OpenPoke to remember something (e.g. "remember that I like formal emails"), the interaction agent delegates this to an execution agent via `send_message_to_agent`. The execution agent has full CRUD tools available: `addPreference`, `updatePreference`, `removePreference`, and `listPreferences`. This means the user can manage their preferences like any other task — add, update, list and delete them through natural conversation.

**Agent-inferred preferences** — the interaction agent has its own `save_preference` tool that it uses when it notices a consistent pattern in the user's behaviour. The key constraint here is that it should only infer from repeated patterns, not a single instance. A user writing in lowercase once doesn't mean they always want lowercase — but if they do it consistently across multiple messages, that's a pattern worth capturing. When the interaction agent saves an inferred preference, it notifies the user with an explanation of what it observed and what it saved, keeping things transparent.

![Preference Storage Flow](./images/preferce_storing.png)

### Preferences in Context

On every turn, as part of `prepare_message_with_history`, all stored preferences are loaded from the preference store and rendered as XML tags inside a `<user_preferences>` block. Each preference is rendered with its ID and source so the interaction agent knows whether it was user-requested or self-inferred. This block sits at the top of the assembled message — before conversation history, before active agents, before the current turn — giving it high positional weight in the context so the LLM is more likely to attend to these preferences when generating its response.

The interaction agent's system prompt instructs it to let these preferences influence its behaviour and, importantly, to pass relevant preferences along in its instructions to execution agents. So if a user has a preference for formal tone in emails and asks OpenPoke to draft one, the interaction agent should include that tone requirement in the instructions it sends to the execution agent handling the draft.

![Preferences Injected into Context](./images/adding_preferences_to_context.png)

