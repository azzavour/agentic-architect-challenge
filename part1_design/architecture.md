AGENTIC CUSTOMER SUPPORT EMAIL SYSTEM
ARCHITECTURE
1.	Overview
The system processes incoming support emails through a pipeline of specialized agents rather than a single monolithic LLM call. This separation makes each stage independently testable, observable, and safe to fail.
2.	Pipeline
Step 1 : Guardrail/Router Agent (runs first, before drafting) 
Checks keyword + LLM intent signals for data loss, outage, or security breach, and looks up contact history for more than 3 contacts in 7 days. Either condition flags the email and routes it straight to a human, skipping drafting.
Step 2 : Classifier Agent
Reached only if not flagged. A single LLM call returns structured JSON (category, confidence, key entities) so downstream logic can branch reliably.
Step 3 : RAG Drafting Agent
Retrieves relevant chunks from the internal knowledge base and answers only from that context, explicitly refusing rather than guessing. A self-check step verifies the draft cites only retrieved facts.
Step 4 : Human Review Queue
Every draft passes through human review before anything is sent to the customer. This makes the system slower, but it is a safer choice for a first version of the product.
3.	Anti-Hallucination Controls 
RAG grounding (no answer without a source chunk), an explicit refusal instruction for unsupported questions, a draft self-verification pass, and human-in-the-loop review before sending refund or billing content.
4.	Trade-offs
Latency vs. safety: the guardrail and self-check add LLM calls and delay, but they prevent the two costliest failures missing a critical issue and inventing refund policy. Structured output vs. flexibility: forcing JSON reduces model freedom but keeps the system debuggable. Human review bottleneck: adds latency and cost, acceptable for a v1 given reputational risk, and can be relaxed later for high-confidence, low-risk categories.
5.	Failure Handling & Observability
Every agent call is logged with input, output, latency, and token cost. LLM calls use retries with exponential backoff; repeated failure defaults to human routing (fail-safe, not fail-open). Low classifier confidence auto-routes to human review. Tracked metrics: routing accuracy, draft acceptance rate, average handling time, and hallucinations caught by the self-check