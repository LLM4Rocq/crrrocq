Require Import PeanoNat.
Import Nat.
From mathcomp Require Import all_ssreflect.

Definition EvenT n := { m | n = 2 * m }.
Definition OddT n := { m | n = 2 * m + 1 }.

Lemma EvenT_0 : EvenT 0.
Proof. 
by exists 0.
Qed.

Lemma EvenT_2 n : EvenT n -> EvenT (S (S n)).

Lemma OddT_1 : OddT 1.

Lemma OddT_2 n : OddT n -> OddT (S (S n)).

Lemma EvenT_S_OddT n : EvenT (S n) -> OddT n.

Lemma OddT_S_EvenT n : OddT (S n) -> EvenT n.

Lemma even_EvenT : forall n, even n = true -> EvenT n.

Lemma odd_OddT : forall n, odd n = true -> OddT n.

Lemma EvenT_Even n : EvenT n -> Even n.

Lemma OddT_Odd n : OddT n -> Odd n.

Lemma Even_EvenT n : Even n -> EvenT n.

Lemma Odd_OddT n : Odd n -> OddT n.

Lemma EvenT_even n : EvenT n -> even n = true.

Lemma OddT_odd n : OddT n -> odd n = true.

Lemma EvenT_OddT_dec n : EvenT n + OddT n.

Lemma OddT_EvenT_rect (P Q : nat -> Type) :
  (forall n, EvenT n -> Q n -> P (S n)) ->
  Q 0 -> (forall n, OddT n -> P n -> Q (S n)) -> forall n, OddT n -> P n.

Lemma EvenT_OddT_rect (P Q : nat -> Type) :
  (forall n, EvenT n -> Q n -> P (S n)) ->
  Q 0 -> (forall n, OddT n -> P n -> Q (S n)) -> forall n, EvenT n -> Q n.
