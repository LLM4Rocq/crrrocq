# Math-comp tutorial

## Definition: `pose` Tactic

**Purpose:** adds local definitions to proof context with enhanced syntax and features.

**Use cases:**
- **Simple constants:**
  ```coq
  pose t := x + y.  (* open syntax, no parentheses needed *)
  ```
- **Functions:**
  ```coq
  pose f x y := x + y.
  (* Creates: f := fun x y : nat => x + y : nat -> nat -> nat *)
  ```
- **Recursive functions:**
  ```coq
  pose fix f (x y : nat) {struct x} : nat :=
    if x is S p then S (f p y) else 0.
  ```
- **Corecursive functions:**
  ```coq
  pose cofix f (arg : T) := ...
  ```
- **Wildcard abstraction:**
  ```coq
  pose f := _ + 1.
  (* Equivalent to: pose f n := n + 1. *)
  ```
- **Mixed wildcards:**
  ```coq
  pose f x := x + _.
  (* Equivalent to: pose f n x := x + n. *)
  (* Note: wildcard abstractions appear first in parameter order *)
  ```
- **Polymorphic functions:**
  ```coq
  pose f x y := (x, y).
  (* Creates: pose f (Tx Ty : Type) (x : Tx) (y : Ty) := (x, y). *)
  (* Automatic handling of implicit arguments and dependent types *)
  ```

## Abbreviation: `set` Tactic

**Purpose:** creates abbreviations by introducing a defined constant for a subterm in the goal/context.

- **Basic Syntax:**
  ```coq
  set ident := term.
  set ident : type := term.
  ```
- **Open Syntax & Wildcards:**
  ```coq
  set t := f _.     (* Creates: t := f x : nat where f x appears in goal *)
  set t := _ + _.   (* Matches any addition, creates: t := x + y : nat *)
  ```
- **Occurrence Selection:** control which occurrences to replace using `{occ_switch}`:
  ```coq
  set x := {+1 3}(f 2). (* Only replaces 1st and 3rd occurrences of f 2 *)
  set x := {1 3}(f 2).  (* Equivalent to above *)
  set x := {-2}(f 2).   (* Replaces all occurrences except the 2nd *)
  set x := {+}(f 2).    (* All occurrences - explicit *)
  set x := {-}(f 2).    (* No occurrences - definition only *)
  ```
- **Pattern Matching Algorithm:** sophisticated matching with head symbol comparison:
  ```coq
  set t := _ x.                           (* Matches any function applied to x, e.g., Nat.add x *)
  set t := (let g y z := S y + z in g) 2. (* Matches let expressions with partial application *)
  ```
  Note: pattern is found first, then occurrences selected
- **Localization with `in`:** define abbreviations in specific context entries:
  ```coq
  set z := 3 in Hx.   (* Folds z in hypothesis Hx only *)
  set z := 3 in Hx *. (* Folds z in hypothesis Hx and in goal *)
  ```

## Basic Tactics

SSReflect emphasizes **explicit bookkeeping** over automatic name generation to improve proof script readability and maintainability.

**Goal Structure (Stack View):**
Think of goals as a stack: variables and assumptions piled on a conclusion:
```
forall (xl : Tl) ...,     <- variables (top of stack)
let ym := bm in ... in    <- local definitions
Pn -> ... ->              <- assumptions
C                         <- conclusion (bottom)
```

**Core tacticals: `:` and `=>`:**
- **The `:` tactical (Push to stack):**
  Moves context elements TO the goal (pushes onto stack):
  ```coq
  move: m le_n_m.
  (* Pushes m and le_n_m from context to goal variables *)
  ```
- **The `=>` tactical (Pop from stack):**
  Moves goal elements TO the context (pops from stack):
  ```coq
  move=> m n le_n_m.
  (* Pops goal variables/assumptions to context as m, n, le_n_m *)
  ```
- **Combined usage:**
  ```coq
  move: m le_n_m => p le_n_p.
  (* Simultaneously rename m->p and le_n_m->le_n_p *)

  elim: n m le_n_m => [|n IHn] m => [_ | lt_n_m].
  (* Complex branching with multiple moves *)
  ```
- **The `move` tactic:**
  Essentially a **placeholder** for `:` and `=>` tacticals:
  ```coq
  move=> m n le_n_m.     (* just introduction *)
  move: m le_n_m.        (* just generalization *)
  ```

**Enhanced basic tactics:**
SSReflect redefines `case`, `elim`, `apply` to:
- Operate on **first variable/constant** of goal
- **Not use/change** proof context
- Require `:` tactical to operate on context elements
```coq
elim: n.           (* operates on n, removes it from context *)
elim=> [|n IHn].   (* direct elimination on top goal variable *)
```

## `move` Tactic

**Purpose:** a "smart" placeholder tactic that performs minimal goal normalization and serves as a foundation for bookkeeping.

**Detective form: `move`**
- If goal allows introduction (product or `let...in`): does **nothing** (`idtac`)
- Otherwise: performs **head normal form** (`hnf`)

```coq
(* Goal: ~ False *)
move.
(* Goal: False -> False *)
(* hnf applied since ~False = False -> False *)
```

**Primary Usage:**
Typically combined with bookkeeping tacticals `:` and `=>`: `move` alone rarely used - it's a **foundation** for SSReflect's bookkeeping system.

## `case` Tactic

**Purpose:** performs primitive case analysis on the **top variable/assumption** of the goal.

**Basic Behavior:**
- Destructs top variable/assumption
```coq
(* Goal (x, y) = (1, 2) -> G *)
case.
(* Goal: x = 1 -> y = 2 -> G *)
```
- Automatically handles `False` premises:
```coq
(* Goal False -> G *)
case.
(* Goal proved - False elimination applied *)
```

**Usage with Tacticals:**
```coq
case=> x y.           (* case + introduction *)
case: H.              (* case on hypothesis H *)
case: H => [|x] y.    (* case on H with branching intro *)
```

## `elim` Tactic

**Purpose:** performs inductive elimination on inductive types.

**Usage with Tacticals:**
```coq
elim=> [|n IHn].             (* elim + immediate case split *)
elim: n.                     (* elim on specific variable n *)
elim: n => [|n IHn].         (* elim on n + case intro *)
elim: n m H => [|n IHn] m H. (* complex elimination with moves *)
```

## `apply` Tactic

**Purpose:** main backward chaining tactic - applies a term to the current goal.

**Basic Syntax:**
```coq
apply term.
apply: term.  (* SSReflect style - operates on goal top *)
apply.        (* Try applying the top assumption on the goal with wildcards *)
```

**Usage with Tacticals:**
```coq
apply: lemma.                   (* apply lemma to goal *)
apply: lemma => H1 H2.          (* apply + handle new assumptions *)
apply: (lemma arg1 arg2).       (* apply with explicit arguments *)
apply: lemma arg1 _ arg3.       (* mix explicit args and wildcards *)
```

**Special behavior on goals containing existential Prop metavariables:**
try solving wildcards with a trivial tactic, it generates a goal if the trivial tactic fails.

## Discharge Tactical `:`

**Purpose:** generalizes terms from context to goal before applying a tactic.

**Compatible tactics:** `move`, `case`, `elim`, `apply`, `exact`, `congr`, and view applications (`/`).

**Discharge items:**
- **Basic discharge:**
  ```coq
  move: n m H.       (* generalizes H, then m, then n *)
  case: H.           (* generalizes hypothesis H, then cases on it *)
  elim: n.           (* generalizes n, then does induction *)
  apply: H x y.      (* generalizes y, then x, then H, then applies H *)
  ```
- **Occurrence selection with `{occ_switch}`:**
  ```coq
  move: {2}n.        (* generalizes only 2nd occurrence of n *)
  move: {1 3}n.      (* generalizes 1st and 3rd occurrences *)
  move: {-2}n.       (* generalizes all except 2nd occurrence *)
  ```
- **Clear switches `{ident+}`:**
  ```coq
  move: n {H1 H2}.   (* generalizes n and clears H1, H2 from context *)
  case: H {n}.       (* cases on H and clears n *)
  ```

**Processing order:**
For `tactic: d_item1 d_item2 ... d_itemN`:
1. Generalize `d_itemN` (rightmost first)
2. Generalize `d_item(N-1)`
3. ...
4. **Apply tactic** (after generalizing d_item1)
5. Clear specified items

**Example:**
```coq
move: n {2}n (refl_equal n).
```
1. Generalizes `(refl_equal n : n = n)`
2. Generalizes 2nd occurrence of `n`
3. Generalizes remaining occurrences of `n` and clears `n` from context
4. Result: `forall n n0 : nat, n = n0 -> G`

**Clear rules:**
- **Automatic clear:** constants/facts are cleared by default unless:
  - An `occ_switch` is used: `move: {2}n` (doesn't clear n)
  - Parentheses are used: `move: (n)` (doesn't clear n)
- **Clear failures:** if term appears in other facts or if cleared identifier not in context
- **Local definitions:**
  - Default: generalized as variables (not definitions)
  - Preserve as definition: prefix with `@`: `move: @n`

**`apply` / `exact` matching:** special matching algorithm: for `apply:` and `exact:`, wildcards are interpreted using the type of the first discharge item = no occurrence switches needed - type-guided matching handles this automatically.
```coq
Lemma test (Hfg : forall x, f x = g x) a b : f a = g b.
apply: trans_equal (Hfg _) _.
(* Applies transitivity with Hfg a on left, leaves g a = g b *)
```

## Abstract Tactic

**Purpose:** assigns a type to abstract constants created with `[: ident]` intro pattern.

**Workflow:**
1. Create abstract constant: use `[: abs]` intro pattern
2. Goal with abstract: context shows `abs : <hidden>`
3. Assign with abstract: use `abstract: abs terms...`
4. Propagate type: other goals see `abs : forall terms ..., goal` in context

## Introduction Tactical `=>`

**Purpose:** introduces variables, assumptions, definitions from goal to context with enhanced pattern matching.

**Processing:** executes tactic first, then processes i_items left to right.

**Simplification items:**
```coq
move=> //.       (* solve trivial subgoals with 'done' *)
move=> /=.       (* simplify goal with 'simpl' *)
move=> //=.      (* combine: simpl; try done *)
case=> {IHn}//.  (* solve subgoals, then clear IHn from remaining *)
```

**Views:**
- **Standard views:**
  ```coq
  move=> /term.           (* interpret top of stack with view 'term' *)
  move=> {}/v.            (* apply view v and clear v from context *)
  move=> /ltac:(tactic).  (* execute arbitrary tactic *)
  ```
- **Built-in ltac views:**
  ```coq
  move=> /[dup].     (* duplicate top of stack *)
  move=> /[swap].    (* swap two top elements *)
  move=> /[apply].   (* apply top to next element *)
  ```

**Intro patterns:**
- **Basic introduction:**
  ```coq
  move=> ident.      (* introduce as named constant/fact/definition *)
  move=> ?.          (* introduce with generated name *)
  move=> _.          (* introduce anonymously, then delete *)
  move=> *.          (* introduce all remaining variables/assumptions *)
  ```
- **Advanced patterns:**
  ```coq
  move=> >.          (* pop all variables in the stack *)
  move=> + y.        (* temporarily introduce, discharge at end *)
  ```
- **Rewriting patterns:**
  ```coq
  move=> ->.         (* rewrite goal with top assumption (left-to-right) *)
  move=> <-.         (* rewrite goal with top assumption (right-to-left) *)
  move=> {2}->.      (* rewrite only 2nd occurrence *)
  ```
- **Destructuring patterns:**
  ```coq
  (* Branching (first pattern after non-move tactic) *)
  case=> [H1 | H2 H3].     (* branch on subgoals from case *)
  elim=> [|n IHn].         (* branch on base/inductive cases *)

  (* Destructuring (not first pattern, or after move) *)
  move=> [a b].            (* destruct pair into a, b *)
  move=> -[H1 H2].         (* explicit destructuring with - *)
  ```
- **Abstract constants:**
  ```coq
  move=> [: abs1 abs2].    (* introduce abstract constants *)
  ```
- **Block introduction:**
  ```coq
  move=> [^ x].            (* destruct and prefix all names with 'x' *)
  move=> [^~ x].           (* destruct and suffix all names with 'x' *)
  ```

**Clear behavior:**
```coq
move=> {H}ident.         (* clear H, introduce ident *)
move=> {}H.              (* replace H (clear old, introduce new) *)
move=> {H1 H2}ident.     (* clear H1, H2, introduce ident *)
```
Note: all clears happen at the end of the intro pattern.

**Key patterns and equivalences:**
- **Destructuring equivalences:**
  ```coq
  move=> [a b].    (* casual pair splitting *)
  case=> [a b].    (* explicit case analysis *)
  case=> a b.      (* same as above *)
  ```
- **Forced branching:**
  ```coq
  case=> [] [a b] c.        (* force branching interpretation *)
  move=> [[a b] c].         (* nested destructuring *)
  ```
- **Separator usage:**
  ```coq
  move=> /eqP-H1.          (* explicit view-name link *)
  move=> /v1-/v2.          (* separate views with - *)
  ```

**Common idioms:**
- **Case analysis with immediate intro:**
  ```coq
  case=> [|n] //.          (* case, solve first subgoal immediately *)
  elim=> [|n IHn] H /=.    (* induction with assumption and simplify *)
  ```
- **View with rewrite:**
  ```coq
  move=> /eqP->.           (* apply eqP view, then rewrite *)
  ```
- **Multiple operations:**
  ```coq
  case=> {H1}[a b]/= H2 //.   (* case, clear H1, destruct, simplify, intro H2, solve *)
  ```

**Generation of equations:** stores definitions as equations instead of transparent definitions.
```coq
move En: (size l) => n.
(* Replaces size l with n in goal, adds En : size l = n to context *)

case E: a => [|n].
(* Goal 1: adds E : a = 0 *)
(* Goal 2: adds E : a = S n *)
```

## Control Flow

**Iteration tactical `do`:** control repetition of tactics with precise multipliers.
```coq
(* Multipliers: *)
do 3! rewrite lemma.              (* Rewrite exactly 3 times *)
do ! case: H.                     (* Case analysis until no more possible, at least once *)
do ? simpl.                       (* Simplify as much as possible, possibly zero times *)
do 2? rewrite mult_comm.          (* Rewrite at most 2 times *)

(* Sequence: *)
do [contradiction | discriminate | auto].    (* Try tactics in sequence *)
```
Note: multipliers integrate with `rewrite` tactic syntax and can be used with any tactic that supports repetition

**Terminators:**
- **`done` tactic:** solves trivial goals using a combination of basic tactics.
- **`by` tactical:** turns any tactic into a closing tactic that must solve the goal completely.
  ```coq
  by tactic.                        (* = tactic; done.)
  by apply: lemma.                  (* Apply lemma and close *)
  by [].                            (* = done. *)
  by [tactic1 | tactic2 | ...].     (* = do [done | by tac1 | by tac2 | ...] *)
  by [contradiction | auto].        (* Try contradiction, then auto *)
  by rewrite lemma1; apply lemma2.  (* = (rewrite lemma1; apply lemma2); done. The tactic list after by is treated as a single block *)
  ```
- **`exact` variants:**
  ```coq
  exact.          (* = do [done | by move=> top; apply top]. *)
  exact: lemma.   (* = by apply: lemma. *)
  ```

**Selectors:**
- **`first` and `last`:** apply tactic to specific subgoals only.
  ```coq
  tactic; first by closing_tactic.   (* Solve first subgoal *)
  tactic; last by closing_tactic.    (* Solve last subgoal *)
  ```
- **`first last` / `last first`:** invert subgoal order.
- **Rotation:**
  ```coq
  last n first.          (* Rotate: subgoal n becomes first *)
  first n last.          (* Rotate: subgoal n becomes first *)
  ```
- **Branch-specific tactics:**
  ```coq
  last k [tactic1 | ... | tacticm] || tacticn.
  (* Applies `tactic1` to (n-k+1)-th goal *)
  (* Applies `tacticm` to (n-k+m)-th goal *)
  (* Applies `tacticn` to the (n-k+m+1)-th goal to the (n-1)-th goal *)
  ```

**Localization tactical `in`:** applies tactics to specific hypotheses and/or goal.
- **Syntax:**
  ```coq
  tactic in ident1 ident2 ... *.
  ```
  - `ident` - apply the tactic to these hypotheses
  - `*` - also apply the tactic to goal (optional)
- **Compatible tactics:** `move`, `case`, `elim`, `rewrite`, `set`, `do`
- **Advanced localization:**
  ```coq
  tactic in (ident).               (* Clear body of local definition *)
  tactic in (y := x).              (* Generalize x, reintroduce as y *)

  rewrite lemma in H1 (@var := pattern) H2 *. (* Pattern matching in context *)
  ```

## `have` Tactic

**Purpose:** main SSReflect forward reasoning tactic for asserting intermediate results.

**Basic syntax:**
  ```coq
  have: term.                      (* Opens subproof for term *)
  have ident: term.                (* Assert term, name it ident *)
  have ident: term by tactic.      (* Assert and prove immediately *)
  have ident := proof_term.        (* Provide explicit proof *)
  ```
- **Subproof mode:** `have: term`
  - Creates two subgoals:
    1. Prove `term` in current context
    2. Prove original goal with `term` as top assumption
  - Creates β-redex at proof-term level
  - Automatically abstracts holes and implicit arguments
  ```coq
  have: _ * 0 = 0.                 (* Expands to: forall n : nat, n * 0 = 0 *)
  have: forall x y, (x, y) = (x, y + 0).  (* Abstracts type of x *)
  ```
- **Explicit proof mode:** `have ident := term`
  - Creates assumption of type `type of term`
  - Body of constant is lost to user
  - Abstracts non-inferred implicit arguments and holes

**Advanced syntax:**
```coq
have H x (y : nat): 2 * x + y = x + x + y. (* With binders *)
(* Creates: H : forall x y : nat, 2 * x + y = x + x + y *)

have (x) : 2 * x = x + x.                  (* Hypothesis name is not specified and bound variables can be surrounded with parentheses to avoid ambiguity *)

have H23: 3 + 2 = 2 + 3 by rewrite addnC.  (* The proof is provided immediatly with by *)

have ->: forall x, x * a = a.              (* Rewrite goal immediately *)

have [x Px]: exists x : nat, x > 0.        (* Destructure the obtained hypothesis *)

have {x} ->: x = y.                        (* Clear x, rewrite with equality *)
```

**Transparent definitions - `@` modifier:**
```coq
have @i: True by exact I.
(* Creates: i := I : True *)

have [:abs] @i: True by abstract: abs; exact I.
(* Creates: abs : True (*1*) and i := abs : True *)

have [:abs] @i: True := abs.
(* Leaves subgoal to prove what abs should be *)

have [:abs] @i P: P -> True by abstract: abs P; move=> _; exact I.
(* Creates: abs : (forall P: Type, P -> True) (*1*) and i := abs : forall P : Type, P -> True *)
```

**Typeclass resolution control:**
```coq
have foo: ty.         (* Full inference for ty, proof of ty needed *)
have foo: ty := .     (* No inference, unresolved instances quantified, proof of ty needed *)
have foo: ty := t.    (* No inference for ty and t, nothing needed *)
have foo := t.        (* No inference for t, instances quantified in the inferred type of t, nothing needed *)
```

**`suff` modifier:** "It suffices to show" reasoning
```coq
(* Need to prove G *)
have suff H: P.
(* Goal 1: need to prove P -> G *)
(* Goal 2: H : P -> G and need to prove G *)
```

**`gen` / `generally` modifier:**
```coq
gen have H, i_pattern: vars / P. (* = wlog suff i_pattern: vars / P; last first. and names the hypothesis H before it behing process by i_pattern *)
(* H: general hypothesis name *)
(* i_pattern: processes the instance *)
(* vars: generalize this list of variables *)
(* P: hypothesis introduced *)
```

## `suff` / `suffices` Tactic

**Purpose:** "suffices to show" variant of `have` with inverted subgoal order.
- Same syntax as `have`
- Inverted subgoal order compared to `have`
- Clear operations performed in second branch
```coq
(* Need to prove G *)
suff H: P.
(* Goal 1: H : P and need to prove G *)
(* Goal 2: need to prove P *)

(* Need to prove G *)
suff have H: P.
(* Goal 1: H : P and need to prove G *)
(* Goal 2: need to prove (P -> G) -> G *)
```

## `wlog` / `without loss` Tactic

**Purpose:** "without loss of generality" reasoning with automatic generalization.
```coq
(* Need to prove G *)
wlog: / P.
(* Goal 1: need to prove (P -> G) -> G *)
(* Goal 2: need to prove P -> G *)

(* x1, x2 : nat and need to prove G *)
wlog : x1 x2 / P.            (* Generalize x1 and x2 in the first subgoal *)
(* Goal 1: x1, x2 : nat and need to prove forall x3 x4 : nat, (P -> G) -> G *)
(* Goal 2: x1, x2 : nat and need to prove P -> G *)

wlog {H}: / P.               (* Clear H in the second subgoal *)

wlog: @x y / P.              (* Keep body of local definition of x *)

wlog H: / P.                 (* Introduce P as hypothesis H in the second subgoal *)

(* Need to prove G *)
wlog suff: / P.              (* Simpler form *)
(* Goal 1: need to prove P -> G *)
(* Goal 2: need to prove P *)
```

## `rewrite` Tactic

**Purpose:** unified rewriting functionality with enhanced control and chaining capabilities.
```coq
rewrite lemma.                     (* Basic rewriting *)
rewrite -lemma.                    (* Reverse direction *)
rewrite {2}lemma.                  (* Only 2nd occurrence *)
rewrite {1 3}[_ + 0]lemma.         (* Rewrite 1st and 3rd occurrence of _ + 0 *)
rewrite [x + y]lemma.              (* Pattern: rewrite only x + y with lemma *)

rewrite /definition.               (* Unfold definition *)
rewrite -/definition.              (* Fold definition *)
rewrite -[term1]/term2.            (* Convert term1 to term2 *)

rewrite (_ : pattern = result).    (* Anonymous lemmas: inline proof obligation *)
rewrite (_ : _ * 0 = 0).           (* Creates n * 0 = 0 subgoal: proves the specific instance used *)
rewrite (_ : forall x, x * 0 = 0). (* Creates forall x, x * 0 = 0 subgoal: general statement *)

rewrite /my_def {2}[f _]/= my_eq //=.  (* Unfold my_def, simplify 2nd occurrence of the first subterm matching pattern [f _], rewrite my_eq, simplify, try done *)

rewrite ?lemma.                    (* Apply as many times as possible, possibly zero *)
rewrite !lemma.                    (* Apply as many times as possible, at least once *)
rewrite 3!lemma.                   (* Exactly 3 times *)
rewrite 2?lemma.                   (* At most 2 times *)
```

**Multi-rule rewriting:**
```coq
rewrite (rule1, rule2, rule3).    (* = do [rewrite rule1 | rewrite rule2 | rewrite rule3]. First applicable rules win. *)

Definition multirule := (rule1, (rule2, rule3), rule4).
rewrite multirule.                (* Grouping doesn't affect selection *)
rewrite (=~ multirule).           (* Reverse all rules in multirule *)
rewrite 2!multirule.              (* Apply best rule twice *)
```

## `under` Tactic

**Purpose:** Rewriting under binders with extensionality support.
```coq
under extensionality_lemma => intro_patterns do tactic. (* One-liner mode *)
under extensionality_lemma do tactic.                   (* One-liner mode with the default intro pattern *)
under extensionality_lemma => intro_patterns.           (* Interactive mode *)
```

**Features:**
- Creates protected goals with `'Under[...]` notation
- Prevents accidental evar instantiation
- Requires `over` to complete

**Interactive mode:**
```coq
(* Goal: sumlist (map (fun m => m - m) l) = 0 *)
under eq_map => m.                (* Start under-rewriting *)
(* Goal: 'Under[ m - m ] *)
  rewrite subnn.                  (* Rewrite in protected context *)
(* Goal: 'Under[ 0 ] *)
over.                             (* Finish and apply *)
(* Goal: sumlist (map (fun _ => 0) l) = 0 *)
```

**One-liner mode:**
```coq
under eq_map => m do rewrite subnn. (* Equivalent to interactive mode above *)
```

## `over` Tactic

**Purpose:** Close `'Under[...]` goals.
```coq
over.                             (* Reflexivity-based closing *)
by rewrite over.                  (* Alternative syntax *)
```

## Locking and Unlocking

**Purpose:** Control term evaluation and simplification.

### Locked Definitions

**Basic locking:**
```coq
Definition locked A := let: tt := master_key in fun x : A => x.
Lemma lock : forall A x, x = locked x :> A.
```

**Usage:**
```coq
rewrite {2}[cons]lock /= -lock.   (* Lock, simplify, unlock *)
```

**Global locking:**
```coq
Definition lid := locked (fun x : nat => x).
unlock lid.                       (* Remove lock *)
```

### `nosimpl` Notation

**Purpose:** Prevent automatic simplification except in forcing contexts.

**Syntax:**
```coq
Notation "'nosimpl' t" := (let: tt := tt in t).
```

**Example:**
```coq
Definition addn := nosimpl plus.  (* Blocks automatic reduction *)
(* addn (S n) m won't auto-simplify to S (addn n m) *)
```

**Best practice:**
```coq
Definition foo x := nosimpl bar x.  (* Tag function, not application *)
```

## `congr` Tactic

**Purpose:** Robust congruence simplification for function applications.

**Syntax:**
```coq
congr natural? term.
```

### Basic Usage

**Function congruence:**
```coq
congr f.                          (* f x1 = f y1 → x1 = y1 *)
congr (_ + _).                    (* x + y = z + w → x = z, y = w *)
```

**Implication handling:**
```coq
congr (_ = _) : H.                (* P -> Q with P = Q *)
```

**Example:**
```coq
(* Goal: f 0 x y = g 1 1 x y *)
congr plus.                       (* Matches plus in both sides *)
(* No subgoals - automatically solved *)
```

### Advanced Features

**Dependent arguments:**
- Supports dependent function applications
- Dependent args must be identical on both sides
- Parameters should appear as first arguments

**Wildcard patterns:**
```coq
congr (_ + (_ * _)).              (* Match structure, generate subgoals *)
```

**Forced argument count:**
```coq
congr 3 f.                        (* Force exactly 3 argument equalities *)
```

### Common Patterns

**Arithmetic simplification:**
```coq
congr S; rewrite -/plus.          (* S m + n = S k → m + n = k *)
```

**Complex term matching:**
```coq
congr (_ + (_ * _)).
(* x + y * z = a + b * c → x = a, y = b, z = c *)
```

## Key Rewriting Idioms

**One-liner forward reasoning:**
```coq
rewrite -{1}[n]lemma1 lemma2 lemma3.
```

**Conditional simplification:**
```coq
rewrite /= ?lemma //.             (* Simplify, maybe rewrite, try done *)
```

**Occurrence-specific rewriting:**
```coq
rewrite {1 3}[pattern]lemma.      (* Only 1st and 3rd occurrences *)
```

**Chain with clearing:**
```coq
rewrite {}H1 lemma H2 //.         (* Use and clear H1 *)
```

**Extensional rewriting:**
```coq
under eq_map => x do rewrite lemma.  (* Rewrite under function binder *)
```

**Flag:** `SsrOldRewriteGoalsOrder` - controls subgoal ordering (default: side conditions first)
