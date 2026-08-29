"""Conversation support for Mammouth AI."""

from __future__ import annotations

import json
import logging
from typing import Literal

from homeassistant.components.conversation import (
    ChatLog,
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import intent, template

from .const import (CONF_BASE_CONTEXT, CONF_LLM_HASS_API, CONF_MAX_TOKENS,
                    CONF_PROMPT, CONF_TEMPERATURE, DEFAULT_MAX_TOKENS,
                    DEFAULT_PROMPT, DEFAULT_TEMPERATURE, DOMAIN)
from .coordinator import MammouthDataUpdateCoordinator
from .ha_tools import HA_TOOLS_SCHEMA, async_dispatch_tool
from .memory import MammouthMemory

_LOGGER = logging.getLogger(__name__)

# Nombre maximum d'aller-retours modèle <-> outils avant d'abandonner, pour
# éviter une boucle infinie si le modèle s'entête à appeler des outils.
MAX_TOOL_ITERATIONS = 8

# Nombre de tours conservés par fil : voir memory.MAX_HISTORY_MESSAGES,
# la troncature et la persistance sont gérées par MammouthMemory.

TOOLS_SYSTEM_SUFFIX = (
    "\n\n---\n"
    "Tu es aussi un assistant de configuration et de contrôle pour cette instance Home "
    "Assistant. Tu as accès à des outils pour :\n"
    "- explorer les zones, appareils et entités et leur état actuel ;\n"
    "- consulter les automatisations, scripts et dashboards déjà existants ;\n"
    "- créer, modifier ou supprimer des automatisations et des scripts (effet immédiat, sans redémarrage) ;\n"
    "- générer des dashboards ;\n"
    "- agir immédiatement sur un appareil (allumer/éteindre/basculer/régler) via call_service ;\n"
    "- mémoriser durablement une information avec remember_fact, pour t'en souvenir dans les "
    "conversations futures (pas seulement celle-ci).\n"
    "Règles à suivre :\n"
    "1. Base toujours tes réponses sur l'état réel de l'installation : utilise les outils de lecture "
    "avant de proposer, créer ou contrôler quoi que ce soit, ne suppose jamais l'existence d'une entité.\n"
    "2. Avant d'agir sur une entité ou de créer une automatisation/script, vérifie que l'entity_id existe "
    "réellement (via get_ha_overview, search_entities ou get_entity_details). Si une recherche dans un "
    "domaine ne donne rien, élargis avec search_entities SANS filtre de domaine avant de conclure que "
    "l'entité n'existe pas : elle peut être dans un domaine différent de celui attendu (ex: switch au "
    "lieu de light). Si un nom donné par l'utilisateur ne matche rien exactement, réessaie avec "
    "search_entities sur un mot-clé plus court (ex: 'cabanon' plutôt que la phrase complète) avant "
    "de dire que ça n'existe pas.\n"
    "2b. Dès que list_automations ou get_automation te donne un entity_id pour une automatisation, "
    "RÉUTILISE ce entity_id exact pour toute action suivante sur cette même automatisation (assign_entity_area, "
    "call_service...). Ne le redéduis JAMAIS toi-même en transformant l'alias en minuscules avec des "
    "underscores : Home Assistant peut générer un entity_id différent (accents, doublons, suffixe "
    "numérique). Si un entity_id que tu as déduit toi-même échoue, ne réessaie pas une autre variante "
    "déduite : rappelle get_automation ou list_automations pour obtenir le vrai entity_id.\n"
    "3. Distingue bien deux types d'actions :\n"
    "   a) Contrôle direct d'un appareil (call_service) : si l'ordre est clair et sans ambiguïté "
    "(« éteins X », « allume Y »), exécute-le tout de suite, sans redemander confirmation.\n"
    "   b) Changement de configuration (create_automation, update_automation, delete_automation, "
    "create_script, create_dashboard, assign_entity_area) : décris D'ABORD précisément ce que tu "
    "vas faire (quoi, sur quelle entité/zone/automatisation) et attends une confirmation EXPLICITE "
    "de l'utilisateur pour CE changement précis, sauf si sa demande initiale nommait déjà "
    "exactement cette action. Un « oui » donné à « veux-tu que je regarde/analyse ? » n'est PAS "
    "une confirmation pour agir ensuite : ça n'autorise que la lecture, pas la modification.\n"
    "4. Quand on te demande des suggestions d'amélioration ou d'automatisation, explore d'abord "
    "l'instance pour proposer des idées pertinentes et concrètes plutôt que génériques.\n"
    "5. Après toute création, modification ou action, résume clairement ce qui a été fait (nom, "
    "entity_id, effet) en langage simple.\n"
    "6. Si un outil retourne une erreur, explique-la à l'utilisateur et corrige ta requête si possible.\n"
    "7. Tu as accès à l'historique de cette conversation : ne redemande pas une information que "
    "l'utilisateur ou toi-même avez déjà donnée plus haut dans l'échange.\n"
    "8. Utilise remember_fact pour retenir durablement : une correction de l'utilisateur sur ta "
    "configuration (ex: 'le plafonnier du bureau est un switch, pas une light'), une préférence "
    "exprimée, ou un fait stable sur l'installation. N'utilise PAS remember_fact pour un état "
    "temporaire (une lumière allumée/éteinte change tout le temps, ce n'est pas un souvenir utile) "
    "ni pour une information déjà présente dans le contexte de base ci-dessus.\n"
    "9. Ne dis JAMAIS qu'une action a réussi (créée, modifiée, assignée, supprimée, exécutée) sans "
    "avoir réellement appelé l'outil correspondant et reçu un résultat avec success:true. S'il "
    "n'existe aucun outil pour faire ce qu'on te demande, dis-le clairement plutôt que d'affirmer "
    "l'avoir fait.\n"
    "10. Si tu découvres qu'un entity_id ne correspond pas à ce qu'on pourrait naïvement déduire du "
    "nom (ex: suffixe numérique inattendu, domaine surprenant), retiens cette correspondance avec "
    "remember_fact pour ne pas avoir à la rechercher à chaque fois dans les prochaines conversations.\n"
    "11. get_automation ne fait que LIRE et ne corrige jamais le fichier réel sur disque : si son "
    "résultat contient schema_issue_on_disk: true, la config a un vrai problème non résolu, même si "
    "l'affichage te semble propre. Pour réellement corriger, appelle update_automation sur cette "
    "automatisation (même sans changer aucun champ) — lui seul réécrit le fichier. Ne dis jamais "
    "qu'un problème de configuration est résolu sur la seule base d'un get_automation ou "
    "list_automations qui a réussi : ce sont des lectures, pas des réparations."
)

MEMORY_TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": (
                "Enregistre durablement une information apprise pendant cette conversation, pour "
                "t'en souvenir dans TOUTES les conversations futures, pas seulement celle-ci. "
                "Utilise ceci pour les corrections de l'utilisateur, ses préférences, ou des faits "
                "stables sur son installation. Ne pas utiliser pour un état temporaire (une lumière "
                "allumée/éteinte change tout le temps, ce n'est pas un souvenir utile)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Le fait à retenir, en une phrase claire et autonome.",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_remembered_facts",
            "description": "Liste tout ce qui a été retenu durablement des conversations précédentes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "Supprime un souvenir précis par son id (voir list_remembered_facts).",
            "parameters": {
                "type": "object",
                "properties": {"fact_id": {"type": "string"}},
                "required": ["fact_id"],
            },
        },
    },
]


class MammouthConversationEntity(ConversationEntity):
    """Mammouth AI conversation entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MammouthDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = f"Mammouth AI ({config_entry.title})"
        self._attr_unique_id = config_entry.entry_id

        # Mémoire persistante : souvenirs auto-appris ET historique de
        # conversation par utilisateur, stockés sur disque via le Store
        # natif de Home Assistant (voir memory.py pour les détails de
        # coût/persistance).
        self._memory = MammouthMemory(hass, config_entry.entry_id)

        if config_entry.options.get(CONF_LLM_HASS_API, False):
            self._attr_supported_features = ConversationEntityFeature.CONTROL

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return "Powered by Mammouth AI"

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return list of supported languages."""
        return MATCH_ALL

    async def _async_handle_message(
        self, user_input: ConversationInput, chat_log: ChatLog
    ) -> ConversationResult:
        """Handle a conversation message."""
        intent_response = intent.IntentResponse(language=user_input.language)

        # Fil de conversation basé sur la PERSONNE, pas sur la fenêtre/session :
        # tant que c'est le même utilisateur HA, l'historique continue, qu'on
        # ferme et rouvre une fenêtre Assist ou qu'on en ouvre une nouvelle.
        # Un conversation_id est quand même retourné (protocole HA), mais on
        # l'aligne sur ce même identifiant plutôt que sur celui, éphémère,
        # fourni par la fenêtre.
        if user_input.context and user_input.context.user_id:
            thread_key = f"user_{user_input.context.user_id}"
        else:
            # Pas d'utilisateur identifié (ex: appel automatisé) : un seul
            # fil partagé, à défaut de mieux.
            thread_key = "anonymous"

        conversation_id = user_input.conversation_id or thread_key

        # Obtenir le prompt système
        system_prompt = self._config_entry.options.get(
            CONF_PROMPT, DEFAULT_PROMPT
        )

        tools_enabled = self._config_entry.options.get(CONF_LLM_HASS_API, False)

        # Si l'option d'accès à Home Assistant est activée, traiter les templates
        # et enrichir le prompt avec les instructions liées aux outils.
        if tools_enabled:
            try:
                # Obtenir les informations utilisateur
                user_name = "Utilisateur"
                if user_input.context and user_input.context.user_id:
                    user = await self.hass.auth.async_get_user(
                        user_input.context.user_id
                    )
                    if user and user.name:
                        user_name = user.name

                # Rendre le template avec les variables HA
                system_prompt = template.Template(
                    system_prompt, self.hass
                ).async_render(
                    {
                        "ha_name": self.hass.config.location_name,
                        "user_name": user_name,
                    },
                    parse_result=False,
                )
            except TemplateError as err:
                _LOGGER.error("Error rendering prompt template: %s", err)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Erreur de template: {err}",
                )
                return ConversationResult(
                    response=intent_response,
                    conversation_id=conversation_id,
                )

            system_prompt += TOOLS_SYSTEM_SUFFIX

            await self._memory.async_load()
            system_prompt += self._memory.facts_as_prompt_block()

        # Le contexte de base (défini par l'utilisateur, façon "Projet" ou
        # "Mammouth personnalisé") s'applique toujours, indépendamment de
        # l'accès aux outils Home Assistant.
        base_context = (self._config_entry.options.get(CONF_BASE_CONTEXT) or "").strip()
        if base_context:
            system_prompt += (
                "\n\n---\nContexte de base défini par l'utilisateur pour cet assistant "
                "(à respecter comme un cadre stable) :\n" + base_context
            )

        # Historique propre (sans tool_calls) de cette conversation, lu
        # depuis la mémoire persistante (survit aux redémarrages).
        history = await self._memory.async_get_history(thread_key)

        # Construire les messages pour l'API : system + historique + message courant
        messages: list[dict] = (
            [{"role": "system", "content": system_prompt}]
            + list(history)
            + [{"role": "user", "content": user_input.text}]
        )

        tools = (HA_TOOLS_SCHEMA + MEMORY_TOOLS_SCHEMA) if tools_enabled else None

        # Ces réglages existent dans le formulaire d'options depuis le début,
        # mais n'étaient jamais transmis à l'API : ils n'avaient aucun effet.
        extra_params = {
            "max_tokens": self._config_entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
            "temperature": self._config_entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
        }

        _LOGGER.debug("Sending request to Mammouth AI: %s", user_input.text)

        try:
            response_text = await self._async_run_conversation(messages, tools, extra_params)
            _LOGGER.debug("Received response from Mammouth AI: %s", response_text)
            intent_response.async_set_speech(response_text)

            # Mettre à jour l'historique propre (uniquement les tours finaux,
            # jamais les tool_calls intermédiaires) ; la troncature et
            # l'écriture différée sont gérées par MammouthMemory.
            history = history + [
                {"role": "user", "content": user_input.text},
                {"role": "assistant", "content": response_text},
            ]
            await self._memory.async_save_history(thread_key, history)

        except HomeAssistantError as err:
            _LOGGER.error("Error processing conversation: %s", err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Erreur de l'assistant Mammouth: {err}",
            )

        return ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )

    async def _async_run_conversation(
        self, messages: list[dict], tools: list[dict] | None, extra_params: dict | None = None
    ) -> str:
        """Run the model, executing any tool calls it requests, until a final answer."""
        extra_params = extra_params or {}
        for _ in range(MAX_TOOL_ITERATIONS):
            message = await self.coordinator.async_chat_completion(
                messages, tools=tools, **extra_params
            )
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                return message.get("content") or ""

            # On rajoute le message assistant (avec ses tool_calls) à l'historique
            # de travail de ce tour (pas à l'historique persistant entre tours).
            messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            for call in tool_calls:
                function = call.get("function", {})
                fn_name = function.get("name")
                raw_args = function.get("arguments") or "{}"
                try:
                    fn_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    fn_args = {}
                    _LOGGER.warning(
                        "Arguments JSON invalides pour l'outil %s: %s", fn_name, raw_args
                    )

                _LOGGER.debug("Executing tool %s with args %s", fn_name, fn_args)
                result = await self._async_dispatch_tool(fn_name, fn_args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

        _LOGGER.warning("Maximum tool iterations reached without a final answer")
        return (
            "Désolé, je n'ai pas réussi à conclure cette demande après plusieurs "
            "étapes d'analyse. Peux-tu reformuler ou préciser ta demande ?"
        )

    async def _async_dispatch_tool(self, fn_name: str, fn_args: dict) -> object:
        """Route un appel d'outil vers ha_tools (état HA) ou memory (souvenirs)."""
        if fn_name == "remember_fact":
            return await self._memory.async_add_fact(fn_args.get("text", ""))
        if fn_name == "list_remembered_facts":
            facts = await self._memory.async_list_facts()
            return {"facts": facts}
        if fn_name == "forget_fact":
            return await self._memory.async_remove_fact(fn_args.get("fact_id", ""))
        return await async_dispatch_tool(self.hass, fn_name, fn_args)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Mammouth AI conversation platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entity = MammouthConversationEntity(hass, coordinator, config_entry)
    async_add_entities([entity])
    _LOGGER.debug("Mammouth AI conversation entity added")
