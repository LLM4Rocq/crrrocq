# Custom pytanque and coq-lsp version

## Installation

**pytanque**:
```
$ uv pip install git+https://github.com/LLM4Rocq/pytanque.git@PetanqueV2-MoreCommands
```

**rocq**:
```
$ opam install coq.8.20.0
$ opam repo add rocq-released https://rocq-prover.org/opam/released
```

**coq-lsp**:
```
$ opam install lwt logs
$ opam pin add coq-lsp https://github.com/LLM4Rocq/coq-lsp.git#v8.20-MoreCommands
```

## New features

- the command `list_notations_in_statement(state, statement)` returns the list of notations appearing in the Rocq statetement `statement` run on `state`
