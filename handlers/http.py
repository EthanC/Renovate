from json import JSONDecodeError
from typing import Any, Dict, Optional, Self, Union

import httpx
from httpx import Response, TimeoutException
from loguru import logger


class HTTP:
    """HTTP client used to perform web requests."""

    def GET(self: Self, url: str) -> Optional[Union[Dict[str, Any], str]]:
        """Perform an HTTP GET request and return its response."""

        logger.debug(f"HTTP GET {url}")

        try:
            res: Response = httpx.get(url, timeout=30.0, follow_redirects=True)

            res.raise_for_status()

            logger.trace(f"HTTP {res.status_code} GET {url}")
            logger.trace(res.text)

            return res.json()
        except (JSONDecodeError, UnicodeDecodeError) as e:
            logger.debug(
                f"HTTP GET {url} response is not JSON, returning raw text ({e})"
            )

            return res.text
        except TimeoutException as e:
            # SteamCMD requests often result in a TimeoutException,
            # quietly log and continue on.
            logger.debug(f"HTTP GET {url} failed, {e}")
        except Exception as e:
            logger.error(f"HTTP GET {url} failed, {e}")
