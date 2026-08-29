"""Outils (function calling) permettant à l'IA de lire et configurer Home Assistant.

Conçu pour rester robuste d'une version de Home Assistant à l'autre : on
s'appuie uniquement sur des API publiques et stables (registres area/device/
entity, services standards, lecture/écriture des fichiers automations.yaml et
scripts.yaml + rechargement via les services natifs "reload"). On évite
volontairement les API internes de validation de schéma ou la collection de
stockage Lovelace, qui changent plus souvent d'une version à l'autre.
"""

from __future__ import annotations

import asyncio
import logging
import unicodedata
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from homeassistant.util.yaml import dump as yaml_dump
from homeassistant.util.yaml.loader import load_yaml as yaml_load

_LOGGER = logging.getLogger(__name__)

AUTOMATIONS_FILE = "automations.yaml"
SCRIPTS_FILE = "scripts.yaml"
DASHBOARDS_DIR = "dashboards"

DEFAULT_OVERVIEW_LIMIT = 200
DEFAULT_SEARCH_LIMIT = 50
CALL_SERVICE_TIMEOUT = 30  # secondes ; évite qu'un appareil non réactif ne bloque toute la conversation

# Verrous pour sérialiser les lectures/modifications/écritures de
# automations.yaml et scripts.yaml : sans ça, deux utilisateurs (ou deux
# outils appelés en parallèle) agissant en même temps pourraient s'écraser
# mutuellement (lost update classique sur un fichier partagé).
_AUTOMATIONS_LOCK = asyncio.Lock()
_SCRIPTS_LOCK = asyncio.Lock()


def _normalize(text: str | None) -> str:
    """Minuscule + accents retirés, pour des comparaisons robustes en français.

    Sans ça, chercher "eclairage" ne matche pas "éclairage", et "a 20h00" ne
    matche pas "à 20h00" — une source fréquente de faux "introuvable".
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()

# ---------------------------------------------------------------------------
# Schéma des outils (format function-calling compatible OpenAI)
# ---------------------------------------------------------------------------

HA_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_ha_overview",
            "description": (
                "Retourne une vue d'ensemble de l'instance Home Assistant : "
                "zones (areas), et les entités qu'elles contiennent avec leur "
                "état actuel. Utilise les filtres domain/area/limit pour "
                "limiter le volume sur une grosse installation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Filtrer par domaine, ex: light, switch, sensor, climate.",
                    },
                    "area": {
                        "type": "string",
                        "description": "Filtrer par nom ou id de zone.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Nombre maximum d'entités retournées (défaut 200).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": (
                "Recherche des entités par mot-clé dans leur nom ou entity_id. "
                "Utile pour retrouver une entité précise sans charger tout l'inventaire."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Mot-clé recherché."},
                    "domain": {"type": "string", "description": "Filtrer par domaine (optionnel)."},
                    "limit": {"type": "integer", "description": "Nombre max de résultats (défaut 50)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_details",
            "description": "Retourne l'état complet, les attributs, la zone et l'appareil d'une entité précise.",
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string"}},
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_entity_area",
            "description": (
                "Assigne une entité (y compris une automatisation ou un script) à une zone "
                "existante. C'est un changement de configuration : présente le changement "
                "précis à l'utilisateur et attends sa confirmation avant d'appeler cet outil, "
                "sauf si sa demande initiale nommait déjà exactement cette entité et cette zone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "area": {"type": "string", "description": "Nom ou id de la zone (doit déjà exister)."},
                },
                "required": ["entity_id", "area"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_automations",
            "description": (
                "Liste toutes les automatisations existantes (id, entity_id réel, nom, "
                "description, état, mode). Utilise TOUJOURS le entity_id renvoyé ici pour "
                "cibler une automatisation avec un autre outil (assign_entity_area, call_service...) "
                "— ne le déduis jamais toi-même en transformant l'alias, HA peut générer un "
                "entity_id différent de ce à quoi on s'attend (accents, doublons, numérotation)."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_automation",
            "description": (
                "Retourne la configuration complète (triggers/conditions/actions) d'une "
                "automatisation existante, ainsi que son entity_id réel et son état. "
                "Utilise TOUJOURS cet entity_id pour cibler l'automatisation avec un autre "
                "outil, ne le déduis jamais toi-même à partir de l'alias."
            ),
            "parameters": {
                "type": "object",
                "properties": {"automation_id": {"type": "string", "description": "Id de configuration, entity_id (ex: automation.xyz), ou alias exact — les trois fonctionnent."}},
                "required": ["automation_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_automation",
            "description": (
                "Crée une nouvelle automatisation Home Assistant et la recharge "
                "immédiatement (aucun redémarrage requis). trigger/condition/action "
                "doivent utiliser la syntaxe native Home Assistant (les mêmes clés "
                "que dans un fichier automations.yaml)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "alias": {"type": "string", "description": "Nom lisible de l'automatisation."},
                    "description": {"type": "string"},
                    "trigger": {"type": "array", "items": {"type": "object"}},
                    "condition": {"type": "array", "items": {"type": "object"}},
                    "action": {"type": "array", "items": {"type": "object"}},
                    "mode": {
                        "type": "string",
                        "enum": ["single", "restart", "queued", "parallel"],
                    },
                },
                "required": ["alias", "trigger", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_automation",
            "description": "Modifie une automatisation existante par id. Seuls les champs fournis sont remplacés.",
            "parameters": {
                "type": "object",
                "properties": {
                    "automation_id": {"type": "string", "description": "Id de configuration, entity_id (ex: automation.xyz), ou alias exact — les trois fonctionnent."},
                    "alias": {"type": "string"},
                    "description": {"type": "string"},
                    "trigger": {"type": "array", "items": {"type": "object"}},
                    "condition": {"type": "array", "items": {"type": "object"}},
                    "action": {"type": "array", "items": {"type": "object"}},
                    "mode": {"type": "string"},
                },
                "required": ["automation_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_automation",
            "description": "Supprime une automatisation existante par id.",
            "parameters": {
                "type": "object",
                "properties": {"automation_id": {"type": "string", "description": "Id de configuration, entity_id (ex: automation.xyz), ou alias exact — les trois fonctionnent."}},
                "required": ["automation_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_scripts",
            "description": "Liste tous les scripts existants (id, nom, mode).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_script",
            "description": "Crée un nouveau script Home Assistant (séquence d'actions réutilisable) et le recharge immédiatement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "string",
                        "description": "Identifiant technique (minuscules, underscores). Généré depuis l'alias si absent.",
                    },
                    "alias": {"type": "string"},
                    "sequence": {"type": "array", "items": {"type": "object"}},
                    "mode": {
                        "type": "string",
                        "enum": ["single", "restart", "queued", "parallel"],
                    },
                },
                "required": ["alias", "sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dashboards",
            "description": "Liste les dashboards Lovelace générés par cet assistant (mode YAML).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_dashboard",
            "description": (
                "Génère un fichier de dashboard Lovelace (mode YAML) dans "
                "config/dashboards/. Si ce dashboard n'est pas encore déclaré "
                "dans configuration.yaml, une étape manuelle unique (ajout + "
                "redémarrage) est nécessaire et sera indiquée dans le résultat ; "
                "les modifications suivantes du même fichier seront prises en "
                "compte automatiquement, sans redémarrage."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url_path": {
                        "type": "string",
                        "description": "Slug d'URL, ex: 'energie'. Généré depuis le titre si absent.",
                    },
                    "icon": {"type": "string"},
                    "views": {
                        "type": "array",
                        "description": "Liste de vues Lovelace au format natif (title, path, cards...).",
                        "items": {"type": "object"},
                    },
                },
                "required": ["title", "views"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_service",
            "description": (
                "Exécute une action immédiate sur un ou plusieurs appareils Home Assistant : "
                "allumer/éteindre/basculer une lumière ou un interrupteur, régler une température, "
                "ouvrir/fermer un volet, etc. C'est le seul moyen d'agir réellement sur un appareil "
                "(les autres outils ne font que lire ou configurer). Vérifie l'entity_id exact avec "
                "search_entities ou get_entity_details si tu n'es pas certain."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domaine du service, ex: light, switch, climate, cover.",
                    },
                    "service": {
                        "type": "string",
                        "description": "Nom du service, ex: turn_on, turn_off, toggle, set_temperature.",
                    },
                    "entity_id": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste des entity_id ciblés (un seul élément si une entité).",
                    },
                    "data": {
                        "type": "object",
                        "description": "Paramètres additionnels du service, ex: {'temperature': 21}.",
                    },
                },
                "required": ["domain", "service", "entity_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Helpers de lecture/écriture YAML (bloquants -> à appeler via executor)
# ---------------------------------------------------------------------------


def _read_yaml_list(path: str) -> list:
    p = Path(path)
    if not p.exists():
        return []
    data = yaml_load(str(p))
    if not data:
        return []
    if not isinstance(data, list):
        raise ValueError(f"{path} ne contient pas une liste YAML valide.")
    return data


def _write_yaml_list(path: str, data: list) -> None:
    Path(path).write_text(yaml_dump(data), encoding="utf-8")


def _read_yaml_dict(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml_load(str(p))
    if not data:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} ne contient pas un dictionnaire YAML valide.")
    return data


def _write_yaml_dict(path: str, data: dict) -> None:
    Path(path).write_text(yaml_dump(data), encoding="utf-8")


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Lecture de l'instance
# ---------------------------------------------------------------------------


async def _get_ha_overview(
    hass: HomeAssistant,
    domain: str | None = None,
    area: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    limit = limit or DEFAULT_OVERVIEW_LIMIT
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    area_filter_id = None
    if area:
        area_norm = _normalize(area)
        for a in area_reg.async_list_areas():
            if a.id == area or _normalize(a.name) == area_norm:
                area_filter_id = a.id
                break
        if area_filter_id is None:
            return {"error": f"Zone '{area}' introuvable."}

    all_states = hass.states.async_all()
    areas_out: dict[str, list[dict[str, Any]]] = {}
    unassigned: list[dict[str, Any]] = []
    count = 0
    truncated = False

    for state in all_states:
        if domain and state.domain != domain:
            continue

        entry = ent_reg.async_get(state.entity_id)
        area_id = entry.area_id if entry else None
        if entry and not area_id and entry.device_id:
            device = dev_reg.async_get(entry.device_id)
            if device:
                area_id = device.area_id

        if area_filter_id and area_id != area_filter_id:
            continue

        if count >= limit:
            truncated = True
            break

        item = {
            "entity_id": state.entity_id,
            "domain": state.domain,
            "name": state.name,
            "state": state.state,
            "device_class": state.attributes.get("device_class"),
        }
        count += 1

        if area_id:
            area_entry = area_reg.async_get_area(area_id)
            area_name = area_entry.name if area_entry else area_id
            areas_out.setdefault(area_name, []).append(item)
        else:
            unassigned.append(item)

    result = {
        "total_entities_in_instance": len(all_states),
        "entities_returned": count,
        "truncated": truncated,
        "areas": areas_out,
        "entities_without_area": unassigned,
    }

    # Filet de sécurité : si un domaine était demandé et ne donne rien, on
    # élargit automatiquement plutôt que de compter sur le modèle pour le
    # faire lui-même (il ne le fait pas toujours de façon fiable).
    if domain and count == 0:
        widened = await _get_ha_overview(hass, domain=None, area=area, limit=limit)
        widened["note"] = (
            f"Aucune entité trouvée pour le domaine '{domain}' ; résultats élargis "
            "à tous les domaines. Vérifie le champ 'domain' de chaque entité."
        )
        return widened

    return result


async def _search_entities(
    hass: HomeAssistant,
    query: str,
    domain: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    limit = limit or DEFAULT_SEARCH_LIMIT
    query_norm = _normalize(query)

    def _matches(state, domain_filter: str | None) -> bool:
        if domain_filter and state.domain != domain_filter:
            return False
        return query_norm in _normalize(state.entity_id) or query_norm in _normalize(state.name)

    results = []
    for state in hass.states.async_all():
        if _matches(state, domain):
            results.append(
                {"entity_id": state.entity_id, "domain": state.domain, "name": state.name, "state": state.state}
            )
            if len(results) >= limit:
                break

    # Filet de sécurité : si un domaine était demandé et ne donne rien, on
    # élargit automatiquement plutôt que de compter sur le modèle pour le
    # faire lui-même (il ne le fait pas toujours de façon fiable).
    if domain and not results:
        for state in hass.states.async_all():
            if _matches(state, None):
                results.append(
                    {"entity_id": state.entity_id, "domain": state.domain, "name": state.name, "state": state.state}
                )
                if len(results) >= limit:
                    break
        if results:
            return {
                "results": results,
                "count": len(results),
                "note": (
                    f"Aucun résultat pour '{query}' dans le domaine '{domain}' ; résultats "
                    "élargis à tous les domaines. Vérifie le champ 'domain' de chaque entité."
                ),
            }

    return {"results": results, "count": len(results)}


async def _assign_entity_area(hass: HomeAssistant, entity_id: str, area: str) -> dict[str, Any]:
    if not entity_id or not area:
        return {"error": "entity_id et area sont requis."}

    if hass.states.get(entity_id) is None:
        return {"error": f"Entité {entity_id} introuvable."}

    area_reg = ar.async_get(hass)
    area_norm = _normalize(area)
    area_entry = None
    for a in area_reg.async_list_areas():
        if a.id == area or _normalize(a.name) == area_norm:
            area_entry = a
            break

    if area_entry is None:
        available = ", ".join(a.name for a in area_reg.async_list_areas())
        return {"error": f"Zone '{area}' introuvable. Zones existantes : {available or 'aucune'}."}

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return {
            "error": (
                f"{entity_id} n'a pas d'entrée dans le registre d'entités : "
                "impossible de lui assigner une zone directement."
            )
        }

    ent_reg.async_update_entity(entity_id, area_id=area_entry.id)
    return {
        "success": True,
        "message": f"{entity_id} assigné à la zone '{area_entry.name}'.",
    }


async def _get_entity_details(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    state = hass.states.get(entity_id)
    if not state:
        return {"error": f"Entité {entity_id} introuvable."}

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    area_name = None
    device_name = None
    entry = ent_reg.async_get(entity_id)
    if entry:
        area_id = entry.area_id
        if entry.device_id:
            device = dev_reg.async_get(entry.device_id)
            if device:
                device_name = device.name_by_user or device.name
                if not area_id:
                    area_id = device.area_id
        if area_id:
            area_entry = area_reg.async_get_area(area_id)
            area_name = area_entry.name if area_entry else area_id

    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "area": area_name,
        "device": device_name,
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }


# ---------------------------------------------------------------------------
# Automatisations
# ---------------------------------------------------------------------------


def _build_automation_entity_map(hass: HomeAssistant) -> dict[str, str]:
    """Associe l'id de config de chaque automatisation à son entity_id réel.

    Sans ça, le modèle devrait deviner l'entity_id en slugifiant l'alias —
    ce qui ne correspond pas toujours exactement à ce que Home Assistant
    génère réellement (accents, doublons, numérotation).
    """
    mapping: dict[str, str] = {}
    for state in hass.states.async_all("automation"):
        config_id = state.attributes.get("id")
        if config_id is not None:
            mapping[str(config_id)] = state.entity_id
    return mapping


def _find_automation_entity_id_by_alias(hass: HomeAssistant, alias: str | None) -> str | None:
    if not alias:
        return None
    for state in hass.states.async_all("automation"):
        if state.name == alias:
            return state.entity_id
    return None


async def _list_automations(hass: HomeAssistant) -> list[dict[str, Any]]:
    path = hass.config.path(AUTOMATIONS_FILE)
    async with _AUTOMATIONS_LOCK:
        items = await hass.async_add_executor_job(_read_yaml_list, path)

    entity_map = _build_automation_entity_map(hass)
    result = []
    for item in items:
        config_id = item.get("id")
        entity_id = entity_map.get(str(config_id)) if config_id is not None else None
        if entity_id is None:
            entity_id = _find_automation_entity_id_by_alias(hass, item.get("alias"))
        state_obj = hass.states.get(entity_id) if entity_id else None
        result.append(
            {
                "id": config_id,
                "entity_id": entity_id,
                "alias": item.get("alias"),
                "description": item.get("description", ""),
                "mode": item.get("mode", "single"),
                "state": state_obj.state if state_obj else None,
            }
        )
    return result


def _find_automation_item(hass: HomeAssistant, items: list[dict], automation_id: str) -> dict | None:
    """Trouve une automatisation par id de config, par entity_id, ou par alias.

    Le paramètre s'appelle "automation_id" mais le modèle a naturellement
    plusieurs identifiants sous la main selon l'outil qui les lui a fournis
    juste avant (id de config numérique, entity_id réel, ou simplement le
    nom) : on accepte les trois plutôt que d'échouer sur une confusion de
    nommage entre ces concepts proches.
    """
    target = str(automation_id)

    # 1) correspondance directe par id de configuration
    for item in items:
        if str(item.get("id")) == target:
            return item

    # 2) correspondance par entity_id réel (ex: "automation.xyz")
    if target.startswith("automation."):
        for state in hass.states.async_all("automation"):
            if state.entity_id == target:
                config_id = state.attributes.get("id")
                if config_id is not None:
                    for item in items:
                        if str(item.get("id")) == str(config_id):
                            return item
                # Pas d'id exposé par l'entité : repli par nom de l'entité.
                name_norm = _normalize(state.name)
                for item in items:
                    if _normalize(str(item.get("alias", ""))) == name_norm:
                        return item
                break

    # 3) correspondance par alias (accents/casse ignorés)
    target_norm = _normalize(target)
    for item in items:
        if _normalize(str(item.get("alias", ""))) == target_norm:
            return item

    return None



async def _get_automation(hass: HomeAssistant, automation_id: str) -> dict[str, Any]:
    path = hass.config.path(AUTOMATIONS_FILE)
    async with _AUTOMATIONS_LOCK:
        items = await hass.async_add_executor_job(_read_yaml_list, path)
    item = _find_automation_item(hass, items, automation_id)
    if item is None:
        return {"error": f"Automatisation {automation_id} introuvable."}
    # Vue nettoyée pour le modèle (pas d'écriture ici, juste l'affichage) :
    # évite de lui montrer un éventuel doublon trigger/triggers pas encore
    # réparé. schema_issue_on_disk indique si CE fichier réel avait un souci
    # — get_automation ne fait que lire, il ne corrige jamais le disque :
    # seul update_automation (une écriture) répare réellement le fichier.
    clean_item = dict(item)
    had_issue = _dedupe_automation_item(clean_item)
    clean_item["schema_issue_on_disk"] = had_issue
    if had_issue:
        clean_item["_note"] = (
            "Le fichier réel contient encore un doublon trigger/triggers (ou condition/action). "
            "Cette vue est nettoyée pour l'affichage mais RIEN N'A ÉTÉ ÉCRIT SUR DISQUE. "
            "Pour réellement corriger, appelle update_automation sur cette automatisation "
            "(même sans changer de champ) — lui seul réécrit le fichier."
        )

    config_id = clean_item.get("id")
    entity_map = _build_automation_entity_map(hass)
    entity_id = entity_map.get(str(config_id)) if config_id is not None else None
    if entity_id is None:
        entity_id = _find_automation_entity_id_by_alias(hass, clean_item.get("alias"))
    clean_item["entity_id"] = entity_id
    if entity_id:
        state_obj = hass.states.get(entity_id)
        clean_item["state"] = state_obj.state if state_obj else None

    return clean_item


async def _find_automation_entity_id(hass: HomeAssistant, automation_id: str, alias: str) -> str | None:
    for state in hass.states.async_all("automation"):
        if str(state.attributes.get("id")) == str(automation_id) or state.name == alias:
            return state.entity_id
    return None


def _validate_object_list(field_name: str, value: Any) -> str | None:
    """Vérifie qu'une liste trigger/condition/action/sequence est bien formée.

    Écrire un YAML syntaxiquement valide mais structurellement invalide
    (ex: une chaîne au lieu d'un objet) ne se remarque qu'au reload, quand
    l'automatisation refuse de charger — mieux vaut le détecter avant
    d'écrire sur disque et retourner une erreur exploitable au modèle.
    """
    if not isinstance(value, list):
        return f"{field_name} doit être une liste, pas {type(value).__name__}."
    if not all(isinstance(v, dict) for v in value):
        return f"{field_name} doit être une liste d'objets (dictionnaires), pas de chaînes de texte brutes."
    return None


# Home Assistant est passé du schéma singulier (trigger/condition/action) au
# schéma pluriel (triggers/conditions/actions) ; les deux sont acceptés en
# lecture mais avoir les DEUX clés sur la même automatisation fait échouer
# son chargement ("Cannot specify both 'trigger' and 'triggers'"). On écrit
# donc toujours en pluriel (schéma canonique actuel), et on nettoie
# systématiquement toute clé singulière restante à chaque écriture — y
# compris sur les automatisations qu'on ne touche pas directement, ce qui
# répare aussi d'anciennes entrées cassées par des versions précédentes.
_FIELD_ALIASES = (("trigger", "triggers"), ("condition", "conditions"), ("action", "actions"))


def _set_automation_field(item: dict, plural_key: str, value: Any) -> None:
    singular_key = next(s for s, p in _FIELD_ALIASES if p == plural_key)
    item.pop(singular_key, None)
    item[plural_key] = value


def _dedupe_automation_item(item: dict) -> bool:
    """Corrige en place une entrée qui aurait les deux clés (singulier + pluriel).

    Retourne True si une correction a été appliquée, pour que l'appelant
    puisse distinguer "c'était déjà propre" de "j'ai nettoyé quelque chose"
    — utile pour ne pas laisser croire qu'une simple lecture a réparé le
    fichier sur disque (seule une écriture, via update_automation, le fait).
    """
    changed = False
    for singular, plural in _FIELD_ALIASES:
        if singular in item and plural in item:
            # Les deux existent : on garde la valeur plurielle (schéma
            # canonique actuel) et on retire le doublon singulier.
            item.pop(singular)
            changed = True
        elif singular in item:
            # Seule l'ancienne clé existe : migration vers le schéma pluriel.
            item[plural] = item.pop(singular)
            changed = True
    return changed


async def _write_automations(hass: HomeAssistant, path: str, items: list[dict]) -> None:
    for item in items:
        _dedupe_automation_item(item)
    await hass.async_add_executor_job(_write_yaml_list, path, items)


async def _create_automation(
    hass: HomeAssistant,
    alias: str,
    trigger: list,
    action: list,
    description: str = "",
    condition: list | None = None,
    mode: str = "single",
) -> dict[str, Any]:
    if not alias or not trigger or not action:
        return {"error": "alias, trigger et action sont requis et ne peuvent être vides."}

    for field_name, value in (("trigger", trigger), ("action", action)):
        err = _validate_object_list(field_name, value)
        if err:
            return {"error": err}
    if condition is not None:
        err = _validate_object_list("condition", condition)
        if err:
            return {"error": err}

    path = hass.config.path(AUTOMATIONS_FILE)

    async with _AUTOMATIONS_LOCK:
        items = await hass.async_add_executor_job(_read_yaml_list, path)

        new_id = dt_util.utcnow().strftime("%Y%m%d%H%M%S%f")
        new_item = {
            "id": new_id,
            "alias": alias,
            "description": description or "",
            "mode": mode or "single",
        }
        _set_automation_field(new_item, "triggers", trigger)
        _set_automation_field(new_item, "conditions", condition or [])
        _set_automation_field(new_item, "actions", action)
        items.append(new_item)

        try:
            await _write_automations(hass, path, items)
        except Exception as err:  # pylint: disable=broad-except
            return {"error": f"Écriture de {AUTOMATIONS_FILE} impossible: {err}"}

    await hass.services.async_call("automation", "reload", blocking=True)
    entity_id = await _find_automation_entity_id(hass, new_id, alias)

    return {
        "success": True,
        "id": new_id,
        "entity_id": entity_id,
        "message": f"Automatisation '{alias}' créée et rechargée avec succès.",
    }


async def _update_automation(
    hass: HomeAssistant,
    automation_id: str,
    alias: str | None = None,
    description: str | None = None,
    trigger: list | None = None,
    condition: list | None = None,
    action: list | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    for field_name, value in (("trigger", trigger), ("condition", condition), ("action", action)):
        if value is not None:
            err = _validate_object_list(field_name, value)
            if err:
                return {"error": err}

    path = hass.config.path(AUTOMATIONS_FILE)

    async with _AUTOMATIONS_LOCK:
        items = await hass.async_add_executor_job(_read_yaml_list, path)
        item = _find_automation_item(hass, items, automation_id)

        if item is None:
            return {"error": f"Automatisation {automation_id} introuvable."}

        if alias is not None:
            item["alias"] = alias
        if description is not None:
            item["description"] = description
        if mode is not None:
            item["mode"] = mode
        if trigger is not None:
            _set_automation_field(item, "triggers", trigger)
        if condition is not None:
            _set_automation_field(item, "conditions", condition)
        if action is not None:
            _set_automation_field(item, "actions", action)

        await _write_automations(hass, path, items)

    await hass.services.async_call("automation", "reload", blocking=True)
    return {"success": True, "message": f"Automatisation {automation_id} mise à jour."}


async def _delete_automation(hass: HomeAssistant, automation_id: str) -> dict[str, Any]:
    path = hass.config.path(AUTOMATIONS_FILE)

    async with _AUTOMATIONS_LOCK:
        items = await hass.async_add_executor_job(_read_yaml_list, path)
        item = _find_automation_item(hass, items, automation_id)

        if item is None:
            return {"error": f"Automatisation {automation_id} introuvable."}

        new_items = [i for i in items if i is not item]
        await _write_automations(hass, path, new_items)

    await hass.services.async_call("automation", "reload", blocking=True)
    return {"success": True, "message": f"Automatisation {automation_id} supprimée."}


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------


async def _list_scripts(hass: HomeAssistant) -> list[dict[str, Any]]:
    path = hass.config.path(SCRIPTS_FILE)
    async with _SCRIPTS_LOCK:
        data = await hass.async_add_executor_job(_read_yaml_dict, path)
    return [
        {"script_id": key, "alias": value.get("alias", key), "mode": value.get("mode", "single")}
        for key, value in data.items()
    ]


async def _create_script(
    hass: HomeAssistant,
    alias: str,
    sequence: list,
    script_id: str | None = None,
    mode: str = "single",
) -> dict[str, Any]:
    if not alias or not sequence:
        return {"error": "alias et sequence sont requis et ne peuvent être vides."}

    err = _validate_object_list("sequence", sequence)
    if err:
        return {"error": err}

    path = hass.config.path(SCRIPTS_FILE)

    async with _SCRIPTS_LOCK:
        data = await hass.async_add_executor_job(_read_yaml_dict, path)

        slug = slugify(script_id or alias)
        original_slug = slug
        i = 2
        while slug in data:
            slug = f"{original_slug}_{i}"
            i += 1

        data[slug] = {"alias": alias, "sequence": sequence, "mode": mode or "single"}

        try:
            await hass.async_add_executor_job(_write_yaml_dict, path, data)
        except Exception as err:  # pylint: disable=broad-except
            return {"error": f"Écriture de {SCRIPTS_FILE} impossible: {err}"}

    await hass.services.async_call("script", "reload", blocking=True)
    return {
        "success": True,
        "script_id": slug,
        "entity_id": f"script.{slug}",
        "message": f"Script '{alias}' créé et rechargé avec succès.",
    }


# ---------------------------------------------------------------------------
# Dashboards (mode YAML)
# ---------------------------------------------------------------------------


async def _list_dashboards(hass: HomeAssistant) -> dict[str, Any]:
    dash_dir = Path(hass.config.path(DASHBOARDS_DIR))
    if not dash_dir.exists():
        return {"dashboards": [], "note": "Aucun dashboard généré pour le moment par cet assistant."}
    files = await hass.async_add_executor_job(
        lambda: sorted(p.stem for p in dash_dir.glob("*.yaml"))
    )
    return {"dashboards": files}


async def _create_dashboard(
    hass: HomeAssistant,
    title: str,
    views: list,
    url_path: str | None = None,
    icon: str | None = None,
) -> dict[str, Any]:
    if not title or not views:
        return {"error": "title et views sont requis et ne peuvent être vides."}

    slug = slugify(url_path or title)
    file_path = Path(hass.config.path(DASHBOARDS_DIR)) / f"{slug}.yaml"

    content: dict[str, Any] = {"title": title, "views": views}
    if icon:
        content["icon"] = icon

    try:
        await hass.async_add_executor_job(_write_text_file, file_path, yaml_dump(content))
    except Exception as err:  # pylint: disable=broad-except
        return {"error": f"Écriture du dashboard impossible: {err}"}

    config_snippet = (
        "lovelace:\n"
        "  dashboards:\n"
        f"    {slug}:\n"
        "      mode: yaml\n"
        f"      filename: {DASHBOARDS_DIR}/{slug}.yaml\n"
        f"      title: \"{title.replace(chr(34), chr(39))}\"\n"
        + (f"      icon: {icon}\n" if icon else "")
    )

    return {
        "success": True,
        "file": f"{DASHBOARDS_DIR}/{slug}.yaml",
        "message": (
            f"Fichier de dashboard '{slug}.yaml' généré dans config/{DASHBOARDS_DIR}/. "
            "S'il n'est pas déjà déclaré, ajoute une seule fois ce bloc dans configuration.yaml "
            "puis redémarre Home Assistant (les modifications suivantes de ce fichier seront "
            f"ensuite prises en compte automatiquement, sans redémarrage) :\n{config_snippet}"
        ),
    }


# ---------------------------------------------------------------------------
# Contrôle direct (action immédiate)
# ---------------------------------------------------------------------------


async def _call_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    entity_id: str | list[str],
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not domain or not service or not entity_id:
        return {"error": "domain, service et entity_id sont requis."}

    if isinstance(entity_id, str):
        entity_id = [entity_id]

    missing = [e for e in entity_id if hass.states.get(e) is None]
    if missing:
        return {
            "error": (
                f"Entité(s) introuvable(s): {', '.join(missing)}. "
                "Vérifie l'entity_id exact avec search_entities avant de réessayer."
            )
        }

    service_data = dict(data or {})
    service_data["entity_id"] = entity_id

    try:
        async with asyncio.timeout(CALL_SERVICE_TIMEOUT):
            await hass.services.async_call(domain, service, service_data, blocking=True)
    except asyncio.TimeoutError:
        return {
            "error": (
                f"{domain}.{service} n'a pas répondu dans les {CALL_SERVICE_TIMEOUT}s "
                "(appareil probablement non réactif)."
            )
        }
    except Exception as err:  # pylint: disable=broad-except
        return {"error": f"Échec de l'appel {domain}.{service}: {err}"}

    new_states = {e: hass.states.get(e).state for e in entity_id if hass.states.get(e)}
    return {
        "success": True,
        "message": f"{domain}.{service} exécuté sur {', '.join(entity_id)}.",
        "new_states": new_states,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    "get_ha_overview": _get_ha_overview,
    "search_entities": _search_entities,
    "get_entity_details": _get_entity_details,
    "assign_entity_area": _assign_entity_area,
    "list_automations": _list_automations,
    "get_automation": _get_automation,
    "create_automation": _create_automation,
    "update_automation": _update_automation,
    "delete_automation": _delete_automation,
    "list_scripts": _list_scripts,
    "create_script": _create_script,
    "list_dashboards": _list_dashboards,
    "create_dashboard": _create_dashboard,
    "call_service": _call_service,
}


async def async_dispatch_tool(hass: HomeAssistant, name: str, arguments: dict[str, Any]) -> Any:
    """Exécute l'outil demandé par le modèle et retourne un résultat sérialisable en JSON."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"Outil inconnu: {name}"}

    try:
        if handler in (_list_automations, _list_scripts, _list_dashboards):
            return await handler(hass)
        return await handler(hass, **arguments)
    except TypeError as err:
        return {"error": f"Arguments invalides pour {name}: {err}"}
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Erreur lors de l'exécution de l'outil %s", name)
        return {"error": f"Erreur lors de l'exécution de {name}: {err}"}
