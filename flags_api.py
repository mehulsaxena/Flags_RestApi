"""REST API endpoints for getting active flags
"""
import logging
from typing import Any, Union

import cachetools
import connexion
import connexion.lifecycle

import feature_flags.db.transactions as transactions
import feature_flags.models as models
import feature_flags.read.yaml_parser as yaml_parser
from feature_flags.read.controller_utils import LIMITER, exempt_when
from feature_flags.utils.scope_helpers import public_endpoint

LOGGER = logging.getLogger(__name__)


@LIMITER.limit("1/second", override_defaults=True, exempt_when=exempt_when)
@public_endpoint
@cachetools.cached(cache=cachetools.TTLCache(maxsize=1024, ttl=10))
def flags(
    application: str, environment: str
) -> Union[
    models.FeatureFlagsResponse, connexion.lifecycle.ConnexionResponse, dict[str, Any]
]:
    """Return flags for anonymous users"""
    result = transactions.get_record(application)
    if not result:
        LOGGER.warning(f"Didn't find {application}")
        return connexion.problem(
            status=404,
            title="Application not found",
            detail="That application does not exist",
            type="about:blank",
        )
    parsed = yaml_parser.parse_anonymous_flags(result, environment)
    return parsed.dict()


@LIMITER.limit("1/second", override_defaults=True, exempt_when=exempt_when)
@public_endpoint
# cachetools can't memoize this signature becuase of the dict (kwargs holds a dict!)
# @cachetools.cached(cache=cachetools.TTLCache(maxsize=1024, ttl=10))
def flags_for_user(
    application: str, environment: str, **kwargs: Any
) -> Union[
    models.FeatureFlagsResponse, connexion.lifecycle.ConnexionResponse, dict[str, Any]
]:
    """Return flags for specific users/roles. If doesn't apply return anonymous users'"""
    # cache_safe_kwargs = orjson.dumps(kwargs, sort_keys=True)

    result = transactions.get_record(application)
    if not result:
        LOGGER.warning(f"Didn't find {application}")
        return connexion.problem(
            status=404,
            title="Application not found",
            detail="That application does not exist",
            type="about:blank",
        )
    user_id = kwargs["token_info"].get("preferred_username")  # noqa
    email = kwargs["token_info"].get("email")
    roles = kwargs["token_info"].get("realm_access", {}).get("roles", [])

    LOGGER.info(f"flags for user for {user_id}, {email} and roles")

    parsed = yaml_parser.parse_authenticated_flags(
        result, environment, user_id, email, roles
    )
    return parsed.dict()


@LIMITER.limit("10/minute", override_defaults=True, exempt_when=exempt_when)
@public_endpoint
@cachetools.cached(cache=cachetools.TTLCache(maxsize=1024, ttl=60 * 60))
def applications() -> Union[connexion.lifecycle.ConnexionResponse, list[str]]:
    """Return applications that have flags
    Cache for one hour
    """
    return transactions.get_applications()
