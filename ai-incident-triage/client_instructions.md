# Implementation Task: OpenRouter Provider + Centralized LLM Client

## Objective

Implement OpenRouter support in the existing LLM architecture and create a common client utility layer that agents can use.

The project already has a provider-based LLM structure:

```text
app/
└── llm/
    ├── __init__.py
    ├── factory.py
    ├── structured_output.py
    └── providers/
        ├── __init__.py
        ├── anthropic.py
        ├── gemini.py
        ├── groq.py
        └── openai.py

Do NOT replace this architecture.

Extend it by adding:

app/llm/providers/openrouter.py
app/llm/client.py

The desired architecture is:

Environment
    ↓
app/config.py
    ↓
app/llm/client.py
    ↓
app/llm/factory.py
    ↓
app/llm/providers/openrouter.py
    ↓
OpenRouter
    ↓
Agents

The goal is to make agent development simple and centralized.

An agent should eventually be able to do:

from app.llm.client import create_agent

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
)

The agent should NOT need to know how OpenRouter is configured, how the API key is loaded, or how the underlying LLM client is initialized.

1. REQUIRED: Inspect the Repository First

Before modifying anything, inspect the existing repository.

At minimum inspect:

app/config.py
app/dependencies.py
app/llm/__init__.py
app/llm/factory.py
app/llm/structured_output.py
app/llm/providers/__init__.py
app/llm/providers/anthropic.py
app/llm/providers/gemini.py
app/llm/providers/groq.py
app/llm/providers/openai.py

Also inspect if present:

agents/
tests/
pyproject.toml
requirements.txt
.env
.env.example
env.example

Search the repository for existing LLM/agent initialization:

ChatOpenAI
ChatAnthropic
ChatGoogle
ChatGroq
OpenAI
create_agent
create_react_agent
OPENAI_API_KEY
ANTHROPIC_API_KEY
GROQ_API_KEY
GEMINI_API_KEY
OPENROUTER_API_KEY
api_key=
base_url=
model=

Determine:

How configuration currently works.
How the existing provider modules are structured.
How factory.py selects or creates providers.
How existing agents create LLMs.
How existing agents are constructed.
How structured output currently works.
Which LangChain/LangGraph versions are installed.
Which OpenAI-compatible packages are installed.
Which Python version the project supports.
Critical rule

Do NOT assume APIs from memory.

The existing repository and installed dependency versions are the source of truth.

2. Preserve Existing Provider Architecture

The repository already has:

app/llm/providers/

with:

anthropic.py
gemini.py
groq.py
openai.py

Do NOT delete these files.

Do NOT replace the existing provider architecture.

Add:

app/llm/providers/openrouter.py

The new provider must follow the same style/interface/pattern used by the existing providers.

For example, if existing providers expose:

get_model(...)

then OpenRouter should expose the equivalent.

If they use classes, factories, helper functions, or another pattern, follow the existing pattern.

Do not invent a second provider architecture.

3. OpenRouter Is the Provider Being Added

OpenRouter is the provider for this implementation.

OpenRouter provides an OpenAI-compatible API.

Use this fixed endpoint:

https://openrouter.ai/api/v1

The endpoint must NOT be configurable through an environment variable.

Do NOT add:

OPENROUTER_BASE_URL=

Do NOT add generic provider-selection environment variables such as:

LLM_PROVIDER=
PROVIDER=
OPENAI_BASE_URL=

unless such a mechanism already exists and is required by the current project architecture.

Do not create a new multi-provider abstraction.

4. Environment Variables

Only these two OpenRouter-specific environment variables are required:

OPENROUTER_API_KEY=
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
OPENROUTER_API_KEY

The user's OpenRouter API key.

Requirements:

Load it from the environment.
Never hard-code it.
Never commit a real key.
Never print it.
Never expose it in logs/errors.
OPENROUTER_MODEL

The default OpenRouter model.

Default:

deepseek/deepseek-v4-flash

The model must be configurable because individual agents may override the model when necessary.

5. Environment Example

Find the existing environment example convention.

If .env.example exists, update it.

Otherwise, if env.example exists, update it.

Otherwise create:

env.example

Add:

# OpenRouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=deepseek/deepseek-v4-flash

Preserve all existing unrelated environment variables.

Do NOT add:

OPENROUTER_BASE_URL=

Do not add any real credentials.

6. app/config.py

Create or update:

app/config.py

Use the project's existing configuration mechanism.

Do NOT create a second independent settings system.

Add configuration for:

openrouter_api_key
openrouter_model

Use the naming convention already used by the project.

The default model must be:

deepseek/deepseek-v4-flash

The OpenRouter API endpoint is fixed and should remain internal to the provider/client implementation:

https://openrouter.ai/api/v1

Do NOT load the endpoint from the environment.

The configuration flow should be:

OPENROUTER_API_KEY
        ↓
app/config.py
        ↓
OpenRouter provider

and:

OPENROUTER_MODEL
        ↓
app/config.py
        ↓
OpenRouter provider
7. Create app/llm/providers/openrouter.py

Create:

app/llm/providers/openrouter.py

This file is responsible for OpenRouter-specific LLM initialization.

It should handle:

OpenRouter API key
OpenRouter endpoint
OpenRouter model
OpenAI-compatible client/model initialization

It should NOT handle:

agent-specific prompts
agent-specific tools
business logic
application-specific behavior
graph/node logic

Follow the architecture and coding style of:

app/llm/providers/anthropic.py
app/llm/providers/gemini.py
app/llm/providers/groq.py
app/llm/providers/openai.py

Do not create unnecessary abstractions.

8. OpenRouter Provider Configuration

OpenRouter must use:

API key:
config.openrouter_api_key

Base URL:
https://openrouter.ai/api/v1

Default model:
config.openrouter_model

Use the existing OpenAI-compatible client/dependency already present in the project whenever possible.

Do NOT install an OpenRouter-specific SDK unless the current dependency stack genuinely cannot support OpenRouter.

The OpenRouter provider should be the only place, or one of the very few infrastructure places, that knows the OpenRouter endpoint.

Agents must never contain:

base_url="https://openrouter.ai/api/v1"

or:

api_key=os.getenv("OPENROUTER_API_KEY")
9. Default Model

The default model is:

deepseek/deepseek-v4-flash

It must come from:

OPENROUTER_MODEL

through:

app/config.py

Do NOT hard-code the model separately inside individual agents.

The intended flow is:

OPENROUTER_MODEL
        ↓
config.py
        ↓
openrouter.py
        ↓
LLM
10. Model Override

The model should be overridable at runtime.

For example:

llm = get_chat_model(
    model="some-other-openrouter-model"
)

or:

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
    model="some-other-openrouter-model",
)

The explicit function argument should take precedence over the configured default.

Do NOT introduce per-agent environment variables such as:

AGENT_A_MODEL
AGENT_B_MODEL
AGENT_C_MODEL
11. Update app/llm/factory.py

Inspect app/llm/factory.py before changing it.

Understand exactly how the current factory works.

Integrate OpenRouter using the existing provider pattern.

For example, if the existing factory has a provider mapping, add OpenRouter to that mapping.

If the existing API looks conceptually like:

get_llm("openai")

then OpenRouter should work through the equivalent existing mechanism:

get_llm("openrouter")

Only follow this example if it matches the actual existing API.

Do NOT rewrite the entire factory.

Do NOT remove the existing providers.

Do NOT create a competing factory.

12. Create app/llm/client.py

Create:

app/llm/client.py

This is the application-facing utility layer.

Its purpose is to provide common functions that multiple agents can use.

The client should hide:

OpenRouter configuration
API key loading
model initialization
provider-specific setup
common agent creation

The client should NOT contain:

business logic
agent-specific prompts
agent-specific tools
application-specific logic
13. Required Public Functions

Implement the following functions where compatible with the existing architecture:

get_client()
get_chat_model()
create_agent()
create_structured_agent()
chat_completion()
async_chat_completion()

Before implementing them, inspect the existing project for equivalent functionality.

If a function already exists elsewhere, reuse or wrap the existing implementation rather than creating duplicate logic.

14. get_client()

Provide a low-level OpenRouter client helper if appropriate for the existing architecture.

Conceptually:

def get_client():
    ...

It should use:

config.openrouter_api_key

and:

https://openrouter.ai/api/v1

If the existing provider already owns low-level client creation, get_client() should delegate to that provider rather than duplicate the configuration.

Prefer reuse.

15. get_chat_model()

Implement:

def get_chat_model(
    model: str | None = None,
    temperature: float = 0,
    **kwargs,
):
    ...

Behavior:

model supplied?
    yes → use supplied model
    no  → use config.openrouter_model

Example:

from app.llm.client import get_chat_model

llm = get_chat_model()

This should use:

deepseek/deepseek-v4-flash

by default.

The function must return the chat model type expected by the existing LangChain/LangGraph code.

16. create_agent()

This is the primary helper for normal agents.

Implement conceptually:

def create_agent(
    system_prompt: str,
    tools=None,
    model: str | None = None,
    **kwargs,
):
    ...

The implementation must use the project's existing LangChain/LangGraph agent creation mechanism.

Before implementing:

Inspect existing agents.
Inspect factory.py.
Inspect installed LangGraph/LangChain versions.
Determine the current agent creation API.
Implement the helper around that API.

Expected usage:

from app.llm.client import create_agent

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
)

It should:

create/use the OpenRouter chat model
accept a system prompt
accept optional tools
accept a model override
pass through appropriate configuration
return the expected agent object/type

Do not add business logic.

17. System Prompts

The client must NOT contain agent-specific prompts.

The individual agent owns its prompt:

SYSTEM_PROMPT = """
You are responsible for...
"""

Then:

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
)

Do not move prompts into client.py.

18. Tools

Tools belong to the individual agent.

The client only accepts them:

create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
)

Do not import agent-specific tools into client.py.

Do not create a global tool registry.

19. create_structured_agent()

Inspect:

app/llm/structured_output.py

before implementing this function.

If structured-output functionality already exists, reuse it.

Do NOT duplicate schema parsing/validation logic.

Conceptually:

def create_structured_agent(
    system_prompt: str,
    output_schema,
    model: str | None = None,
    **kwargs,
):
    ...

It should integrate with the project's existing structured-output implementation.

Use it for things such as:

classification
extraction
RCA reports
structured decisions
Pydantic output
schema-based responses

If the current architecture does not support the concept of a "structured agent", implement the simplest compatible wrapper around the existing structured-output functionality instead of inventing a new framework.

20. chat_completion()

Implement a lightweight synchronous helper if appropriate:

def chat_completion(
    messages,
    model: str | None = None,
    **kwargs,
):
    ...

It should:

Resolve the model.
Use OpenRouter.
Use centralized configuration.
Make the completion request.
Return the result expected by the current project/client stack.

Do not duplicate authentication or provider setup.

21. async_chat_completion()

If the repository uses async execution, implement:

async def async_chat_completion(
    messages,
    model: str | None = None,
    **kwargs,
):
    ...

Use the project's existing async-compatible client/model implementation.

Do not block the event loop with synchronous network calls.

If an equivalent async helper already exists, reuse it.

22. Existing Agents

Inspect all existing agent implementations.

Search for:

ChatOpenAI(
ChatAnthropic(
ChatGoogle(
ChatGroq(
OpenAI(

and:

OPENROUTER_API_KEY
os.getenv(
api_key=
base_url=
model=

Identify duplicated LLM initialization.

Where appropriate, migrate agents to:

from app.llm.client import get_chat_model

or:

from app.llm.client import create_agent

Example:

Before
llm = ChatOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    model="deepseek/deepseek-v4-flash",
)
After
from app.llm.client import get_chat_model

llm = get_chat_model()

Or for a normal agent:

from app.llm.client import create_agent

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
)

Do NOT change:

business logic
prompts
tools
graph state
node behavior

unless required to integrate the centralized client.

Do not perform unrelated refactoring.

23. Do Not Remove Existing Providers

Even though OpenRouter is being added, do NOT automatically remove:

anthropic.py
gemini.py
groq.py
openai.py

Do not rewrite all provider implementations.

The task is to add OpenRouter cleanly to the existing architecture.

Only remove existing provider code if repository evidence clearly shows it is obsolete AND removal is required/safe.

Otherwise leave it intact.

24. Error Handling

If:

OPENROUTER_API_KEY

is missing, produce a clear configuration error.

Example:

OPENROUTER_API_KEY is not configured.

Requirements:

Never print the API key.
Never log the API key.
Never include the API key in an exception.
Do not silently fall back to another provider.
25. Dependencies

Inspect:

pyproject.toml
requirements.txt

before adding dependencies.

Prefer existing dependencies.

OpenRouter should normally work through the existing OpenAI-compatible/LangChain integration.

Do NOT install an OpenRouter-specific SDK unless genuinely necessary.

Do NOT upgrade unrelated packages.

26. Tests

Inspect the existing test structure before adding tests.

Add focused tests for the new functionality.

At minimum verify:

Configuration
OPENROUTER_API_KEY is read correctly.
OPENROUTER_MODEL is read correctly.
Default model is deepseek/deepseek-v4-flash.
OpenRouter Provider
OpenRouter provider can construct the expected LLM/client.
OpenRouter endpoint is:
https://openrouter.ai/api/v1
Model override works.
Client
get_chat_model() works.
Default model is used.
Model override works.
create_agent() works without tools.
create_agent() works with tools.
System prompt is passed correctly.
Credentials
Missing API key produces a clear error.

Tests must NOT require a real OpenRouter API key.

Mock external API/network calls where appropriate.

27. Avoid Over-Engineering

Do NOT introduce:

provider registry
provider interface hierarchy
provider-selection framework
model registry
agent registry
dependency injection framework
configuration registry
retry framework
new OpenRouter SDK
multi-provider abstraction

unless the existing repository already uses such concepts.

The goal is a simple extension of the current architecture:

config.py
    ↓
llm/client.py
    ↓
llm/factory.py
    ↓
llm/providers/openrouter.py
    ↓
OpenRouter
28. Expected Final Structure

After implementation, the LLM directory should conceptually look like:

app/
└── llm/
    ├── __init__.py
    ├── factory.py
    ├── structured_output.py
    ├── client.py
    │
    └── providers/
        ├── __init__.py
        ├── anthropic.py
        ├── gemini.py
        ├── groq.py
        ├── openai.py
        └── openrouter.py

Do not force this exact structure if the repository has a slightly different established convention, but the important additions are:

app/llm/client.py
app/llm/providers/openrouter.py
29. Expected Agent Developer Experience

A normal agent should be able to use:

from app.llm.client import create_agent

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
)

A custom model should be possible:

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
    model="another-openrouter-model",
)

A plain chat model should be possible:

from app.llm.client import get_chat_model

llm = get_chat_model()

A structured agent should be possible where supported:

from app.llm.client import create_structured_agent

agent = create_structured_agent(
    system_prompt=SYSTEM_PROMPT,
    output_schema=MyOutputSchema,
)

Agents should NOT need to know:

OpenRouter URL
API key environment variable
OpenRouter client initialization
model configuration
provider-specific implementation details
30. Definition of Done

The task is complete only when:

 Existing LLM architecture was inspected before coding.
 Existing provider pattern was followed.
 app/llm/providers/openrouter.py was created.
 OpenRouter is integrated into the existing factory.py.
 Existing providers were preserved.
 app/config.py contains OpenRouter API key configuration.
 app/config.py contains OpenRouter model configuration.
 Default model is deepseek/deepseek-v4-flash.
 OpenRouter endpoint is fixed internally to https://openrouter.ai/api/v1.
 No OPENROUTER_BASE_URL environment variable was added.
 Only OPENROUTER_API_KEY and OPENROUTER_MODEL were added as OpenRouter environment variables.
 app/llm/client.py was created.
 get_client() is implemented where appropriate.
 get_chat_model() is implemented.
 create_agent() is implemented.
 create_structured_agent() is implemented where appropriate.
 chat_completion() is implemented where appropriate.
 async_chat_completion() is implemented where appropriate.
 Existing structured-output functionality was reused.
 Existing agents were inspected for duplicated LLM setup.
 Appropriate duplicated setup was migrated.
 No business logic was moved into client.py.
 No real API keys were committed.
 Relevant tests were added/updated.
 Tests were actually run.
 Relevant lint/type checks were actually run if available.
 No unrelated refactoring was introduced.
31. Required Final Response

After implementation, provide a concise report containing:

Files Changed

List every file created or modified.

OpenRouter Provider

Explain how:

app/llm/providers/openrouter.py

was implemented and how it integrates with factory.py.

Client API

List every public function in:

app/llm/client.py

and briefly explain each.

Environment

Confirm the OpenRouter environment variables:

OPENROUTER_API_KEY
OPENROUTER_MODEL

Confirm the default model:

deepseek/deepseek-v4-flash

Confirm that the endpoint is internally:

https://openrouter.ai/api/v1
Agent Migration

List the agents that were updated to use the centralized client.

If no agents needed migration, explain why.

Validation

List the exact commands executed for:

tests
lint
type checking
formatting

Report the actual results.

Do not claim a command passed unless it was actually executed.

Remaining Concerns

Mention any compatibility issues, assumptions, or remaining work.

32. FINAL REQUIRED OUTPUT

After ALL implementation, testing, linting, and validation is finished, the LAST line of your response MUST be exactly:

completed
