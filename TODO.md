# TODO

## Dataset V2

Entraîner le modèle à réagir aux erreurs de script et de have :
- générer des CoTs pour 1000 nouveaux exemples,
- choisir une tactic aléatoirement dans chaque preuve,
- donner la CoT jusqu'à cette tactique au modèle et lui demander d'écrire la suite,
- le faire jusqu'à ce qu'il génère une erreur (pas beaucoup d'itérations normalement ...),
- faire un court paragraphe réagissant à cette erreur,
- faire un court paragraphe corrigeant l'erreur au regard de la bonne tactique,
- rajouter la fin de la CoT générée pour avoir une entrée du dataset v2

Pour éviter de dépenser trop d'argent, attendre la version 2 de la génération de CoT

## Rocq Vanilla

Essayer de tester notre modèle sur Rocq Vanilla
pour voir ce qu'il donne avec du Rocq plus simple.

## Amélioration des searchs

Essayer de rendre les search plus compacte :
- mettre le kind dans les query de search (`Lemma`, `Definition`, `Notation`, ...),
- mettre le goal dans les query de search (my goal is ...), la difficulté est de trouver un bon modèle d'embedding qui marche bien pour des goals Rocq,
- regarder les objects sélectionnés par le LLM après une search et regarder leur position dans le résultat de la search, si par exemple 90% des objects sélectionnés par le LLM sont dans les 5 premiers résultats, alors on peut diminuer le nombre de résultats dans les outputs de search à 5

## Amélioration des CoTs

A faire :
- le LLM qui génère des CoTs doit écrire le résultat de ses blocks de search, par exemple :
  ```
  <search><the_lemma_I_search_for>
  A lemma stating that ...
  </search>
  ```
- un petit paragraph introductif dans le prompt (génération de CoT et inférence) qui parle des dépendances du statement et des notations du statement, et qui présente les variables globales (pour éviter qu'elles soient répétées dans chaque goal)
- on peut lâcher le statement Rocq (`Lemma my_lemma (hyp1 : ...) ... : goal.`) et seulement considérer des goals (`hyp1 : ...\n ... \n |- goal`)

Pistes d'amélioration :
- demander au LLM de plus parler des goals qu'il pense avoir. Par exemple, après avoir sélectionné un lemme après une search, le LLM devrait dire : "Nice the lemma `blabla` corresponds exactly to what I'm looking for. After rewriting with it, my goal should be ...". Cela lui permet de plus garder le fil de la preuve Rocq, ce qui est important pour du code mathcomp où beaucoup de goals intermédiaire apparaissent au sein d'une même tactique.

## Outils de définition

Dans mathcomp, il arrive que des définitions soient unfoldées (on remplace la définition par son contenu). Pour l'instant, on les traite comme des dépendances. Par exemple pour cette tactique de rewrite `rewrite /some_def some_lemma1 some_lemma2`, on demandera au LLM de faire des searchs pour trouver `some_def`, `some_lemma1` et `some_lemma2`. Or ce ne devrait pas être le cas pour des définitions : la définition à unfolder est déjà dans le goal, on ne veut pas que le LLM doive la trouver avec un block search.

C'est pourquoi il faudrait introduire un nouvel outil, l'outil `<definition>`. Cet outil serait assez simple à implémenter, le LLM devrait mettre le nom d'un object qu'il veut inspecter et on lui renverrait le résultat de `Print` de l'object.

Pour l'ajouter aux CoTs, il faudrait mettre des appels à cet outil à chaque fois qu'une définition est unfoldée. Je ne sais pas vraiment quoi faire dans le cas contraire, quand une définition est foldée (on remplace le contenu d'une définition par un appel à la définition). Je suppose que ce cas se présente lorsque l'on veut appliquer un lemme qui contient le nom de la définition plutôt que son contenu, mais alors le LLM qui génère les CoTs devrait d'abord chercher le lemme, ensuite print la définition qui apparait dedans avec `<definition>` puis dire qu'elle s'applique, et donc expliquer que pour écrire la tactique, il faut folder la définition puis appliquer le lemme. C'est possible à faire mais cela me semble compliqué et pourrait mener à des phases de search très longue. Dans un premier temps, on pourrait éviter les cas où on fold une définition.

