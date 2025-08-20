(** source https://www-sop.inria.fr/teams/marelle/MC-2022/exercise4.v*)

From elpi Require Import elpi.
From HB Require Import structures.
From mathcomp Require Import all_ssreflect.

Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(** # This is the <a href="https://math-comp.github.io/htmldoc_2_0_alpha1/mathcomp.ssreflect.seq.html">doc of seq</a>, use it! #*)

(**

----
Exercise 1: 
    - look up the documentation of [take] and [drop]
    - prove this by induction (mind the recursive argument)
*)
Lemma cat_take_drop T n (s : seq T) : take n s ++ drop n s = s.
Proof.
Admitted.

(** Exercise 2:
   - look at the definition of [take] and [size] and prove the following lemma
   - the proof goes by cases (recall the spec lemma [leqP])
*)
Lemma size_take T n (s : seq T) :
  size (take n s) = if n < size s then n else size s.
Proof.
Admitted.

(** Exercise 3:
    - another proof by cases 
    - remark that also [eqP] is a spec lemma
*)
Lemma takel_cat T n (s1 s2 : seq T) :
  n <= size s1 -> take n (s1 ++ s2) = take n s1.
Proof.
Admitted.

(** Exercise 4:
    - Look up the definition of [rot]
    - Look back in this file the lemma [cat_take_drop] 
    - can you rewrite with it right-to-left in the right-hand-side of the goal? 
*)
Lemma size_rot T n (s : seq T) : size (rot n s) = size s.
Proof.
Admitted.

(** Exercise 5:
    - which is the size of an empty sequence?
    - Use lemmas about [size] and [filter] 
*)
Lemma has_filter (T : eqType) a (s : seq T)  : has a s = (filter a s != [::]).
Proof.
Admitted.

(** Exercise 6:
    - prove that by induction 
*)
Lemma filter_all T a (s : seq T) : all a (filter a s).
Proof. 
Admitted.

(** Exercise 7:
  - prove that view (one branch is by induction) 
*)
Lemma all_filterP T a (s : seq T) :
  reflect (filter a s = s) (all a s).
Proof.
Admitted.

(** Exercise 9:
    - prove this by induction on [s] 
*)
Lemma allP (T : eqType) (a : pred T) (s : seq T) :
  reflect (forall x, x \in s -> a x) (all a s).
Proof.
Admitted.

(** *** Exercise 10:
  - check out the definitions and theory of [leq] and [maxn]
  - use only [rewrite] and [apply]
  - proof sketch:
<<
   n <= m = n - m == 0
          = m + n - m == m + 0
          = maxn m n == m
>> *)
Lemma maxn_idPl m n : reflect (maxn m n = m) (m >= n).
