"""Routeur d'intentions de Formia.

Détermine ce que l'utilisateur veut faire à partir de son message et du
contexte de la conversation, sans appeler le LLM.

Règle du projet (§5.5) : chaque transition préserve les règles de validation
et de sécurité. Une intention n'est jamais une création : elle oriente le
graphe, qui décide ensuite s'il faut créer, clarifier ou rejeter.

Liens avec les autres fichiers
------------------------------
- agents/orchestrator.py : utilise cette classe pour choisir le chemin du graphe.
- agents/nodes.py        : reçoit l'intention pour adapter sa réponse.
- schemas/form.py        : fournit le modèle Form (pas d'import ici).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intention(str, Enum):
    """Intentions reconnues par le routeur."""

    NOUVELLE_IDEA = "nouvelle_idee"          # l'utilisateur a une idée de formulaire
    AJOUT_CONTEXTE = "ajout_contexte"        # il complète son brief existant
    MODIFICATION = "modification"            # il veut changer une partie
    DEMANDE_JUSTIFICATION = "demande_justification"  # il veut savoir pourquoi une question
    VALIDATION_EXPLICITE = "validation_explicite"    # il confirme la version présentée
    ANNULATION = "annulation"                # il abandonne l'opération en cours
    HORS_SUJET = "hors_sujet"                # demande sans rapport avec un formulaire


@dataclass(frozen=True)
class ResultatRoutage:
    """Résultat du routage, exploitable par le graphe et journalisable."""

    intention: Intention
    confiance: float  # 0.0 à 1.0
    raisons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class IntentRouter:
    """Route les messages vers une intention métier.

    Le routage repose sur des règles déterministes (mots-clés, expressions
    régulières et contexte de session). Cela évite un appel LLM pour une
    décision qui peut être prise localement : coût nul, latence faible, et
    comportement facile à expliquer et à tester.
    """

    # Seuils de confiance par intention. Une intention détectée avec un score
    # inférieur à son seuil est repliée sur HORS_SUJET ou AJOUT_CONTEXTE selon
    # le contexte.
    SEUILS_PAR_DEFAUT: dict[Intention, float] = {
        Intention.NOUVELLE_IDEA: 0.5,
        Intention.AJOUT_CONTEXTE: 0.4,
        Intention.MODIFICATION: 0.5,
        Intention.DEMANDE_JUSTIFICATION: 0.5,
        Intention.VALIDATION_EXPLICITE: 0.5,
        Intention.ANNULATION: 0.5,
        Intention.HORS_SUJET: 0.0,
    }

    # Mots qui indiquent une confirmation explicite (§4.3 : seule une
    # confirmation explicite déclenche la création).
    MOTS_VALIDATION = {
        "ok", "d'accord", "okay", "confirme", "confirmation", "valide",
        "validation", "c'est bon", "ça me va", "parfait", "bien", "fonce",
        "allez", "crée", "créez", "génère", "générez", "fais-le", "faites-le",
        "oui", "accepte", "acceptez",
    }

    # Mots qui indiquent une annulation.
    MOTS_ANNULATION = {
        "annule", "annulation", "stop", "arrête", "arret", "non", "oublie",
        "oubliez", "annulons", "abandonne", "annulé", "annulez",
    }

    # Mots qui indiquent une demande de justification.
    MOTS_JUSTIFICATION = {
        "pourquoi", "justifie", "justification", "d'où vient", "d ou vient",
        "origine", "suggérée", "suggerée", "recommandé", "recommande",
    }

    # Mots qui indiquent une modification ciblée (§5 : opération ciblée, pas
    # régénération complète non contrôlée).
    MOTS_MODIFICATION = {
        "change", "modifie", "remplace", "corrige", "modifiez", "changez",
        "corrigez", "intitulé", "intitule", "option", "supprime",
        "ajoute", "enleve", "enlever", "retirer",
    }

    # Mots qui indiquent un ajout de contexte (complète le brief).
    MOTS_AJOUT_CONTEXTE = {
        "en fait", "aussi", "ajoute", "précise", "precise", "en plus",
        "également", "egalement", "de plus", "notamment", "autre chose",
        "sinon", "peut-être", "peut etre",
    }

    # Mots qui indiquent une nouvelle idée (démarre un formulaire).
    MOTS_NOUVELLE_IDEA = {
        "formulaire", "form", "google forms", "créer", "creer", "générer",
        "generer", "concevoir", "nouveau", "nouvelle", "sondage", "quiz",
        "inscription", "réservation", "reservation", "candidature",
    }

    # Mots hors sujet typiques (liste non exhaustive, utilisée en dernier
    # ressort quand rien d'autre ne matche).
    MOTS_HORS_SUJET = {
        "météo", "meteo", "recette", "cuisine", "voiture", "voiture",
        "cinéma", "cinema", "film", "musique", "blague", "histoire",
        "poème", "poeme", "math", "calcul",
    }

    def __init__(
        self,
        seuils: dict[Intention, float] | None = None,
    ) -> None:
        """Crée un routeur avec des seuils personnalisables pour les tests."""
        self.seuils = dict(self.SEUILS_PAR_DEFAUT)
        if seuils:
            self.seuils.update(seuils)

    # ------------------------------------------------------------------
    # Point d'entrée public
    # ------------------------------------------------------------------

    def router(
        self,
        message: str,
        contexte: dict[str, Any] | None = None,
    ) -> ResultatRoutage:
        """Route un message utilisateur vers une intention.

        Paramètres
        ----------
        message : texte brut de l'utilisateur (non fiable, jamais exécuté).
        contexte : informations de session utiles au routage.
            Clés reconnues :
            - "a_formulaire_pret" : un formulaire est déjà généré et attendu.
            - "en_attente_confirmation" : le formulaire a été présenté.
            - "derniere_intention" : intention du tour précédent.
            - "a_deja_clarifie" : des questions de clarification ont été posées.

        Retourne un ResultatRoutage figé.
        """
        contexte = contexte or {}
        normalise = self._normaliser(message)

        scores: dict[Intention, float] = {}
        raisons: dict[Intention, list[str]] = {}

        # Chaque intention est évaluée indépendamment.
        scores[Intention.VALIDATION_EXPLICITE], raisons[Intention.VALIDATION_EXPLICITE] = self._evaluer_validation(
            normalise, contexte
        )
        scores[Intention.ANNULATION], raisons[Intention.ANNULATION] = self._evaluer_annulation(
            normalise
        )
        scores[Intention.DEMANDE_JUSTIFICATION], raisons[Intention.DEMANDE_JUSTIFICATION] = self._evaluer_justification(
            normalise
        )
        scores[Intention.MODIFICATION], raisons[Intention.MODIFICATION] = self._evaluer_modification(
            normalise, contexte
        )
        scores[Intention.AJOUT_CONTEXTE], raisons[Intention.AJOUT_CONTEXTE] = self._evaluer_ajout_contexte(
            normalise, contexte
        )
        scores[Intention.NOUVELLE_IDEA], raisons[Intention.NOUVELLE_IDEA] = self._evaluer_nouvelle_idee(
            normalise, contexte
        )

        # Choisir l'intention avec le meilleur score au-dessus de son seuil.
        meilleure_intention, meilleur_score = self._choisir_meilleure_intention(
            scores, raisons, contexte
        )

        # Contexte par défaut pour le journalisme et le debug.
        metadata = {
            "message_longueur": len(message),
            "scores": {k.value: round(v, 2) for k, v in scores.items()},
        }

        return ResultatRoutage(
            intention=meilleure_intention,
            confiance=meilleur_score,
            raisons=raisons.get(meilleure_intention, []),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Évaluateurs par intention (privés, faciles à tester unitairement)
    # ------------------------------------------------------------------

    def _normaliser(self, message: str) -> str:
        """Minuscule, accents simplifiés, espaces compressés."""
        message = message.lower().strip()
        remplacements = {
            "à": "a", "â": "a", "é": "e", "è": "e", "ê": "e", "ë": "e",
            "î": "i", "ï": "i", "ô": "o", "ù": "u", "û": "u", "ü": "u",
            "ç": "c", "œ": "oe", "æ": "ae",
        }
        for origine, remplace in remplacements.items():
            message = message.replace(origine, remplace)
        return re.sub(r"\s+", " ", message)

    def _contient_un_mot(self, texte: str, mots: set[str]) -> bool:
        """Vérifie qu'un mot de la liste apparaît comme mot entier."""
        for mot in mots:
            if re.search(rf"\b{re.escape(mot)}\b", texte):
                return True
        return False

    def _evaluer_validation(
        self, texte: str, contexte: dict[str, Any]
    ) -> tuple[float, list[str]]:
        """Confirmer la version présentée : seule une validation explicite crée."""
        raisons: list[str] = []
        score = 0.0

        if self._contient_un_mot(texte, self.MOTS_VALIDATION):
            score += 0.4
            raisons.append("mot de confirmation detecte")

        if contexte.get("en_attente_confirmation"):
            score += 0.4
            raisons.append("formulaire presente et en attente de confirmation")

        if contexte.get("a_formulaire_pret") and not contexte.get(
            "en_attente_confirmation"
        ):
            score += 0.1
            raisons.append("formulaire deja pret")

        return min(score, 1.0), raisons

    def _evaluer_annulation(self, texte: str) -> tuple[float, list[str]]:
        raisons: list[str] = []
        score = 0.0

        if self._contient_un_mot(texte, self.MOTS_ANNULATION):
            score += 0.6
            raisons.append("mot d'annulation detecte")

        return min(score, 1.0), raisons

    def _evaluer_justification(self, texte: str) -> tuple[float, list[str]]:
        """Demander pourquoi une question a été suggérée."""
        raisons: list[str] = []
        score = 0.0

        if self._contient_un_mot(texte, self.MOTS_JUSTIFICATION):
            score += 0.5
            raisons.append("mot de justification detecte")

        if re.search(r"\b(pour|quoi|comment)\b", texte):
            score += 0.1
            raisons.append("mot interrogatif detecte")

        return min(score, 1.0), raisons

    def _evaluer_modification(
        self, texte: str, contexte: dict[str, Any]
    ) -> tuple[float, list[str]]:
        """Modifier une partie ciblée du formulaire existant."""
        raisons: list[str] = []
        score = 0.0

        if self._contient_un_mot(texte, self.MOTS_MODIFICATION):
            score += 0.5
            raisons.append("mot de modification detecte")

        if contexte.get("a_formulaire_pret"):
            score += 0.2
            raisons.append("formulaire existant a modifier")

        # Une référence numérique (ex. "question 3") renforce la modification ciblée.
        if re.search(r"\bquestion\s*\d+\b", texte):
            score += 0.2
            raisons.append("reference a une question precise")

        return min(score, 1.0), raisons

    def _evaluer_ajout_contexte(
        self, texte: str, contexte: dict[str, Any]
    ) -> tuple[float, list[str]]:
        """Compléter le brief avec des informations supplémentaires."""
        raisons: list[str] = []
        score = 0.0

        if self._contient_un_mot(texte, self.MOTS_AJOUT_CONTEXTE):
            score += 0.4
            raisons.append("mot d'ajout de contexte detecte")

        if contexte.get("a_deja_clarifie"):
            score += 0.2
            raisons.append("clarification deja en cours")

        if len(texte.split()) >= 8:
            score += 0.1
            raisons.append("message relativement long")

        return min(score, 1.0), raisons

    def _evaluer_nouvelle_idee(
        self, texte: str, contexte: dict[str, Any]
    ) -> tuple[float, list[str]]:
        """Démarrer un nouveau formulaire."""
        raisons: list[str] = []
        score = 0.0

        if self._contient_un_mot(texte, self.MOTS_NOUVELLE_IDEA):
            score += 0.4
            raisons.append("mot de nouveau formulaire detecte")

        if not contexte.get("a_formulaire_pret"):
            score += 0.2
            raisons.append("aucun formulaire en cours")

        return min(score, 1.0), raisons

    # ------------------------------------------------------------------
    # Sélection finale
    # ------------------------------------------------------------------

    def _choisir_meilleure_intention(
        self,
        scores: dict[Intention, float],
        raisons: dict[Intention, list[str]],
        contexte: dict[str, Any],
    ) -> tuple[Intention, float]:
        """Retourne (intention, score) la plus pertinente au-dessus du seuil."""
        meilleure_intention = Intention.HORS_SUJET
        meilleur_score = 0.0

        for intention, score in scores.items():
            seuil = self.seuils.get(intention, 0.5)
            if score >= seuil and score > meilleur_score:
                meilleure_intention = intention
                meilleur_score = score

        # Si rien ne dépasse les seuils, classer selon le contexte.
        if meilleur_score == 0.0:
            if contexte.get("en_attente_confirmation") or contexte.get(
                "a_formulaire_pret"
            ):
                return Intention.AJOUT_CONTEXTE, 0.3
            return Intention.HORS_SUJET, 0.1

        # Si la meilleure est annulation ou validation, la privilégier même à
        # score égal (règles de sécurité : l'utilisateur doit pouvoir arrêter).
        if meilleure_intention in {
            Intention.ANNULATION,
            Intention.VALIDATION_EXPLICITE,
        }:
            return meilleure_intention, meilleur_score

        return meilleure_intention, meilleur_score
