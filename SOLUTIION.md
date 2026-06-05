# General Magic Take Home

The aim of this assignment was  two fold: 

1. Fix the agent overload issue related to the uncontrolled growth of execution agents 
2. Add a new AI feature, with a focus on creativity/usefulness 

This short README will give a brief but detailed decription on the approach to achieving both goals. 


## Fixing Agent Overload Issues 

The issue to fix here is as the roster of execution agent grow they begin to overload the context of the agent since the active agents are inserted into the messages of the LLM call at every turn in the ```prepare_message_with_history``` function. Interestingly the blog authors claim that semantic search is a naive solution is not necessarily correct. Semantic search (depending on how its implemented of course) is actually a really robust and useful solution to the problem as it is the best way to filter possible agents to a relevnat and provide those as agents to be rendered as part of message preperation with history. With this in mind my proposed and implemented solution works as follows:

### Embeddings, Search Space and Roster

A new embedding store is added to the application, along with an update to the schema of the roster (updated from just agent name to a list of dicts containing name and last_interacted) to facilitate this idea 

#### Execution Agent Creation and Reuse
When an execution agent is created by the interaction agent and added to the roster a new embedding is added to the embedding store, this entry includes the agent name, the instruction used for the agent and the vector. The vector data itself is created using a small OpenRouter embedding model and contains the ```[agent name] | [agent insruction]```

Whenever an agent is resused (found to already be in the roster) the agent embeddings are updated, for updating the embeddings, a sliding window of the three most recent intsructions along with the agent name are used for the embedding, this allows the semantic search to bias towards what the agent has most recently done, improving relevancy of results. 

This all happens async, to prevent blocking the event loop and adding uneeded latency. This can cause a very very narrow edge case whereby a user sends a message that requires an execution agent and the embedding store has not been updated so semantic search may not return that agent as part of the search. To combat this we also pull a set of k most recent interacted with agents from the roster and merge them with what semantic search returns when necessary to meet our quota of k results for rendering the agents (this will be explained in the next section where we go through the flow of how the agents are rendered)

![Embedding and Agent Search Flow](images/embedding_diagram.png)



