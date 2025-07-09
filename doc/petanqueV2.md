# PetanqueV2

## Installation

**rocq**:
```
$ opam install coq.8.20.0
$ opam repo add rocq-released https://rocq-prover.org/opam/released
```

**coq-lsp**:
```
$ opam install lwt logs
$ opam pin add coq-lsp https://github.com/ejgallego/coq-lsp.git#v8.20
```

**pytanque**:
```
$ uv pip install git+https://github.com/LLM4Rocq/pytanque.git@PetanqueV2
```

## New features

- the command `run(state, command)` replaces the command `run_tac(state, tac)`
- states now have a new field `feedback` containing all messages sent by Rocq when computing this state; one can find errors, warnings, results from `Search`, `Print`, ...
- the command `get_root_state(doc)` returns the first state of `doc`
- the command `get_state_at_pos(doc, line, char, offset)` returns the state at a given position
- the command `ast(state, command)` returns the AST of `command` parsed at `state`
- the command `ast_at_pos(doc, line, char, offset)` returns the AST at a given position
