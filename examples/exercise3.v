(** source https://www-sop.inria.fr/teams/marelle/MC-2022/exercise3.v*)

From elpi Require Import elpi.
From HB Require Import structures.
From mathcomp Require Import all_ssreflect.

Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
(**
  ----
  ** Exercise 1 *)

(**
Try to define a next function over 'I_n that correspond to the
successor function over the natural plus the special case that
"n -1" is mapped to zero

Hint: potentially useful theorems are: [ltn_neqAle], [ltnS], [negbT], [ifP]

Hint: potentially useful tactics are [case], [move], [rewrite]

Hint: you may also need to use the val function (or \val notation) *)

Definition onext n (x : 'I_n) : 'I_n.
Proof.
refine (
(* sub takes two arguments: a value and a proof *)
  sub
(* Write the valued in the following line *)

(* Leave _ for the proof, you will fill it in by tactics later *)
_
(* more precisely: sub must have two arguments, the second one being _ *)
).
(* Finish the proof with the Defined keyword, so that we can compute this
  function in tests afterward. *)
Defined.

(** These should return 3 and 0 respectively. *)
Eval compute in val (onext (Ordinal (isT : 2 < 4))).
Eval compute in val (onext (Ordinal (isT : 3 < 4))).

(**
  ----
  ** Exercise 2
*)

(**
   Show that injectivity is decidable for a function [f : aT -> rT]
   when [aT] is a finite type.

   As a first step, we exhibit a boolean formulation of injectivity:
   a boolean formula, based on boolean "forall", "exists", and "==>" and
   boolean equality, which expresses the property of injectivity.

   We then show that this boolean formula is equivalent to th existing notion
   of [injective], which is not injective in general.
*)

Module MyInj.

Check injective.

Definition injectiveb (aT : finType) (rT : eqType) (f : aT -> rT) : bool :=

Lemma injectiveP (aT : finType) (rT : eqType) (f : aT -> rT) :
  reflect (injective f) (injectiveb f).
Proof.
apply: (iffP forallP).
Admitted.

End MyInj.
(**
  ----
  ** Exercise 3

  Build a function that maps an element of an ordinal to another element
  of the same ordinal with a p subtracted from it.

  Hint: if [i] has type ['I_n], then [i] can also be used for type [nat]
  and [i < n] is given by theorem [ltn_ord].  Others potentially useful
  theorems are [leq_ltn_trans] and [leq_subr]
*)

Lemma neg_offset_ord_proof n (i : 'I_n) (p : nat) : i - p < n.
Proof.
Admitted.

Definition neg_offset_ord n (i : 'I_n) p := Ordinal (neg_offset_ord_proof i p).

Eval compute in (val (neg_offset_ord (Ordinal (isT : 7 < 9)) 4)).

(**
  ----
  ** Exercise 4
*)

(**
   Prove the following statement by induction in several ways.
   - a proof by induction
   - a proof by reorganization:
<<
     2 * (1 + 2 ... + n) = (1 + 2 ... + (n - 1) + n) +
                           (n + (n - 1) ... + 2 + 1)
                         =  (1 + n) + (2 + n - 1) +
                              ... + (n + 1)
                         = n * (1 + n)
>>
   - Two variants of proof by reorganization are possible: one using
     [neg_offset_ord], the other using [rev_ord]

   Hint: potentially useful theorems: [big_ord0], [big_ord_recr],
     [doubleD], [muln2], [mulnDr], [addn2], [mulnC], [leq_trans],
     [ltnS], [leq_subr], [neg_offset_ord], [reindex_inj], [ord_max],
     [val_eqP], [eqP], [subKn], [ltnS], [big_split], [eqxx], [subnK],
     [eq_bigr], [sum_nat_const], [card_ord], [rev_ord_inj], [subSS]
 *)

Lemma gauss_ex_p1 : forall n, (\sum_(i < n) i).*2 = n * n.-1.
Proof.
Admitted.

Lemma gauss_ex_p2 : forall n, (\sum_(i < n) i).*2 = n * n.-1.
Proof.
Qed.

Lemma gauss_ex_p3 : forall n, (\sum_(i < n) i).*2 = n * n.-1.
Proof.
Admitted.

(**
  ----
  ** Exercise 5
*)

(**
   Try to formalize the following problem
*)

(**
  Given a parking  where the boolean indicates if the slot is occupied or not
*)

Definition parking n := 'I_n -> 'I_n -> bool.

(**
   Number of cars at line i
*)

Definition sumL n (p : parking n) i := \sum_(j < n) p i j.

(**
   Number of cars at column j
*)

Definition sumC n (p : parking n) j := \sum_(i < n) p i j.

(**
   Show that if 0 < n there is always two lines, or two columns, or a column and a line
   that have the same numbers of cars
*)

(* Two intermediate lemmas to use injectivity  *)

Lemma leq_sumL n (p : parking n) i : sumL p i < n.+1.
Proof.

Admitted.

Lemma leq_sumC n (p : parking n) j : sumC p j < n.+1.
Proof.
Admitted.

Lemma inl_inj {A B} : injective (@inl A B). Proof. by move=> x y []. Qed.
Lemma inr_inj {A B} : injective (@inr A B). Proof. by move=> x y []. Qed.

Lemma result n (p : parking n) : 0 < n ->
  exists i, exists j,
   [\/  (i != j) /\ (sumL p i = sumL p j),
        (i != j) /\ (sumC p i = sumC p j) | sumL p i = sumC p j].
Proof.
Admitted.


(**
  ----
   ** Exercise 6
*)

Lemma sum_odd1 : forall n, \sum_(i < n) (2 * i + 1) = n ^ 2.
Proof.
Admitted.

(**
  ----
  ** Exercise 7
*)

Lemma sum_exp : forall x n, x ^ n.+1 - 1 = (x - 1) * \sum_(i < n.+1) x ^ i.
Proof.
Admitted.

(**
  ----
 ** Exercise 8
*)

(** Prove the following statement by induction and by using a similar trick
   as for Gauss noticing that n ^ 3 = n * (n ^ 2) *)

Lemma bound_square : forall n, \sum_(i < n) i ^ 2 <= n ^ 3.
Proof.
Admitted.

(**
  ----
  ** Exercise 9

  Prove the following statement using only big operator theorems.
  [big_cat_nat], [big_nat_cond], [big_mkcondl], [big1]
*)
Lemma sum_prefix_0 (f : nat -> nat) n m : n <= m ->
  (forall k, k < n -> f k = 0) ->
  \sum_(0 <= i < m) f i = \sum_(n <= i < m) f i.
Proof.
Admitted.

(**
  ----
  ** Exercise 10
*)

(**
  building a monoid law
*)

Section cex.

Variable op2 : nat -> nat -> nat.

Hypothesis op2n0 : right_id 0 op2.

Hypothesis op20n : left_id 0 op2.

Hypothesis op2A : associative op2.

Hypothesis op2add : forall x y, op2 x y = x + y.

HB.instance Definition _ := Monoid.isLaw.Build nat 0 op2 op2A op20n op2n0.

Lemma ex_op2 : \big[op2/0]_(i < 3) i = 3.
Proof.
Admitted.

End cex.