"""Mémoire persistante pour Mammouth AI.

Trois notions distinctes, stockées ensemble mais gérées séparément :

- Le "contexte de base" (voir const.CONF_BASE_CONTEXT) est écrit par
  l'utilisateur dans les options de l'intégration, comme les instructions
  personnalisées d'un Projet Claude ou d'un Mammouth personnalisé. Stable,
  contrôlé par l'humain, pas géré ici (lu directement depuis les options).
- Les "souvenirs" (facts) sont appris automatiquement par le modèle via
  l'outil remember_fact pendant les conversations. Peu nombreux, changent
  rarement : écriture immédiate.
- L'"historique" (threads) est le fil de conversation par utilisateur.
  Change à chaque message : écriture DIFFÉRÉE et fusionnée (voir plus bas)
  pour éviter d'écrire sur disque à chaque tour.

On utilise Store, l'API standard de Home Assistant pour ce genre de petites
données (écriture atomique, versionnage intégré), déjà utilisée par le
registre d'entités et des centaines d'intégrations core et custom.

Coût disque maîtrisé par construction :
- Un seul fichier JSON par entrée de configuration (pas un fichier par outil
  ou par utilisateur).
- Historique plafonné par fil (MAX_HISTORY_MESSAGES) ET nombre de fils
  plafonné (MAX_THREADS, éviction du plus ancien) : la taille du fichier a
  un plafond dur, elle ne grossit pas indéfiniment avec l'usage.
- Écritures de l'historique différées via Store.async_delay_save : plusieurs
  mises à jour rapprochées (ex: une conversation avec plusieurs allers-retours
  d'outils) sont fusionnées en une seule écriture disque, au lieu d'une par
  tour. C'est le même mécanisme utilisé par le registre d'entités de HA pour
  des données qui changent souvent.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
MAX_FACTS = 200
MAX_HISTORY_MESSAGES = 20  # par fil, donc ~10 tours user+assistant
MAX_THREADS = 50  # nombre de fils (utilisateurs) conservés au total
HISTORY_SAVE_DELAY = 5  # secondes ; fusionne les écritures rapprochées


class MammouthMemory:
    """Charge/sauvegarde la mémoire persistante d'une entrée de configuration."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}_memory"
        )
        self._facts: list[dict[str, str]] = []
        self._threads: dict[str, list[dict]] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Charge la mémoire depuis le disque (une seule fois, puis mise en cache)."""
        if self._loaded:
            return
        data = await self._store.async_load() or {}
        self._facts = data.get("facts", [])
        self._threads = data.get("threads", {})
        self._loaded = True

    def _data_to_save(self) -> dict[str, Any]:
        """Snapshot des données à écrire (appelé au moment de l'écriture différée)."""
        return {"facts": self._facts, "threads": self._threads}

    # -- Souvenirs (facts) : peu fréquents, écriture immédiate -------------

    async def async_list_facts(self) -> list[dict[str, str]]:
        await self.async_load()
        return list(self._facts)

    async def async_add_fact(self, text: str) -> dict[str, Any]:
        if not text or not text.strip():
            return {"error": "Le contenu du souvenir ne peut pas être vide."}

        await self.async_load()
        fact = {"id": uuid.uuid4().hex[:8], "text": text.strip()}
        self._facts.append(fact)

        # FIFO : on garde les souvenirs les plus récents pour éviter une
        # croissance illimitée du prompt système au fil du temps.
        if len(self._facts) > MAX_FACTS:
            self._facts = self._facts[-MAX_FACTS:]

        await self._store.async_save(self._data_to_save())
        return {
            "success": True,
            "id": fact["id"],
            "message": "Souvenir enregistré durablement, il sera rappelé dans les prochaines conversations.",
        }

    async def async_remove_fact(self, fact_id: str) -> dict[str, Any]:
        await self.async_load()
        before = len(self._facts)
        self._facts = [f for f in self._facts if f["id"] != fact_id]

        if len(self._facts) == before:
            return {"error": f"Souvenir {fact_id} introuvable."}

        await self._store.async_save(self._data_to_save())
        return {"success": True, "message": f"Souvenir {fact_id} oublié."}

    def facts_as_prompt_block(self) -> str:
        """Rendu texte des souvenirs, à injecter dans le prompt système.

        Doit être appelé après async_load()/async_list_facts() pour refléter
        le contenu actuel.
        """
        if not self._facts:
            return ""
        lines = "\n".join(f"- {fact['text']}" for fact in self._facts)
        return (
            "\n\n---\nSouvenirs retenus des conversations précédentes (à réutiliser, "
            "mais à revérifier avec les outils de lecture en cas de doute) :\n" + lines
        )

    # -- Historique de conversation (threads) : fréquent, écriture différée -

    async def async_get_history(self, thread_key: str) -> list[dict]:
        await self.async_load()
        return list(self._threads.get(thread_key, []))

    async def async_save_history(self, thread_key: str, history: list[dict]) -> None:
        """Met à jour l'historique d'un fil et programme une écriture différée.

        Plusieurs appels rapprochés (même thread ou threads différents) sont
        fusionnés en une seule écriture disque après HISTORY_SAVE_DELAY
        secondes d'inactivité, plutôt que d'écrire à chaque message.
        """
        await self.async_load()

        self._threads[thread_key] = history[-MAX_HISTORY_MESSAGES:]

        # Éviction du fil le plus ancien si on dépasse la limite, pour que
        # la taille du fichier reste plafonnée même après des mois d'usage
        # avec plusieurs utilisateurs.
        if len(self._threads) > MAX_THREADS:
            oldest_key = next(iter(self._threads))
            if oldest_key != thread_key:
                del self._threads[oldest_key]

        self._store.async_delay_save(self._data_to_save, HISTORY_SAVE_DELAY)

    async def async_flush(self) -> None:
        """Force l'écriture immédiate (utile à l'arrêt de Home Assistant)."""
        if self._loaded:
            await self._store.async_save(self._data_to_save())
