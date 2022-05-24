"""
Yaml parsing factored out from controller so that it is unit testable
"""

from typing import Any

from pip._internal.utils import logging

import feature_flags._version as _version
from feature_flags.models import FeatureFlagsResponse, Flag, Metadata

LOGGER = logging.getLogger(__name__)


def parse_anonymous_flags(result: dict[str, Any], environment) -> FeatureFlagsResponse:
    """Parse flags return pydantic model"""
    default_values = result["default_values"]
    metadata = Metadata(api_version=_version.__version__)
    if result.get("environments"):
        metadata.supported_environments.extend(result.get("environments"))
    process_environment_overrides(default_values, environment, result)
    feature_flags = bind_feature_flag_objects(default_values)
    return FeatureFlagsResponse(
        metadata=metadata, quick_flags=default_values, feature_flags=feature_flags
    )


def process_environment_overrides(
    default_values: dict[str, bool], environment: str, result: dict[str, Any]
) -> None:
    """Use default values unless specified per environment. e.g. Default off, but
    on for dev,test,stage. Or default on but off for prod.
    """
    environments = result.get("environments")
    if environments:
        environment_overrides = environments.get(environment)
        if environment_overrides:
            for key, value in environment_overrides.items():
                default_values[key] = value


def bind_feature_flag_objects(default_values: dict[str, bool]) -> list[Flag]:
    """Convert a dictionary of bools into a list of objects"""
    feature_flags: list[Flag] = []
    for flag_name, flag_value in default_values.items():
        feature_flags.append(Flag(name=flag_name, enabled=flag_value))
    return feature_flags


def parse_authenticated_flags(
    result: dict[str, Any], environment: str, user_id: str, email: str, roles: list[str]
) -> FeatureFlagsResponse:
    """Parse flags with no reference to connexion objects, return pydantic model"""
    default_values = result["default_values"]
    process_environment_overrides(default_values, environment, result)
    metadata = Metadata(api_version=_version.__version__)
    if result.get("environments"):
        metadata.supported_environments.extend(result.get("environments"))

    for identity in (email, user_id):
        user_overrides = result["user_overrides"].get(identity, "")
        if user_overrides:
            LOGGER.info(f"Applying overides for user {identity}")
            metadata.identities_considered.append(identity)
            for key, value in user_overrides.items():
                default_values[key] = value
    # My roles. What these mean, I don't know.
    # "realm_access": {
    #     "roles": [
    #         "rd_internal",
    #         "offline_access",
    #         "admin",
    #         "uma_authorization",
    #         "rd_copyright"
    #     ]
    # },
    # "resource_access": {
    #     "account": {
    #         "roles": [
    #             "manage-account",
    #             "manage-account-links",
    #             "view-profile"
    #         ]
    #     }
    # },

    for role in roles:
        role_overrides = result["role_overrides"].get(role)
        if role_overrides:
            LOGGER.info(f"Applying overides for role {role}")
            metadata.roles_considered.append(role)
            for key, value in role_overrides.items():
                default_values[key] = value

    feature_flags = bind_feature_flag_objects(default_values)

    return FeatureFlagsResponse(
        metadata=metadata, quick_flags=default_values, feature_flags=feature_flags
    )
