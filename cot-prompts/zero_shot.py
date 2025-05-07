prompt = r"""
Your task is to simulate realistic training data for a model designed to perform mathematical proofs in the MathComp style, based on an already known proof, and the corresponding sequence of intermediate goals and tactics. Your simulation will create structured "reasoning blocks," reflecting genuine, incremental reasoning aligned with the provided proof sequence. Each block of reasoning should realistically employ one or more of the following tools available to the model:

- Execute a block of proof script: to progress towards or modify the current goal.
- Perform a search (IR): to retrieve helpful lemmas or theorems from a corpus based on informal descriptions.
- Define and prove an intermediate lemma: if necessary to simplify the current goal or support the reasoning.

For each reasoning block, adhere strictly to the following structured format:

<think>
[Explicitly describe your inner reasoning, capturing uncertainty and incremental thought processes. Discuss your analysis of the current goal, potential approaches, the reasoning behind considering certain lemmas or script executions, or the rationale behind defining an intermediate lemma. PRETEND THAT YOU DO NOT KNOW THE NEXT TACTIC OR THE COMMENTS. In particular, do not explain the next tactic but simulate its discovery. 

To guide you we added the tag SEARCH ...listing the lemmas used in the next tactics. Insert a search block to retrieve these lemma for each SEARCH comment. Again, you need to pretend that you discovered these lemmas. DO NOT DIRECTLY REFER TO THE SEARCH TAG IN THE TEXT.]
</think>

<search>
[The search block contains an informal query to find a lemma from the corpus. Write what you would type if you didn't know the name of the lemma.]
</search>

<result>
[Lemma(s) retrieved from the search engine. Direclty copy the content of the result block of the input.]
</result>

<think>
[If applicable; an additional reasoning step to explain how you can use these Lemmas in a script or a tactic.]
</think>

<script>
[If applicable: exact script instruction applied (e.g., Coq/SSReflect tactic).]
</script>

<result>
[New context and goal(s) as given by the environment — these are not to be predicted, only output what the environment would reveal after the script is run.]
</result>

Repeat this structured approach clearly for each subsequent tactic, explicitly simulating the reasoning process based on the provided goal and next known tactic.

Guidelines:

- Context for each reasoning block: clearly consider the provided theorem statement, the current goal, the known tactic sequence, and previous steps already performed.
- Detailed reasoning: ensure your inner thought process is detailed, realistic, and incremental. Simulate genuine exploration, including dead-ends, uncertainties, and corrections in thinking if applicable.
- Tool usage justification: clearly justify why you're choosing a particular tool (script execution, search, or lemma definition) based explicitly on the provided next tactic step.
- Search specifics: when using search, formulate an informal query clearly reflecting your uncertainty or the type of result you're seeking.
- Intermediate lemmas: if defining a lemma, clearly explain why it simplifies or helps your reasoning process.
- Realistic constraints: simulate realistic limitations — acknowledge explicitly when certain lemmas might not be available, when searches fail, or when script executions lead to unexpected results.
- This structured simulation is crucial as it will serve as the training dataset for a model learning incremental, realistic proof reasoning using MathComp.

Ready?
Here is the input.

"""