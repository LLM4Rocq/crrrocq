# CRRRocq

CRRRocq stands for C(hain of thoughts) R(etrival Assisted Generation) R(ecursive) Rocq (the interactive theorem prover).
In a nutshell, CRRRocq combines chain of thoughts with RAG and tool calling to generate proof in interaction with the Rocq prover.
 and the SSReflect tactic language.
We focus on the math-comp library, the most advanced mathematics library formalized in Rocq
We train the model to reason using the SSReflect tactic language which is 1) more specialized than vanilla Rocq tactics, 2) less common in the Rocq ecosystem (fewer examples).

## Challenges

- Interface the model with the prover using tool calling
- Break reasoning in multiple subgoals and recursively apply the subgoal
- Few available data (math-comp or proofs using SSReflect)

## Tasks
- [] Generate the dataset for the RAG (search tool)
- [] Build the RAG
- [] Inference pipeline with tool calling
- [] Generate the dataset for CoT with tool calling
- [] Train the model following the S1 paper (1000 well chosen examples)
- [] Test / Benchmarks

## Workflow

Here is a example 


## Training

## Benchmarks

